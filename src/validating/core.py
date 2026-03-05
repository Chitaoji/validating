"""
Contains the core of validating: attr(), dataclass(), etc.

NOTE: this module is private. All functions and objects are available in the main
`validating` namespace - use that instead.

"""

from .attrval import ValidatorError, attr
from .datacls import dataclass

__all__ = ["attr", "dataclass", "ValidatorError"]
