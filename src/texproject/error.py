"""TODO: write"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import NoReturn
    from pathlib import Path

# def assert_never(value: NoReturn) -> NoReturn:
def assert_never(value) -> NoReturn:
    assert False, f"Unhandled value: {value} ({type(value).__name__})"


class AbortRunner(Exception):
    def __init__(self, message: str, stderr: bytes = b""):
        self.stderr = stderr
        self.message = message
        super().__init__(message)


class BasePathError(Exception):
    """TODO: write"""

    def __init__(self, path: Path, message: str = "Error involving path."):
        self.path = path
        self.message = message
        super().__init__(message)
