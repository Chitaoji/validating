"""
Provides a lightweight :func:`attr` descriptor factory that adds runtime validation to
dataclass fields.

NOTE: this module is private. All functions and objects are available in the main
:mod:`validating` namespace - use that instead.

"""

from dataclasses import Field, field
from functools import partialmethod
from types import UnionType
from typing import Any, Callable, Literal, Optional, Union, get_args, get_origin, get_type_hints

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

    def __set_name__(self, cls: type, name: str) -> None:
        _install_slots_guard(cls)
        self.name = name
        self.type = _resolve_field_type_hint(cls, name)
        self._validate_allowlist(cls)
        self._validate_default(cls)

    def _validate_default(self, cls: type) -> None:
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


def _resolve_field_type_hint(cls: type, name: str) -> type:
    if name not in cls.__annotations__:
        return Any

    raw_type_hint = cls.__annotations__[name]
    if not isinstance(raw_type_hint, str):
        return raw_type_hint

    try:
        resolved_hints = get_type_hints(cls, include_extras=True)
    except Exception as exc:  # pragma: no cover - exact exception depends on annotation
        raise ValidatorError(
            f"failed to resolve annotation for {cls.__name__}.{name}: "
            f"{raw_type_hint!r}"
        ) from exc

    if name not in resolved_hints:
        raise ValidatorError(
            f"failed to resolve annotation for {cls.__name__}.{name}: "
            f"{raw_type_hint!r}"
        )

    return resolved_hints[name]


def isoftype(value: object, type_hint: type, name: str, path: str = "") -> Optional[str]:
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
        if isinstance(value, type_hint):
            return None
        return _format_isoftype_error(path, f"{type_hint!r}, got {type(value)!r} instead")

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
                return _format_isoftype_error(path, f"a tuple, got {type(value)!r} instead")
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
            key_error = isoftype(
                key, key_t, name, f"{name}.keys() element {key!r}"
            )
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


class ValidatorError(RuntimeError): ...


def _format_isoftype_error(path: str, detail: str) -> str:
    if path:
        return f"{path} expected {detail}"
    return f"expected {detail}"
