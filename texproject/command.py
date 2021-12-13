import click
import subprocess
import shutil
import shlex
import sys
from pathlib import Path

from . import __version__, __repo__
from .template import ProjectTemplate, PackageLinker
from .filesystem import (CONFIG, ProjectPath, CONFIG_PATH,
        macro_linker, citation_linker, template_linker)
from .export import create_export

from .error import BasePathError, BuildError
from .term import REPO_FORMATTED, err_echo

from .latex import compile_tex


click_proj_dir_option = click.option(
        '-C', 'proj_dir',
        default='.',
        show_default=True,
        help='working directory',
        type=click.Path(
            exists=True, file_okay=False, dir_okay=True, writable=True, path_type=Path))

click_output_directory_option = click.option(
        '-D', 'output_dir',
        default='.',
        help="output directory",
        show_default=True,
        type=click.Path(
            exists=True, file_okay=False, dir_okay=True, writable=True, path_type=Path))

click_output_file_option = click.option(
            '-O', 'output_file',
            help="specify output filename",
            type=click.Path(
                exists=False, writable=True, path_type=Path))

class CatchInternalExceptions(click.Group):
    def __call__(self, *args, **kwargs):
        try:
            return self.main(*args, **kwargs)

        except BasePathError as err:
            err_echo(err.message)
            sys.exit(1)

        except BuildError as err:
            err_echo(err.message + " Here is the build error output:\n")
            click.echo(err.stderr, err=True)
            sys.exit(1)


@click.group(cls=CatchInternalExceptions)
@click.version_option(prog_name="tpr (texproject)")
def cli():
    pass


@cli.command()
@click.argument('template')
@click.option('--citation','-c',
        multiple=True,
        help="include citation file")
@click_proj_dir_option
def init(template, citation, proj_dir):
    """Initialize a new project in the current directory. The project is
    created using the template with name TEMPLATE and placed in the output
    folder OUTPUT.

    The path OUTPUT either must not exist or be an empty folder. Missing
    intermediate directories are automatically constructed."""
    proj_path = ProjectPath(proj_dir, exists=False)

    proj_gen = ProjectTemplate.load_from_template(
            template,
            citation)

    proj_gen.create_output_folder(proj_path)
    proj_gen.write_tpr_files(proj_path, write_template=True)


@cli.command()
@click.option('--local', 'config_file', flag_value='local', default=True,
        help="Edit local project configuration.")
@click.option('--user', 'config_file', flag_value='user',
        help="Edit user information.")
@click.option('--system', 'config_file', flag_value='system',
        help="Edit global system configuration.")
@click_proj_dir_option
def config(config_file, proj_dir):
    """Edit texproject configuration files. This opens the corresponding file
    in your $EDITOR. By default, edit the project configuration file; this
    requires the current directory (or the directory specified by -C) to be
    a texproject directory.

    Note that this command does not replace existing macro files. See the
    `tpr import` command for this functionality.
    """
    match config_file:
        case 'local':
            proj_path = ProjectPath(proj_dir, exists=True)
            click.edit(filename=str(proj_path.config))
            proj_info = ProjectTemplate.load_from_project(proj_path)

            proj_info.write_tpr_files(proj_path)

            proj_path.clear_temp()

        case 'user':
            click.edit(filename=str(CONFIG_PATH.user))

        case 'system':
            click.edit(filename=str(CONFIG_PATH.system))


@cli.command('import')
@click.option('--macro', multiple=True,
        help="macro file")
@click.option('--citation', multiple=True,
        help="citation file")
@click.option('--format', default=None,
        help="format file")
@click.option('--path/--no-path', default=False,
        help="files given as absolute paths")
@click_proj_dir_option
def import_(macro, citation, format, path, proj_dir):
    """Import macro, citation, and format files.
    Warning: this command replaces existing files.
    """
    proj_path = ProjectPath(proj_dir, exists=True)
    linker = PackageLinker(proj_path, force=True, is_path=path)
    linker.link_macros(macro)
    linker.link_citations(citation)
    linker.link_format(format)


