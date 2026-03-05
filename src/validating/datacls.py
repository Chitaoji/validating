"""
Dataclass helpers for validating.

NOTE: this module is private. All functions and objects are available in the main
`validating` namespace - use that instead.

"""

from dataclasses import Field
from dataclasses import dataclass as _stdlib_dataclass
from functools import partial
from inspect import signature
from typing import Any, Callable

from .attrval import AttrValidator, attr

__all__ = ["dataclass"]


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
    Dataclass decorator compatible with `dataclasses.dataclass`.

    The only behavior difference is that annotated class attributes with direct
    default values (for example `x: int = 1`) are automatically converted to
    `attr(default=1)` before applying `dataclasses.dataclass`.

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


def _promote_defaults_to_attr(cls: type) -> type:
    for name in cls.__annotations__:
        if name not in cls.__dict__:
            continue
        value = cls.__dict__[name]
        if isinstance(value, Field):
            continue
        setattr(cls, name, attr(default=value))
    return cls
