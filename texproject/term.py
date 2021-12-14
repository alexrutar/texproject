from . import __repo__
import subprocess
import shlex
import os
import click

REPO_FORMATTED = click.style(__repo__, fg='bright_blue')
def err_echo(string):
    click.secho(f"Error: {string}", err=True, fg='red')

def get_github_api_token(user_dict):
    env_token = os.environ.get('API_TOKEN_GITHUB', None)

    proc = subprocess.run(
            shlex.split(user_dict['github']['archive']['github_api_token_command']),
            capture_output=True,
            check=True)
    user_token = proc.stdout.decode('ascii')[:-1]

    if env_token is not None:
        return env_token
    else:
        return user_token

def subproc_run(command, cwd, check=True, verbose=False, conceal=False):
    if verbose and not conceal:
        click.secho(f"$ {shlex.join(command)}", fg='green')
    elif verbose and conceal:
        click.secho(f"$ # command concealed", fg='green')
    proc = subprocess.run(
            command,
            cwd=cwd,
            check=check,
            capture_output=True)
    if verbose:
        print(proc.stdout.decode('ascii'))