@cli.command()
@click.option('--force/--no-force','-f/-F', default=False,
        help="overwrite files")
@click.option(
        '-O', '--output',
        'output',
        help="specify name for output .pdf",
        type=click.Path(
            exists=False, writable=True, path_type=Path))
@click_proj_dir_option
def build(force, output, proj_dir):
    """Compile the current file, using 'latex_compile_command'.
    """
    proj_path = ProjectPath(proj_dir, exists=True)
    if output is not None and output.exists() and not force:
        raise BasePathError(output, "Output file already exists! Run with '-f' to overwrite")
    else:
        output_map = {'.pdf': output} if output is not None else {}
        with proj_path.temp_subpath() as build_dir:
            build_dir.mkdir()
            compile_tex(proj_path.dir, outdir=build_dir, output_map=output_map)


@cli.command()
@click_proj_dir_option
def clean(proj_dir):
    """Cleans the project directory.
    """
    proj_path = ProjectPath(proj_dir, exists=True)
    proj_path.clear_temp()


@cli.command()
@click.option('--compression',
        type=click.Choice([ar[0] for ar in shutil.get_archive_formats()],
            case_sensitive=False),
        show_default=True,
        default=CONFIG['default_compression'],
        help="compression mode")
@click.option('--arxiv/--no-arxiv',
        default=False,
        show_default=True,
        help="format for arXiv")
@click.option('--force/--no-force','-f/-F', default=False,
        help="overwrite files")
@click.argument('output',
        type=click.Path(exists=False, writable=True, path_type=Path))
@click_proj_dir_option
def export(compression, arxiv, force, output, proj_dir):
    """Create a compressed export with name OUTPUT.

    \b
    Compression modes:
     bztar: bzip2'ed tar-file
     gztar: gzip'ed tar-file
     tar: uncompressed tar-file
     xztar: xz'ed tar-file
     zip: ZIP file

    Note that not all compression modes may be available on your system.
    """
    proj_path = ProjectPath(proj_dir)
    if output.exists() and not force:
        raise BasePathError(output, "Output file already exists! Run with '-f' to overwrite")
    else:
        create_export(proj_path, compression, output, arxiv=arxiv)


# TODO: create git subcommand, with init sub sub-command
# and other convenient sub sub-commands (maybe some sort of incremental tagging would be
# convenient?)
@cli.command()
@click.option('--gh/--no-gh',
        default=True,
        show_default=True,
        help="automatically sync with github")
@click_proj_dir_option
def git_init(gh, proj_dir):
    """Initialize the git repository."""
    proj_path = ProjectPath(proj_dir, exists=True)

    proj_gen = ProjectTemplate.load_from_project(proj_path)

    proj_gen.write_git_files(proj_path)
    subprocess.run(
            ['git', 'init'],
            cwd=proj_path.dir,
            capture_output=True) # ? keep or no? depends on verbosity...
    if gh:
        pass


# TODO: refactor this
# - have option positional argument for listing / descriptions?
# - write descriptions into packages, and write access methods
@cli.command()
@click.option('--list','-l', 'listfiles',
        type=click.Choice(['C','M','T']))
@click.option('--description','-d',
        type=click.Choice(['C','M','T']))
@click.option('--show-all', is_flag=True)
def info(listfiles,description,show_all):
    """Retrieve program and template information."""
    if show_all or listfiles is None:
        click.echo(f"""
TPR - TexPRoject (version {__version__})
Maintained by Alex Rutar ({REPO_FORMATTED}).
MIT License.""")

    if show_all:
        listfiles = ['C','M','T']
    elif listfiles is None:
        listfiles = []
    else:
        listfiles = [listfiles]

    linker = {'C': citation_linker,
            'M': macro_linker,
            'T': template_linker}

    for code in listfiles:
        ld = linker[code]
        if show_all:
            click.echo(f"\nDirectory for {ld.user_str}s: '{ld.dir_path}'.")
            click.echo(f"Available {ld.user_str}s:")
        click.echo(" " + "\t".join(ld.list_names()))
