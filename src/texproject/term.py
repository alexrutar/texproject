"""TODO: write"""
from __future__ import annotations
from typing import TYPE_CHECKING

from pathlib import Path
import shlex

import click

from . import __repo__

if TYPE_CHECKING:
    from typing import Iterable, Final
    from .filesystem import FileLinker

REPO_FORMATTED = click.style(__repo__, fg="bright_blue")


class Secret(str):
    """Special string class which is concealed when printed by _MessageFormatter."""


def redact(obj: str) -> str:
    """Redact the string if it is a Secret."""
    if isinstance(obj, Secret):
        return "[*****]"
    return obj


class _MessageFormatter:
    """Formatting messages before printing to the terminal."""

    _prefix: Final = {
        "cmd": "$",
        "file": ">",
        "info": "%",
        "err": "!",
        "prompt": "?",
    }
    _fg: Final = {
        "info": "blue",
        "ok": "green",
        "warn": "yellow",
        "err": "red",
    }

    def _apply_style(self, msg: str, prefix: str, fmt: str):
        """Helper to apply the prefix and format styles to the message."""
        return click.style(self._prefix[prefix], fg=self._fg[fmt]) + " " + msg

    def render(self, template_path: Path, target: Path, overwrite: bool = False):
        """Format for rendering."""
        pref = "file"
        base_str = f" file '{target}' from template at '{template_path}'"
        if overwrite:
            return self._apply_style("Re-render" + base_str, pref, "warn")
        else:
            return self._apply_style("Render" + base_str, pref, "ok")

    def prompt(self, prompt: str):
        return self._apply_style(prompt, "prompt", "info")

    def link(self, linker: FileLinker, name: str, target_dir: Path, mode: str):
        """TODO: write"""

        def helper(prop):
            return f"{linker.user_str} '{name}' {prop} directory '{target_dir}'"

        match mode:
            case "overwrite":
                return self._apply_style(f"Replace {helper('in')}", "file", "warn")
            case "exists":
                return self._apply_style(f"Use existing {helper('in')}", "file", "info")
            case "new":
                return self._apply_style(f"Copy {helper('to')}", "file", "info")
            case "fail":
                return self._apply_style(
                    f"Could not import {helper('to')}", "err", "err"
                )
            case _:
                raise NotImplementedError

    def show(self, linker: FileLinker, name: str, mode: str):
        """TODO: write"""
        match mode:
            case "diff":
                return self._apply_style(
                    f"Diff of {linker.user_str} '{name}' with local version",
                    "info",
                    "info",
                )
            case "no-diff":
                return self._apply_style(
                    f"Contents of {linker.user_str} '{name}'", "info", "info"
                )
            case _:
                raise NotImplementedError

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
            f"Create compressed archive '{output_path}' with compression"
            f" '{compression}'.",
            "info",
            "ok",
        )

    def info(self, message: str):
        return self._apply_style(message, "info", "info")

    def error(self, message: str):
        return self._apply_style(message, "err", "err")


FORMAT_MESSAGE: Final = _MessageFormatter()
