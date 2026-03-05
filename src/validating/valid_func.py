"""
Provides the :func:`validate` decorator for runtime function argument validation.

NOTE: this module is private. All functions and objects are available in the main
:mod:`validating` namespace - use that instead.

"""

import ast
import linecache
import re
from functools import wraps
from inspect import Parameter, Signature, getsourcelines, signature
from textwrap import dedent
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
            converted = _assertion_error_to_value_error(exc, bound.arguments, func)
            if converted is None:
                raise
            raise converted.with_traceback(exc.__traceback__) from None

    setattr(wrapper, _VALIDATE_MARKER, True)

    return wrapper


def _assertion_error_to_value_error(
    exc: AssertionError, arguments: dict[str, Any], func: Callable[..., Any]
) -> ValueError | None:
    if not exc.args:
        message = _assertion_expression_from_traceback(exc, func)
        if message is None:
            return None
        return _value_error_for_assertion_message(message, arguments, func)

    return None


def _assertion_expression_from_traceback(
    exc: AssertionError, func: Callable[..., Any]
) -> str | None:
    traceback = TracebackException.from_exception(exc)
    if not traceback.stack:
        return None

    last_frame = traceback.stack[-1]
    source_line = last_frame.line
    if source_line is None:
        source_line = linecache.getline(last_frame.filename, last_frame.lineno)
    if source_line:
        match = re.match(r"\s*assert\s+(.+?)(?:\s*,\s*.+)?\s*$", source_line.strip())
        if match is not None:
            candidate = _normalize_assertion_expression(match.group(1))
            try:
                ast.parse(candidate, mode="eval")
            except SyntaxError:
                pass
            else:
                return candidate

    expression = _assertion_expression_from_function_source(
        func,
        filename=last_frame.filename,
        lineno=last_frame.lineno,
    )
    if expression is not None:
        return expression

    return None


def _assertion_expression_from_function_source(
    func: Callable[..., Any], filename: str, lineno: int
) -> str | None:
    if getattr(func, "__code__", None) is None:
        return None

    if func.__code__.co_filename != filename:
        return None

    try:
        source_lines, start_line = getsourcelines(func)
    except (OSError, TypeError):
        return None

    source = dedent("".join(source_lines))
    try:
        module = ast.parse(source)
    except SyntaxError:
        return None

    for node in ast.walk(module):
        if not isinstance(node, ast.Assert):
            continue

        node_start_lineno = start_line + node.lineno - 1
        node_end_lineno = start_line + getattr(node, "end_lineno", node.lineno) - 1
        if not (node_start_lineno <= lineno <= node_end_lineno):
            continue

        segment = ast.get_source_segment(source, node.test)
        if segment is None:
            continue

        return _normalize_assertion_expression(segment)

    return None


def _normalize_assertion_expression(expression: str) -> str:
    expression = re.sub(r"\\\s*\n\s*", " ", expression)
    return " ".join(expression.split())


def _value_error_for_assertion_message(
    message: str, arguments: dict[str, Any], func: Callable[..., Any]
) -> ValueError | None:
    if not message:
        return None

    try:
        tree = ast.parse(message, mode="eval")
    except SyntaxError:
        return None

    if not isinstance(tree.body, ast.Compare):
        return None

    names: list[str] = []
    for node in ast.walk(tree.body):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in arguments and node.id not in names:
                names.append(node.id)

    if len(names) != 1:
        return None

    name = names[0]
    return ValueError(
        f"invalid value for argument {name!r} of {func.__name__}: "
        f"expected {message}, got {arguments[name]!r} instead"
    )


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
