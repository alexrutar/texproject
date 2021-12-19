import subprocess
from pathlib import Path
import os
import keyring

from .error import SubcommandError, LaTeXCompileError
from .term import Secret, cmd_echo

def get_github_api_token(proj_info):
    env_token = os.environ.get('API_TOKEN_GITHUB', None)
    if env_token is not None:
        return Secret(env_token)
    else:
        try:
            params = proj_info.config.github['keyring']
            user_token = keyring.get_password(params['entry'], params['username'])
            return Secret(user_token)
        except KeyError as e:
            raise e

def compile_tex(proj_info, outdir=Path.cwd(), output_map={}):
    try:
        subproc_run(proj_info,
                ['latexmk', '-pdf', '-interaction=nonstopmode'] + \
                proj_info.config.process['latexmk_compile_options'] + \
                [f"-outdir={str(outdir)}", proj_info.config.render['default_tex_name'] + '.tex'])
    except SubcommandError:
        raise LaTeXCompileError()
    finally:
        for filetype, target in output_map.items():
            if target is not None:
                try:
                    (outdir / (proj_info.config.render['default_tex_name'] + filetype)).rename(target)
                except FileNotFoundError:
                    pass


def subproc_run(proj_info, command):
    if proj_info.verbose:
        cmd_echo(command)

    if not proj_info.dry_run:
        try:
            proc = subprocess.run(
                    command,
                    cwd=proj_info.dir,
                    check=True,
                    capture_output=True)
        except subprocess.CalledProcessError as e:
            raise SubcommandError(e) from e

        if proj_info.verbose:
            print(proc.stdout.decode('ascii'))
