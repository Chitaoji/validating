"""
Provides a lightweight :func:`attr` descriptor factory that adds runtime validation to
dataclass fields.

NOTE: this module is private. All functions and objects are available in the main
:mod:`validating` namespace - use that instead.

"""

import sys
from ast import (
    Attribute,
    If,
    Import,
    ImportFrom,
    Name,
    NodeVisitor,
    parse,
)
from dataclasses import Field, field
from functools import partialmethod
from importlib import import_module
from pathlib import Path
from types import UnionType
from typing import (
    Any,
    Callable,
    ForwardRef,
    Literal,
    Optional,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

try:  # pragma: no cover - Python >= 3.11
    from typing import NotRequired, Required, Unpack
except ImportError:  # pragma: no cover - Python < 3.11
    from typing_extensions import NotRequired, Required, Unpack

try:  # pragma: no cover - available on modern Python versions
    from typing import is_typeddict
except ImportError:  # pragma: no cover - compatibility fallback
    def is_typeddict(type_hint: Any) -> bool:
        return bool(
            isinstance(type_hint, type)
            and isinstance(getattr(type_hint, "__annotations__", None), dict)
            and hasattr(type_hint, "__required_keys__")
            and hasattr(type_hint, "__optional_keys__")
        )

__all__ = ["attr"]


def attr(
    *,
    default: Any = ...,
    default_factory: Callable[[], Any] = ...,
    allowlist: list = ...,
    denylist: list = ...,
    validator: Callable[[Any], bool] = ...,
    lb: Any = ...,
    slb: Any = ...,
    ub: Any = ...,
    sub: Any = ...,
    init: bool = True,
    repr: bool = True,
    hash: Optional[bool] = None,
    compare: bool = True,
    kw_only: bool = False,
) -> Any:
    """
    Build a validated attribute descriptor, optionally wrapped as a dataclass field.

    The returned object enforces constraints both during initialization and on
    later assignment. It is primarily intended for classes that store instance
    state in ``__dict__`` (for example regular dataclasses without ``slots=True``).

    Parameters
    ----------
    default : Any, optional
        Default value, by default ...
    default_factory : Callable[[], Any], optional
        Callable used to generate a default value lazily, by default ...
    allowlist : list, optional
        Allowed values, by default ...
    denylist : list, optional
        Forbidden values, by default ...
    lb : Any, optional
        Lower bound (inclusive), by default ...
    slb : Any, optional
        Strict lower bound (exclusive), by default ...
    ub : Any, optional
        Upper bound (inclusive), by default ...
    sub : Any, optional
        Strict upper bound (exclusive), by default ...
    validator : Callable[[Any], bool], optional
        Custom validator function, by default ...
    init : bool, optional
        Whether this field should be included as a generated ``__init__()``
        parameter when used with ``dataclasses.dataclass``, by default True.
    repr : bool, optional
        Whether this field should be included in the generated ``__repr__()``
        output, by default True.
    hash : Optional[bool], optional
        Whether this field should be included in generated ``__hash__()``.
        Follows ``dataclasses.field`` behavior where ``None`` defers to
        ``compare``, by default None.
    compare : bool, optional
        Whether this field should be used in generated comparison methods,
        by default True.
    kw_only : bool, optional
        Whether this field should be marked as keyword-only for
        ``dataclasses.dataclass`` generated ``__init__()``, by default False.

    Returns
    -------
    Any
        A descriptor-backed field object compatible with dataclasses.

    """
    descriptor = AttrValidator(
        default=default,
        default_factory=default_factory,
        allowlist=allowlist,
        denylist=denylist,
        lb=lb,
        slb=slb,
        ub=ub,
        sub=sub,
        validator=validator,
    )
    if not isinstance(init, bool):
        raise ValidatorError(
            f"invalid init type: expected a bool, got {type(init)!r} instead"
        )
    if not isinstance(repr, bool):
        raise ValidatorError(
            f"invalid repr type: expected a bool, got {type(repr)!r} instead"
        )
    if hash is not None and not isinstance(hash, bool):
        raise ValidatorError(
            f"invalid hash type: expected a bool or None, got {type(hash)!r} instead"
        )
    if not isinstance(compare, bool):
        raise ValidatorError(
            f"invalid compare type: expected a bool, got {type(compare)!r} instead"
        )
    if not isinstance(kw_only, bool):
        raise ValidatorError(
            f"invalid kw_only type: expected a bool, got {type(kw_only)!r} instead"
        )
    return _field_with_guard(
        default=descriptor,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        kw_only=kw_only,
    )


class _FieldWithGuard(Field):
    """Field subclass that forwards descriptor access to the wrapped validator."""

    def __get__(self, instance: object, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return self.default.__get__(instance, owner)

    def __set__(self, instance: object, value: Any) -> None:
        return self.default.__set__(instance, value)


def _field_with_guard(
    *,
    default: Any,
    init: bool,
    repr: bool,
    hash: Optional[bool],
    compare: bool,
    kw_only: bool,
) -> Any:
    """Create a ``dataclasses.field`` clone that preserves descriptor semantics."""

    base_field = field(
        default=default,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        kw_only=kw_only,
    )
    guarded_field = _FieldWithGuard(
        base_field.default,
        base_field.default_factory,
        base_field.init,
        base_field.repr,
        base_field.hash,
        base_field.compare,
        base_field.metadata,
        base_field.kw_only,
    )
    guarded_field._field_type = base_field._field_type
    return guarded_field


def _install_slots_guard(cls: type) -> None:
    if getattr(cls, "__validattr_slots_guard_installed__", False):
        return
    original_post_init = getattr(cls, "__post_init__", None)

    cls.__post_init__ = partialmethod(
        _slots_guard_post_init,
        original_post_init=original_post_init,
    )
    setattr(cls, "__validattr_slots_guard_installed__", True)


def _slots_guard_post_init(
    self: object,
    *args: Any,
    original_post_init: Callable[..., Any] | None,
    **kwargs: Any,
) -> None:
    if not hasattr(self, "__dict__"):
        raise ValidatorError(
            "dataclasses with slots=True are not supported by validattr"
        )
    if original_post_init is not None:
        original_post_init(self, *args, **kwargs)


class AttrValidator:
    """
    Runtime descriptor that validates values written to a single attribute.

    This class is an implementation detail behind :func:`attr` and should not be
    instantiated directly by user code.

    """

    def __init__(
        self,
        *,
        default: Any = ...,
        default_factory: Callable[[], Any] = ...,
        allowlist: list = ...,
        denylist: list = ...,
        lb: Any = ...,
        slb: Any = ...,
        ub: Any = ...,
        sub: Any = ...,
        validator: Callable[[Any], bool] = ...,
    ) -> None:
        self.default = default
        if default is not ... and default_factory is not ...:
            raise ValidatorError(
                "invalid defaults: default and default_factory cannot both be set"
            )
        if default_factory is not ... and not callable(default_factory):
            raise ValidatorError(
                "invalid default_factory type: expected a callable, "
                f"got {type(default_factory)!r} instead"
            )
        self.default_factory = default_factory
        if allowlist is not ... and not isinstance(allowlist, list):
            raise ValidatorError(
                f"invalid allowlist type: expected a list, got {type(allowlist)!r} "
                "instead"
            )
        if denylist is not ... and not isinstance(denylist, list):
            raise ValidatorError(
                f"invalid denylist type: expected a list, got {type(denylist)!r} "
                "instead"
            )
        self.allowlist = allowlist
        self.denylist = denylist
        self.lb = lb
        self.slb = slb
        self.ub = ub
        self.sub = sub
        if self.lb is not ... and self.slb is not ...:
            raise ValidatorError("invalid bounds: lb and slb cannot both be set")
        if self.ub is not ... and self.sub is not ...:
            raise ValidatorError("invalid bounds: ub and sub cannot both be set")
        lower_bound = self.lb if self.lb is not ... else self.slb
        upper_bound = self.ub if self.ub is not ... else self.sub
        if (
            lower_bound is not ...
            and upper_bound is not ...
            and lower_bound >= upper_bound
        ):
            raise ValidatorError(
                f"invalid bounds: lower bound {lower_bound!r} is not less than "
                f"upper bound {upper_bound!r}"
            )
        self.validator = (lambda _: True) if validator is ... else validator
        self.name: str
        self.type: type
        self._deferred_type_ctx: dict[str, Any] | None = None

    def __set_name__(self, cls: type, name: str) -> None:
        _install_slots_guard(cls)
        self.name = name
        try:
            self.type = _resolve_field_type_hint(cls, name)
        except ValidatorError:
            raw_type_hint = cls.__annotations__.get(name)
            if not isinstance(raw_type_hint, str):
                raise
            self._deferred_type_ctx = {
                "owner_cls": cls,
                "owner_localns": _get_owner_localns(),
                "raw_type_hint": raw_type_hint,
            }
            self.type = Any
        self._validate_allowlist(cls)
        self._validate_default(cls)

    def _ensure_type_resolved(self) -> None:
        if self._deferred_type_ctx is None:
            return

        owner_cls = self._deferred_type_ctx["owner_cls"]
        owner_localns = self._deferred_type_ctx["owner_localns"]
        localns = _collect_runtime_localns(owner_localns)
        self.type = _resolve_field_type_hint(
            owner_cls,
            self.name,
            localns=localns,
        )
        self._deferred_type_ctx = None

    def _validate_default(self, cls: type) -> None:
        if self._deferred_type_ctx is not None:
            return
        if self.default_factory is not ...:
            default = self.default_factory()
            mismatch_reason = isoftype(
                default,
                self.type,
                self.name,
                path="default_factory()",
            )
            if mismatch_reason is not None:
                raise ValidatorError(
                    "invalid default_factory return type for "
                    f"{cls.__name__}.{self.name}: {mismatch_reason}"
                )
            self._validate_bounds(cls, default, "default_factory()")
            self._validate_default_membership(cls, default, "default_factory()")
            self._validate_default_custom_validator(cls, default, "default_factory()")
            return
        if self.default is ...:
            return
        mismatch_reason = isoftype(self.default, self.type, self.name, path="")
        if mismatch_reason is not None:
            raise ValidatorError(
                f"invalid default type for {cls.__name__}.{self.name}: "
                f"{mismatch_reason}"
            )
        self._validate_bounds(cls, self.default, "default")
        self._validate_default_membership(cls, self.default, "default")
        self._validate_default_custom_validator(cls, self.default, "default")

    def _validate_default_custom_validator(
        self, cls: type, value: Any, value_name: str
    ) -> None:
        if not self.validator(value):
            raise ValidatorError(
                f"invalid {value_name} value for {cls.__name__}.{self.name}: "
                f"failed custom validator for {self.name}={value!r}"
            )

    def _validate_allowlist(self, cls: type) -> None:
        if self._deferred_type_ctx is not None:
            return
        if self.allowlist is ...:
            return
        if not isinstance(self.allowlist, list):
            raise ValidatorError(
                f"invalid allowlist type of {cls.__name__}.{self.name}: "
                f"expected a list, got {type(self.allowlist)!r} instead"
            )
        for idx, item in enumerate(self.allowlist):
            mismatch_reason = isoftype(
                item,
                self.type,
                self.name,
                path=f"allowlist[{idx}]",
            )
            if mismatch_reason is not None:
                raise ValidatorError(
                    f"invalid allowlist type of {cls.__name__}.{self.name}: "
                    + mismatch_reason
                )
            self._validate_bounds(cls, item, f"allowlist[{idx}]")

    def _validate_default_membership(
        self, cls: type, value: Any, value_name: str
    ) -> None:
        if self.allowlist is not ... and value not in self.allowlist:
            raise ValidatorError(
                f"invalid {value_name} value for {cls.__name__}.{self.name}: "
                f"expected {value_name} in {self.allowlist!r}, "
                f"got {value!r} instead"
            )
        if self.denylist is not ... and value in self.denylist:
            raise ValidatorError(
                f"invalid {value_name} value for {cls.__name__}.{self.name}: "
                f"expected {value_name} not in {self.denylist!r}, "
                f"but got {value!r}"
            )

    def _validate_bounds(self, cls: type, value: Any, value_name: str) -> None:
        expected = self._combined_bounds_expected(value_name)
        if self.lb is not ... and value < self.lb:
            expected_text = (
                f"expected {expected}, "
                if expected is not None
                else f"expected {value_name} ≥ {self.lb!r}, "
            )
            raise ValidatorError(
                f"invalid value for {value_name} of {cls.__name__}.{self.name}: "
                f"{expected_text}got {value!r} (< {self.lb!r}) instead"
            )
        if self.slb is not ... and value <= self.slb:
            expected_text = (
                f"expected {expected}, "
                if expected is not None
                else f"expected {value_name} > {self.slb!r}, "
            )
            raise ValidatorError(
                f"invalid value for {value_name} of {cls.__name__}.{self.name}: "
                f"{expected_text}got {value!r} (≤ {self.slb!r}) instead"
            )
        if self.ub is not ... and value > self.ub:
            expected_text = (
                f"expected {expected}, "
                if expected is not None
                else f"expected {value_name} ≤ {self.ub!r}, "
            )
            raise ValidatorError(
                f"invalid value for {value_name} of {cls.__name__}.{self.name}: "
                f"{expected_text}got {value!r} (> {self.ub!r}) instead"
            )
        if self.sub is not ... and value >= self.sub:
            expected_text = (
                f"expected {expected}, "
                if expected is not None
                else f"expected {value_name} < {self.sub!r}, "
            )
            raise ValidatorError(
                f"invalid value for {value_name} of {cls.__name__}.{self.name}: "
                f"{expected_text}got {value!r} (≥ {self.sub!r}) instead"
            )

    def _combined_bounds_expected(self, name: str) -> str | None:
        lower = self.lb if self.lb is not ... else self.slb
        upper = self.ub if self.ub is not ... else self.sub
        if lower is ... or upper is ...:
            return None
        lower_op = "≤" if self.lb is not ... else "<"
        upper_op = "≤" if self.ub is not ... else "<"
        return f"{lower!r} {lower_op} {name} {upper_op} {upper!r}"

    def __set__(self, instance: object, value: Any) -> None:
        if isinstance(value, self.__class__):
            if self.default is ... and self.default_factory is ...:
                raise TypeError(
                    f"{instance.__class__.__name__}.__init__() missing 1 required "
                    f"argument: {self.name!r}"
                )
            return
        self._ensure_type_resolved()
        mismatch_reason = isoftype(value, self.type, self.name)
        if mismatch_reason is not None:
            raise TypeError(
                f"invalid type for {instance.__class__.__name__}.{self.name}: "
                + mismatch_reason
            )
        if self.allowlist is not ...:
            if value not in self.allowlist:
                raise ValueError(
                    f"invalid value for {instance.__class__.__name__}.{self.name}: "
                    f"expected {self.name} in {self.allowlist!r}, got {value!r} instead"
                )
        if self.denylist is not ...:
            if value in self.denylist:
                raise ValueError(
                    f"invalid value for {instance.__class__.__name__}.{self.name}: "
                    f"expected {self.name} not in {self.denylist!r}, but got {value!r}"
                )
        expected = self._combined_bounds_expected(self.name)
        if self.lb is not ... and value < self.lb:
            expected_text = (
                f"expected {expected}, "
                if expected is not None
                else f"expected {self.name} ≥ {self.lb!r}, "
            )
            raise ValueError(
                f"invalid value for {instance.__class__.__name__}.{self.name}: "
                f"{expected_text}got {value!r} (< {self.lb!r}) instead"
            )
        if self.slb is not ... and value <= self.slb:
            expected_text = (
                f"expected {expected}, "
                if expected is not None
                else f"expected {self.name} > {self.slb!r}, "
            )
            raise ValueError(
                f"invalid value for {instance.__class__.__name__}.{self.name}: "
                f"{expected_text}got {value!r} (≤ {self.slb!r}) instead"
            )
        if self.ub is not ... and value > self.ub:
            expected_text = (
                f"expected {expected}, "
                if expected is not None
                else f"expected {self.name} ≤ {self.ub!r}, "
            )
            raise ValueError(
                f"invalid value for {instance.__class__.__name__}.{self.name}: "
                f"{expected_text}got {value!r} (> {self.ub!r}) instead"
            )
        if self.sub is not ... and value >= self.sub:
            expected_text = (
                f"expected {expected}, "
                if expected is not None
                else f"expected {self.name} < {self.sub!r}, "
            )
            raise ValueError(
                f"invalid value for {instance.__class__.__name__}.{self.name}: "
                f"{expected_text}got {value!r} (≥ {self.sub!r}) instead"
            )
        if not self.validator(value):
            raise ValueError(
                f"invalid value for {instance.__class__.__name__}.{self.name}: "
                f"failed custom validator for {self.name}={value!r}"
            )
        instance.__dict__[self.name] = value

    def __get__(self, instance: object, owner: type) -> Any:
        if not instance:
            return self
        if self.name not in instance.__dict__:
            if self.default_factory is not ...:
                self.__set__(instance, self.default_factory())
            elif self.default is ...:
                raise AttributeError(
                    f"{owner.__name__!r} object has no attribute {self.name!r}"
                )
            else:
                self.__set__(instance, self.default)
        return instance.__dict__[self.name]

    def __delete__(self, instance: object) -> None:
        del instance.__dict__[self.name]


def _resolve_field_type_hint(
    cls: type,
    name: str,
    *,
    localns: dict[str, Any] | None = None,
) -> type:
    if name not in cls.__annotations__:
        return Any

    raw_type_hint = cls.__annotations__[name]
    if not isinstance(raw_type_hint, str):
        return raw_type_hint

    merged_localns = _merge_localns(
        localns,
        _collect_type_checking_names(cls.__module__),
    )

    try:
        resolved_hints = get_type_hints(
            cls,
            globalns=vars(sys.modules[cls.__module__]),
            localns=merged_localns,
            include_extras=True,
        )
    except NameError as exc:
        raise ValidatorError(
            f"failed to resolve annotation for {cls.__name__}.{name}: {raw_type_hint!r}"
        ) from exc
    except Exception as exc:  # pragma: no cover - exact exception depends on annotation
        raise ValidatorError(
            f"failed to resolve annotation for {cls.__name__}.{name}: {raw_type_hint!r}"
        ) from exc

    if name not in resolved_hints:
        raise ValidatorError(
            f"failed to resolve annotation for {cls.__name__}.{name}: {raw_type_hint!r}"
        )

    return resolved_hints[name]


def _get_owner_localns() -> dict[str, Any] | None:
    try:
        frame = sys._getframe(1)
    except ValueError:
        return None
    return frame.f_locals


def _collect_runtime_localns(
    initial_localns: dict[str, Any] | None,
) -> dict[str, Any] | None:
    merged: dict[str, Any] = {}
    if initial_localns is not None:
        merged.update(initial_localns)

    depth = 2
    while True:
        try:
            frame = sys._getframe(depth)
        except ValueError:
            break
        merged.update(frame.f_locals)
        depth += 1

    return merged or None


def _merge_localns(*namespaces: dict[str, Any] | None) -> dict[str, Any] | None:
    merged: dict[str, Any] = {}
    for namespace in namespaces:
        if namespace:
            merged.update(namespace)
    return merged or None


def _collect_type_checking_names(module_name: str) -> dict[str, Any]:
    module = sys.modules.get(module_name)
    if module is None:
        return {}

    module_file = getattr(module, "__file__", None)
    if module_file is None:
        return {}

    try:
        source = Path(module_file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    package = getattr(module, "__package__", None)
    return _TypeCheckingImportCollector(package).collect(source)


class _TypeCheckingImportCollector(NodeVisitor):
    def __init__(self, package: str | None) -> None:
        self.package = package
        self.names: dict[str, Any] = {}

    def collect(self, source: str) -> dict[str, Any]:
        try:
            tree = parse(source)
        except SyntaxError:
            return {}
        self.visit(tree)
        return self.names

    def visit_If(self, node: If) -> None:
        if self._is_type_checking_guard(node.test):
            for stmt in node.body:
                self._consume_type_checking_stmt(stmt)

        self.generic_visit(node)

    @staticmethod
    def _is_type_checking_guard(test: Any) -> bool:
        if isinstance(test, Name):
            return test.id == "TYPE_CHECKING"
        if isinstance(test, Attribute):
            return isinstance(test.value, Name) and test.value.id == "typing" and test.attr == "TYPE_CHECKING"
        return False

    def _consume_type_checking_stmt(self, stmt: Any) -> None:
        if isinstance(stmt, Import):
            for alias in stmt.names:
                try:
                    module = import_module(alias.name)
                except Exception:
                    continue
                self.names[alias.asname or alias.name.split(".")[0]] = module
            return

        if not isinstance(stmt, ImportFrom) or stmt.module is None:
            return

        target_module = "." * stmt.level + stmt.module
        try:
            imported = import_module(target_module, self.package)
        except Exception:
            return

        for alias in stmt.names:
            if alias.name == "*":
                continue
            try:
                symbol = getattr(imported, alias.name)
            except AttributeError:
                continue
            self.names[alias.asname or alias.name] = symbol


def isoftype(
    value: object, type_hint: type, name: str, path: str = ""
) -> Optional[str]:
    """
    Returns a detailed mismatch message when ``value`` does not satisfy ``type_hint``.

    Parameters
    ----------
    value : object
        Value to be checked.
    type_hint : type
        Type hint object.
    name: str
        Variable name.
    path : str, optional
        Human-readable value path used in the error details.

    Returns
    -------
    Optional[str]
        None when the check passes; otherwise a description of the mismatch.

    """
    if type_hint is Any:
        return None

    origin = get_origin(type_hint)
    args = get_args(type_hint)

    if origin is None:
        if isinstance(type_hint, ForwardRef):
            # Unresolved forward references may appear in dynamic annotations
            # (e.g. ``Union[ForwardRef("MyTypedDict"), None]``). At runtime,
            # accept these values instead of failing with a low-signal error.
            return None

        newtype_super = getattr(type_hint, "__supertype__", None)
        if newtype_super is not None:
            return isoftype(value, newtype_super, name, path)

        if is_typeddict(type_hint):
            return _validate_typed_dict(value, type_hint, name, path)

        try:
            if isinstance(value, type_hint):
                return None
        except TypeError:
            pass
        return _format_isoftype_error(
            path, f"{type_hint!r}, got {type(value)!r} instead"
        )

    if origin is Union or origin is UnionType:
        union_errors = [isoftype(value, arg, name, path) for arg in args]
        if any(error is None for error in union_errors):
            return None
        return _format_isoftype_error(
            path,
            f"one of {args}, got {value.__class__!r} instead",
        )

    if origin is Literal:
        if value in args:
            return None
        return _format_isoftype_error(path, f"one of {args!r}, got {value!r} instead")

    if origin is Unpack:
        (unpacked_type,) = args
        return isoftype(value, unpacked_type, name, path)

    if origin is list:
        (elem_type,) = args
        if not isinstance(value, list):
            return _format_isoftype_error(path, f"a list, got {type(value)!r} instead")
        for idx, elem in enumerate(value):
            elem_error = isoftype(elem, elem_type, name, f"{name}[{idx}]")
            if elem_error is not None:
                return elem_error
        return None

    if origin is tuple:
        if len(args) == 2 and args[1] is ...:
            (elem_type, _) = args
            if not isinstance(value, tuple):
                return _format_isoftype_error(
                    path, f"a tuple, got {type(value)!r} instead"
                )
            for idx, elem in enumerate(value):
                elem_error = isoftype(elem, elem_type, name, f"{name}[{idx}]")
                if elem_error is not None:
                    return elem_error
            return None

        if not isinstance(value, tuple) or len(value) != len(args):
            return _format_isoftype_error(
                path,
                f"a tuple with {len(args)} elements, got {type(value)!r} with "
                f"length {len(value) if isinstance(value, tuple) else 'N/A'} instead",
            )
        for idx, (elem, elem_type) in enumerate(zip(value, args)):
            elem_error = isoftype(elem, elem_type, name, f"{name}[{idx}]")
            if elem_error is not None:
                return elem_error
        return None

    if origin is dict:
        key_t, val_t = args
        if not isinstance(value, dict):
            return _format_isoftype_error(path, f"a dict, got {type(value)!r} instead")
        for key, val in value.items():
            key_error = isoftype(key, key_t, name, f"{name}.keys() element {key!r}")
            if key_error is not None:
                return key_error
            val_error = isoftype(val, val_t, name, f"{name}[{key!r}]")
            if val_error is not None:
                return val_error
        return None

    if origin is set:
        (elem_type,) = args
        if not isinstance(value, set):
            return _format_isoftype_error(path, f"a set, got {type(value)!r} instead")
        for elem in value:
            elem_path = f"{path} element {elem!r}" if path else f"element {elem!r}"
            elem_error = isoftype(elem, elem_type, name, elem_path)
            if elem_error is not None:
                return elem_error
        return None

    raise NotImplementedError(f"Unsupported type hint: {type_hint}")


def _format_isoftype_error(path: str, detail: str) -> str:
    if path:
        return f"{path} expected {detail}"
    return f"expected {detail}"


def _validate_typed_dict(
    value: object,
    type_hint: Any,
    name: str,
    path: str,
) -> Optional[str]:
    if not isinstance(value, dict):
        return _format_isoftype_error(path, f"a dict, got {type(value)!r} instead")

    annotations = getattr(type_hint, "__annotations__", {})
    required_keys = set(getattr(type_hint, "__required_keys__", set()))
    optional_keys = set(getattr(type_hint, "__optional_keys__", set()))
    allowed_keys = required_keys | optional_keys | set(annotations)

    missing = sorted(required_keys - set(value))
    if missing:
        keys = ", ".join(repr(k) for k in missing)
        return _format_isoftype_error(path, f"missing required keys: {keys}")

    extra = sorted(set(value) - allowed_keys)
    if extra:
        keys = ", ".join(repr(k) for k in extra)
        return _format_isoftype_error(path, f"unexpected keys: {keys}")

    for key, annotated in annotations.items():
        if key not in value:
            continue
        key_type = _unwrap_required_marker(annotated)
        key_error = isoftype(value[key], key_type, name, f"{name}[{key!r}]")
        if key_error is not None:
            return key_error

    return None


def _unwrap_required_marker(type_hint: Any) -> Any:
    origin = get_origin(type_hint)
    if origin is Required or origin is NotRequired:
        return get_args(type_hint)[0]
    return type_hint


class ValidatorError(RuntimeError): ...
