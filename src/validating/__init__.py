"""Public package interface for :mod:`validating`.

This package re-exports the main runtime-validation APIs:

- :func:`attr` for validated dataclass-style fields.
- :func:`dataclass` as an enhanced wrapper around ``dataclasses.dataclass``.
- :func:`validate` for function argument validation based on annotations.
- :class:`ValidatorError` for definition-time configuration errors.

Typical usage:

.. code-block:: python

    from validating import attr, dataclass, validate, ValidatorError

"""

from . import core
from .core import *

__all__: list[str] = []
__all__.extend(core.__all__)
