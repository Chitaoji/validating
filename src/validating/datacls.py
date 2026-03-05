"""
Dataclass helpers for validating.

NOTE: this module is private. All functions and objects are available in the main
:mod:`validating` namespace - use that instead.

"""

from dataclasses import Field
from dataclasses import dataclass as _stdlib_dataclass
from functools import partial
from inspect import signature
from typing import Any, Callable, overload

from .valid_attr import AttrValidator, attr
from .valid_func import validate

__all__ = ["dataclass"]


@overload
def dataclass[T](
    cls: type[T] = None,
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
    validate_methods: bool = True,
) -> type[T]: ...
@overload
def dataclass[T](
    cls: None = None,
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
    validate_methods: bool = True,
) -> Callable[[type[T]], type[T]]: ...
def dataclas(
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
    validate_methods: bool = True,
) -> type | Callable[[type], type]:
    """
    Dataclass decorator compatible with ``dataclasses.dataclass``.

    Differences from the stdlib decorator:

    1. Annotated class attributes with direct defaults (for example ``x: int = 1``)
       are automatically promoted to :func:`attr` fields using ``attr(default=1)``.
    2. When ``validate_methods=True``, public methods are wrapped by
       ``validating.validate``.

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
        "validate_methods": validate_methods,
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
    validate_methods: bool,
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

    if validate_methods:
        _decorate_public_methods(dataclass_cls)

    return dataclass_cls


def _decorate_public_methods(cls: type) -> None:
    """Wrap public instance/static/class methods on ``cls`` with :func:`validate`."""

    for name, value in cls.__dict__.items():
        if name.startswith("_"):
            continue

        if isinstance(value, staticmethod):
            setattr(cls, name, staticmethod(validate(value.__func__)))
            continue

        if isinstance(value, classmethod):
            setattr(cls, name, classmethod(validate(value.__func__)))
            continue

        if callable(value):
            setattr(cls, name, validate(value))


def _promote_defaults_to_attr(cls: type) -> type:
    """Convert annotated fields on ``cls`` into :func:`attr` fields."""

    for name in cls.__annotations__:
        if name in cls.__dict__:
            value = cls.__dict__[name]
            if isinstance(value, Field):
                continue
            setattr(cls, name, attr(default=value))
            continue

        setattr(cls, name, attr())
    return cls
