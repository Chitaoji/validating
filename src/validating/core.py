"""
Contains the core of validating: attr() , etc.

NOTE: this module is private. All functions and objects are available in the main
`validating` namespace - use that instead.

"""

from dataclasses import Field, dataclass as _stdlib_dataclass
from functools import partial
from inspect import signature
from typing import Any, Callable, Optional

from .attrval import AttrValidator, ValidatorError, field_with_guard

__all__ = ["attr", "dataclass"]


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
    Returns an attribute with validator. This works well with dataclasses.

    Only for dict classes.

    Parameters
    ----------
    default : Any, optional
        Default value, by default Ellipsis.
    default_factory : Callable[[], Any], optional
        Callable used to generate a default value lazily, by default Ellipsis.
    allowlist : list, optional
        Allowed values, by default Ellipsis.
    denylist : list, optional
        Forbidden values, by default Ellipsis.
    lb : Any, optional
        Lower bound (inclusive), by default Ellipsis.
    slb : Any, optional
        Strict lower bound (exclusive), by default Ellipsis.
    ub : Any, optional
        Upper bound (inclusive), by default Ellipsis.
    sub : Any, optional
        Strict upper bound (exclusive), by default Ellipsis.
    validator : Callable[[Any], bool], optional
        Custom validator function, by default Ellipsis.
    init : bool, optional
        Whether this field should be included as a generated `__init__()`
        parameter when used with `dataclasses.dataclass`, by default True.
    repr : bool, optional
        Whether this field should be included in the generated `__repr__()`
        output, by default True.
    hash : Optional[bool], optional
        Whether this field should be included in generated `__hash__()`.
        Follows `dataclasses.field` behavior where `None` defers to
        `compare`, by default None.
    compare : bool, optional
        Whether this field should be used in generated comparison methods,
        by default True.
    kw_only : bool, optional
        Whether this field should be marked as keyword-only for
        `dataclasses.dataclass` generated `__init__()`, by default False.

    Returns
    -------
    Any
        Attribute with validator.

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
    return field_with_guard(
        default=descriptor,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        kw_only=kw_only,
    )


def _promote_defaults_to_attr(cls: type) -> type:
    for name in cls.__annotations__:
        if name not in cls.__dict__:
            continue
        value = cls.__dict__[name]
        if isinstance(value, Field):
            continue
        setattr(cls, name, attr(default=value))
    return cls


def _apply_validating_dataclass(
    target_cls: type,
    *,
    init: bool,
    repr: bool,
    eq: bool,
    order: bool,
    unsafe_hash: bool,
    frozen: bool,
    match_args: bool,
    kw_only: bool,
    slots: bool,
    weakref_slot: bool,
) -> type:
    promoted_cls = _promote_defaults_to_attr(target_cls)
    dataclass_kwargs: dict[str, Any] = {
        "init": init,
        "repr": repr,
        "eq": eq,
        "order": order,
        "unsafe_hash": unsafe_hash,
        "frozen": frozen,
        "match_args": match_args,
        "kw_only": kw_only,
        "slots": slots,
        "weakref_slot": weakref_slot,
    }
    supported = signature(_stdlib_dataclass).parameters
    dataclass_kwargs = {
        key: value for key, value in dataclass_kwargs.items() if key in supported
    }
    dataclass_cls = _stdlib_dataclass(promoted_cls, **dataclass_kwargs)
    for name in getattr(dataclass_cls, "__annotations__", {}):
        value = getattr(dataclass_cls, name, None)
        if isinstance(value, AttrValidator) and not hasattr(value, "name"):
            value.__set_name__(dataclass_cls, name)
    return dataclass_cls


def dataclass(
    cls: type | None = None,
    /,
    *,
    init: bool = True,
    repr: bool = True,
    eq: bool = True,
    order: bool = False,
    unsafe_hash: bool = False,
    frozen: bool = False,
    match_args: bool = True,
    kw_only: bool = False,
    slots: bool = False,
    weakref_slot: bool = False,
) -> type | Callable[[type], type]:
    """
    Dataclass decorator compatible with ``dataclasses.dataclass``.

    The only behavior difference is that annotated class attributes with direct
    default values (for example ``x: int = 1``) are automatically converted to
    ``attr(default=1)`` before applying ``dataclasses.dataclass``.
    """
    apply_kwargs = {
        "init": init,
        "repr": repr,
        "eq": eq,
        "order": order,
        "unsafe_hash": unsafe_hash,
        "frozen": frozen,
        "match_args": match_args,
        "kw_only": kw_only,
        "slots": slots,
        "weakref_slot": weakref_slot,
    }
    if cls is not None:
        return _apply_validating_dataclass(cls, **apply_kwargs)

    return partial(_apply_validating_dataclass, **apply_kwargs)
