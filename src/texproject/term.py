"""TODO: write"""
from __future__ import annotations
from pathlib import Path
import shlex
from typing import TYPE_CHECKING

import click

from . import __repo__

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Iterable, Final
    from .template import _FileLinker

REPO_FORMATTED = click.style(__repo__, fg="bright_blue")


class Secret(str):
    """Special string class which is concealed when printed by _MessageFormatter."""


def redact(obj: str):
    """Redact the string if it is a Secret."""
    if isinstance(obj, Secret):
        return "[*****]"
    return str(obj)


class _MessageFormatter:
    """Formatting messages before printing to the terminal."""

    _prefix = {
        "cmd": "$ ",
        "file": "> ",
        "info": "% ",
        "err": "! ",
    }
    _opts = {
        "info": dict(fg="blue"),
        "ok": dict(fg="green"),
        "warn": dict(fg="yellow"),
        "err": dict(fg="red"),
    }

    def _apply_style(self, msg: str, prefix, fmt):
        """Helper to apply the prefix and format styles to the message."""
        return click.style(self._prefix[prefix] + msg, **self._opts[fmt])

    def render(self, template_path: Path, target: Path, overwrite: bool = False):
        """Format for rendering."""
        pref = "file"
        base_str = f" file '{target}' from template at '{template_path}'"
        if overwrite:
            return self._apply_style("Re-render" + base_str, pref, "warn")
        else:
            return self._apply_style("Render" + base_str, pref, "info")

    def link(self, linker: _FileLinker, name: str, target_dir: Path, mode: str):
        """TODO: write"""

        def helper(prop):
            return f"{linker.user_str} '{name}' {prop} directory '{target_dir}'"

        if mode == "overwrite":
            return self._apply_style(f"Replace {helper('in')}", "file", "warn")
        elif mode == "exists":
            return self._apply_style(f"Use existing {helper('in')}", "file", "info")
        elif mode == "new":
            return self._apply_style(f"Copy {helper('to')}", "file", "info")
        elif mode == "fail":
            return self._apply_style(f"Could not import {helper('to')}", "err", "err")
        return ""

    def template_dict(self, target: Path, overwrite: bool = False):
        pref = "file"
        base_str = f" template dictionary in directory '{target}'"
        if overwrite:
            return self._apply_style("Replace" + base_str, pref, "warn")
        else:
            return self._apply_style("Write" + base_str, pref, "info")

    def copy(self, source: Path, target: Path):
        return self._apply_style(f"Copying '{source}' to '{target}'", "file", "info")

    def rename(self, source: Path, target: Path):
        return self._apply_style(f"Rename '{source}' to '{target}'", "file", "info")

    def remove(self, target: Path):
        return self._apply_style(f"Removing file '{target}'", "file", "info")

    def edit(self, file_path: Path):
        return self._apply_style(f"Editing file at '{file_path}'", "info", "ok")

    def cmd(self, cmd_list: Iterable[str]):
        """TODO: write"""
        return self._apply_style(
            f"{shlex.join([redact(cmd) for cmd in cmd_list])}", "cmd", "ok"
        )

    def archive(self, output_path: Path, compression: str):
        return self._apply_style(
            f"Create compressed archive '{output_path}' with compression '{compression}'.",
            "info",
            "ok",
        )

    def info(self, message: str):
        return self._apply_style(message, "info", "info")

    def error(self, message: str):
        return self._apply_style(message, "err", "err")


FORMAT_MESSAGE: Final = _MessageFormatter()
