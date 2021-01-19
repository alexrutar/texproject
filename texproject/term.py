from . import __repo__
import click

REPO_FORMATTED = click.style(__repo__, fg='bright_blue')
def err_echo(string):
    click.secho(f"Error: {string}", err=True, fg='red')
