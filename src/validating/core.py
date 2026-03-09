"""
Contains the core of validating: attr(), dataclass(), validate(), etc.

NOTE: this module is private. All functions and objects are available in the main
:mod:`validating` namespace - use that instead.

"""

from .datacls import dataclass
from .valid_attr import ValidatorError, attr
from .valid_func import validate

__all__ = ["attr", "dataclass", "validate", "ValidatorError"]
