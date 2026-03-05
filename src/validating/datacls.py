"""
Compatibility re-export for dataclass helper.

NOTE: this module is private. All functions and objects are available in the main
`validating` namespace - use that instead.
"""

from .core import dataclass

__all__ = ["dataclass"]
