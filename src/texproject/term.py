"""TODO: write"""
from __future__ import annotations
from pathlib import Path
import shlex
from typing import TYPE_CHECKING

import click

from . import __repo__
from .error import BasePathError, SubcommandError, LaTeXCompileError

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Iterable, Literal
    from .filesystem import _FileLinker

REPO_FORMATTED = click.style(__repo__, fg="bright_blue")


def _normalize(path: Path) -> str:
    """TODO: write"""
    return str(path)
    # return click.format_filename(path, shorten=True)


class VerboseEcho:
    def __init__(self, verbose: bool):
        """TODO: write"""
        self.verbose = verbose
        self._prefix = {
            "cmd": "$ ",
            "file": "> ",
            "err": "! ",
        }
        # should remove fail and print err to stdout?
        self._opts = {
            "info": dict(fg="blue", err=False),
            "ok": dict(fg="green", err=False),
            "warn": dict(fg="yellow", err=False),
            "err": dict(fg="red", err=False),
            "fail": dict(fg="red", err=True),
        }

    def _echo(
        self,
        msg: str,
        prefix: Literal["cmd", "file", "err"],
        fmt: Literal["info", "ok", "warn", "err", "fail"],
    ):
        # when fail, always print to stdout?
        if self.verbose:
            click.secho(self._prefix[prefix] + msg, **self._opts[fmt])

    def _echo_traceback(self, msg: str):
        click.echo(msg, err=True)

    def binary(self, msg):
        click.echo(msg.decode("ascii"))

    def err(self, err_inst: Exception) -> None:
        """TODO: write"""

        match err_inst:
            case BasePathError(message=string):
                self._echo(string, "err", "fail")

            case LaTeXCompileError(message=string):
                self._echo(string, "err", "fail")

            case SubcommandError(message=string, cmd=cmd, stdout=stdout, stderr=stderr):
                self._echo(string, "err", "fail")
                self._echo_traceback(f"Command:\n$ {shlex.join(cmd)}")
                self._echo_traceback(f"Output:\n{stdout}")
                self._echo_traceback(f"Error output:\n{stderr}")

    def rm(self, target: Path):
        """TODO: write"""
        self._echo(f"Removing path '{_normalize(target)}'.", "file", "warn")

    def write_template(self, target: Path, overwrite: bool = False):
        if overwrite:
            self._echo(
                f"Replace template dictionary in directory '{_normalize(target)}'",
                "file",
                "warn",
            )
        else:
            self._echo(
                f"Write template dictionary to directory '{_normalize(target)}'",
                "file",
                "info",
            )

    def render(self, template_path: Path, target: Path, overwrite: bool = False):
        """TODO: write"""
        if overwrite:
            self._echo(
                f"Re-render file '{_normalize(target)}' from template at '{template_path}'",
                "file",
                "warn",
            )
        else:
            self._echo(
                f"Render file '{_normalize(target)}' from template at '{template_path}'",
                "file",
                "info",
            )

    def link(self, linker: _FileLinker, name: str, target: Path, mode: str):
        """TODO: write"""

        def helper(prop):
            return f"{linker.user_str} '{name}' {prop} directory '{_normalize(target)}'"

        if mode == "overwrite":
            self._echo(f"Replace {helper('in')}", "file", "warn")
        elif mode == "exists":
            self._echo(f"Use existing {helper('in')}", "file", "info")
        elif mode == "new":
            self._echo(f"Copy {helper('to')}", "file", "info")
        elif mode == "fail":
            self._echo(f"Could not import {helper('to')}", "err", "err")

    def init(self, dirname: Path):
        """TODO: write"""
        self._echo(f"Initializing project in '{_normalize(dirname)}'", "file", "info")

    def cmd(self, cmd_list: Iterable[str]):
        """TODO: write"""
        self._echo(f"$ {shlex.join([redact(cmd) for cmd in cmd_list])}", "cmd", "ok")


class _MessageFormatter:
    def __init__(self):
        """TODO: write"""
        self._prefix = {
            "cmd": "$ ",
            "file": "> ",
            "edit": "% ",
            "err": "! ",
        }
        # should remove fail and print err to stdout?
        self._opts = {
            "info": dict(fg="blue"),
            "ok": dict(fg="green"),
            "warn": dict(fg="yellow"),
            "err": dict(fg="red"),
        }

    def _apply_style(self, msg: str, prefix, fmt):
        return click.style(self._prefix[prefix] + msg, **self._opts[fmt])

    def render(self, template_path: Path, target: Path, overwrite: bool = False):
        """TODO: write"""
        pref = "file"
        base_str = f" file '{_normalize(target)}' from template at '{template_path}'"
        if overwrite:
            return self._apply_style("Re-render" + base_str, pref, "warn")
        else:
            return self._apply_style("Render" + base_str, pref, "info")

    def link(self, linker: _FileLinker, name: str, target_dir: Path, mode: str):
        """TODO: write"""

        def helper(prop):
            return f"{linker.user_str} '{name}' {prop} directory '{_normalize(target_dir)}'"

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
        base_str = f" template dictionary in directory '{_normalize(target)}'"
        if overwrite:
            return self._apply_style("Replace" + base_str, pref, "warn")
        else:
            return self._apply_style("Write" + base_str, pref, "info")

    def copy(self, source: Path, target: Path):
        return self._apply_style(f"Copying '{source}' to '{target}'", "file", "info")

    def edit(self, file_path: Path):
        return self._apply_style(f"Editing file at '{file_path}'", "edit", "ok")

    def cmd(self, cmd_list: Iterable[str]):
        """TODO: write"""
        return self._apply_style(
            f"{shlex.join([redact(cmd) for cmd in cmd_list])}", "cmd", "ok"
        )

    def archive(self, output_path: Path, compression: str):
        return self._apply_style(
            f"Create compressed archive '{output_path}' with compression '{compression}'.",
            "edit",
            "ok",
        )

    def info(self, message: str):
        return self._apply_style(message, "edit", "ok")

    def error(self, message: str):
        return self._apply_style(message, "err", "err")


FORMAT_MESSAGE = _MessageFormatter()


class Secret(str):
    """TODO: write"""


def redact(obj: str):
    """TODO: write"""
    if isinstance(obj, Secret):
        return "[*****]"
    return str(obj)
