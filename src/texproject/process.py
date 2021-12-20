from __future__ import annotations
import os
from pathlib import Path
import subprocess
from typing import TYPE_CHECKING

import keyring

from .error import SubcommandError, LaTeXCompileError
from .term import Secret, cmd_echo

if TYPE_CHECKING:
    from .filesystem import ProjectInfo

def get_github_api_token(proj_info: ProjectInfo):
    """TODO: write"""
    env_token = os.environ.get('API_TOKEN_GITHUB', None)
    if env_token is not None:
        return Secret(env_token)
    try:
        params = proj_info.config.github['keyring']
        user_token = keyring.get_password(params['entry'], params['username'])
        return Secret(user_token)
    except KeyError as err:
        # TODO: have a better error here
        raise err from None

def compile_tex(proj_info: ProjectInfo, outdir:Path=Path.cwd(), output_map=None):
    """TODO: write"""
    if output_map is None:
        output_map = {}
    try:
        subproc_run(proj_info,
                ['latexmk', '-pdf', '-interaction=nonstopmode'] + \
                proj_info.config.process['latexmk_compile_options'] + \
                [f"-outdir={str(outdir)}", proj_info.config.render['default_tex_name'] + '.tex'])
    except SubcommandError as err:
        raise LaTeXCompileError() from err
    finally:
        for filetype, target in output_map.items():
            if target is not None:
                try:
                    (outdir / (proj_info.config.render['default_tex_name'] + filetype)).rename(target)
                except FileNotFoundError:
                    pass


def subproc_run(proj_info, command):
    """TODO: write"""
    if proj_info.verbose:
        cmd_echo(command)

    if not proj_info.dry_run:
        try:
            proc = subprocess.run(
                    command,
                    cwd=proj_info.dir,
                    check=True,
                    capture_output=True)
        except subprocess.CalledProcessError as err:
            raise SubcommandError(err) from err

        if proj_info.verbose:
            print(proc.stdout.decode('ascii'))
