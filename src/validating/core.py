"""
Contains the core of validating: attr() , etc.

NOTE: this module is private. All functions and objects are available in the main
`validating` namespace - use that instead.

"""

from typing import Any, Callable, Optional

from .attribute import AttrValidator, ValidatorError, field_with_guard

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
