"""TODO: write"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class AbortRunner(Exception):
    def __init__(self, message: str, stderr: bytes = b""):
        self.stderr = stderr
        self.message = message
        super().__init__(message)
