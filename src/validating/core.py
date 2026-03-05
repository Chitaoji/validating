"""
Contains the core of validating: attr(), dataclass(), etc.

NOTE: this module is private. All functions and objects are available in the main
`validating` namespace - use that instead.

"""

from .datacls import dataclass
from .valid_attr import ValidatorError, attr

__all__ = ["attr", "dataclass", "ValidatorError"]
