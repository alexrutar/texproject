"""TODO: write"""
from pathlib import Path
import shlex

import click

from . import __repo__
from .error import BasePathError, SubcommandError, LaTeXCompileError

REPO_FORMATTED = click.style(__repo__, fg='bright_blue')

def err_echo(err_inst):
    """TODO: write"""
    def _err_header(string):
        click.secho(f"Error: {string}", err=True, fg='red')

    match err_inst:

        case BasePathError(message=string):
            _err_header(string)

        case LaTeXCompileError(message=string):
            _err_header(string)

        case SubcommandError(message=string, cmd=cmd, stdout=stdout, stderr=stderr):
            _err_header(string)
            click.secho(f"Command:\n$ {shlex.join(cmd)}", err=True)
            click.secho(f"Output:\n{stdout}", err=True)
            click.secho(f"Error output:\n{stderr}", err=True)


def _normalize(path):
    """TODO: write"""
    try:
        return path.relative_to(Path.cwd())
    except ValueError:
        return path

def render_echo(template_path, target):
    """TODO: write"""
    click.secho(
            f"> Render file '{_normalize(target)}' from template at '{template_path}'",
            fg='blue')

def link_echo(linker, name, target):
    """TODO: write"""
    click.secho(
            f"> Copy {linker.user_str} '{name}' to directory '{_normalize(target)}'",
            fg='blue')

def init_echo(dirname):
    """TODO: write"""
    click.secho(
            f"> Initializing project in '{_normalize(dirname)}'",
            fg='blue')

class Secret(str):
    """TODO: write"""

def redact(obj):
    """TODO: write"""
    if isinstance(obj, Secret):
        return '[*****]'
    return str(obj)

def cmd_echo(cmd_list):
    """TODO: write"""
    click.secho(f"$ {shlex.join([redact(cmd) for cmd in cmd_list])}", fg='green')
