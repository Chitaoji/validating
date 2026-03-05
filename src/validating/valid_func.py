"""
Provides the :func:`validate` decorator for runtime function argument validation.

NOTE: this module is private. All functions and objects are available in the main
:mod:`validating` namespace - use that instead.

"""

from functools import wraps
from inspect import Parameter, Signature, signature
import linecache
import re
from traceback import TracebackException
from typing import Any, Callable

from .valid_attr import isoftype

__all__ = ["validate"]

_VALIDATE_MARKER = "__validating_is_validate_wrapped__"


def validate[T](func: T) -> T:
    """
    Decorator that validates function arguments against type annotations.

    Parameters
    ----------
    func : Callable[..., Any]
        Target function.

    Returns
    -------
    Callable[..., Any]
        Wrapped function that validates all provided arguments at call time.

    """
    if not callable(func):
        raise TypeError(f"validate() expected a callable, got {type(func)!r} instead")

    if getattr(func, _VALIDATE_MARKER, False):
        return func

    sig = signature(func)

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = sig.bind(*args, **kwargs)
        _validate_bound_arguments(func, sig, bound.arguments)
        try:
            return func(*args, **kwargs)
        except AssertionError as exc:
            converted = _assertion_error_to_value_error(exc, bound.arguments)
            if converted is None:
                raise
            raise converted from exc

    setattr(wrapper, _VALIDATE_MARKER, True)

    return wrapper


def _assertion_error_to_value_error(
    exc: AssertionError, arguments: dict[str, Any]
) -> ValueError | None:
    if not exc.args:
        message = _assertion_expression_from_traceback(exc)
        if message is None:
            return None
        return _value_error_for_assertion_message(message, arguments, fallback=exc.args)

    return None


def _assertion_expression_from_traceback(exc: AssertionError) -> str | None:
    traceback = TracebackException.from_exception(exc)
    if not traceback.stack:
        return None

    last_frame = traceback.stack[-1]
    source_line = last_frame.line
    if source_line is None:
        source_line = linecache.getline(last_frame.filename, last_frame.lineno)
    if not source_line:
        return None

    match = re.match(r"\s*assert\s+(.+?)(?:\s*,\s*.+)?\s*$", source_line.strip())
    if match is None:
        return None

    return match.group(1)


def _value_error_for_assertion_message(
    message: str, arguments: dict[str, Any], fallback: tuple[Any, ...]
) -> ValueError | None:
    if not message:
        return None

    match = re.match(r"\s*([A-Za-z_]\w*)\s*(==|!=|>=|<=|>|<).+", message)
    if match is None:
        return None

    name = match.group(1)
    if name not in arguments:
        return None

    return ValueError(f"expected {message}, got {arguments[name]!r} instead")


def _validate_bound_arguments(
    func: Callable[..., Any],
    sig: Signature,
    arguments: dict[str, Any],
) -> None:
    for name, value in arguments.items():
        param = sig.parameters[name]
        annotation = param.annotation
        if annotation is Signature.empty:
            continue

        if param.kind is Parameter.VAR_POSITIONAL:
            for idx, item in enumerate(value):
                mismatch_reason = isoftype(
                    item,
                    annotation,
                    name,
                    path=f"{name}[{idx}] expected",
                )
                if mismatch_reason is not None:
                    raise TypeError(
                        f"invalid type for argument {name!r} of {func.__name__}: "
                        + mismatch_reason
                    )
            continue

        if param.kind is Parameter.VAR_KEYWORD:
            for key, item in value.items():
                mismatch_reason = isoftype(
                    item,
                    annotation,
                    name,
                    path=f"{name}[{key!r}] expected",
                )
                if mismatch_reason is not None:
                    raise TypeError(
                        f"invalid type for argument {name!r} of {func.__name__}: "
                        + mismatch_reason
                    )
            continue

        mismatch_reason = isoftype(value, annotation, name, path="expected")
        if mismatch_reason is not None:
            raise TypeError(
                f"invalid type for argument {name!r} of {func.__name__}: "
                + mismatch_reason
            )
