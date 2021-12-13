import click
import subprocess
import shutil
import sys
from pathlib import Path

from . import __version__, __repo__
from .template import ProjectTemplate, PackageLinker
from .filesystem import (CONFIG, ProjectPath, CONFIG_PATH,
        format_linker, macro_linker, citation_linker, template_linker)
from .export import create_export

from .error import BasePathError, BuildError
from .term import REPO_FORMATTED, err_echo

from .latex import compile_tex


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
@click.option(
        '-C', 'proj_dir',
        default='.',
        show_default=True,
        help='working directory',
        type=click.Path(
            exists=True, file_okay=False, dir_okay=True, writable=True, path_type=Path))
@click.pass_context
def cli(ctx, proj_dir):
    ctx.obj = ProjectPath(proj_dir)


@cli.command()
@click.argument('template')
@click.option('--citation','-c',
        multiple=True,
        help="include citation file")
@click.pass_obj
def init(proj_path, template, citation):
    """Initialize a new project in the current directory. The project is
    created using the template with name TEMPLATE and placed in the output
    folder OUTPUT.

    The path OUTPUT either must not exist or be an empty folder. Missing
    intermediate directories are automatically constructed."""
    proj_path.validate(exists=False)

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
@click.pass_obj
def config(proj_path, config_file):
    """Edit texproject configuration files. This opens the corresponding file
    in your $EDITOR. By default, edit the project configuration file; this
    requires the current directory (or the directory specified by -C) to be
    a texproject directory.

    Note that this command does not replace existing macro files. See the
    `tpr import` command for this functionality.
    """
    match config_file:
        case 'local':
            proj_path.validate(exists=True)

            click.edit(filename=str(proj_path.config))

            proj_info = ProjectTemplate.load_from_project(proj_path)
            proj_info.write_tpr_files(proj_path)

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
@click.pass_obj
def import_(proj_path, macro, citation, format, path):
    """Import macro, citation, and format files.
    Warning: this command replaces existing files.
    """
    proj_path.validate(exists=True)

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
@click.pass_obj
def build(proj_path, force, output):
    """Compile the current file, using 'latex_compile_command'.
    """
    proj_path.validate(exists=True)
    if output is not None and output.exists() and not force:
        raise BasePathError(output, "Output file already exists! Run with '-f' to overwrite")
    else:
        output_map = {'.pdf': output} if output is not None else {}
        with proj_path.temp_subpath() as build_dir:
            build_dir.mkdir()
            compile_tex(proj_path.dir, outdir=build_dir, output_map=output_map)


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
@click.pass_obj
def export(proj_path, compression, arxiv, force, output):
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
    proj_path.validate(exists=True)
    if output.exists() and not force:
        raise BasePathError(output, "Output file already exists! Run with '-f' to overwrite")
    else:
        create_export(proj_path, compression, output, arxiv=arxiv)


@cli.command()
@click.pass_obj
def clean(proj_path):
    """Cleans the project directory.
    """
    proj_path.validate(exists=True)
    proj_path.clear_temp()


# TODO: create git subcommand, with init sub sub-command
# and other convenient sub sub-commands (maybe some sort of incremental tagging would be
# convenient?)
@cli.command()
@click.option('--gh/--no-gh',
        default=True,
        show_default=True,
        help="automatically sync with github")
@click.pass_obj
def git_init(proj_path, gh):
    """Initialize the git repository."""
    proj_path.validate(exists=True)

    proj_gen = ProjectTemplate.load_from_project(proj_path)

    proj_gen.write_git_files(proj_path, gh=gh)

    # initialize repo
    subprocess.run(
            ['git', 'init'],
            cwd=proj_path.dir,
            capture_output=True) # ? keep or no? depends on verbosity...

@cli.command()
@click.option('--repo-name', 'repo_name',
        prompt='Repository name',
        type=str)
@click.option('--repo-description', 'repo_desc',
        prompt='Repository description',
        type=str)
@click.option('--repo-visiblity', 'vis',
        prompt='Repository visibility',
        type=click.Choice(['public', 'private']),
        default='private')
@click.pass_obj
def it(proj_path, repo_name, repo_desc, vis):
    proj_path.validate(exists=True)
    proj_gen = ProjectTemplate.load_from_project(proj_path)
    # proj_gen.user_dict is the user configuration file

    print(repo_name, repo_desc,vis)



@cli.command()
@click.argument('res_class',
        type=click.Choice(['citation', 'macro', 'format', 'template']))
def list(res_class):
    """Retrieve program and template information."""

    linker_map = {
            'citation': citation_linker,
            'macro':macro_linker,
            'format': format_linker,
            'template': template_linker
            }

    click.echo("\n".join(linker_map[res_class].list_names()))

@cli.command()
@click.pass_obj
def migrate_yaml(proj_path):
    import yaml
    import pytomlpp
    proj_path.validate(exists=True)
    yaml_path = proj_path.data_dir / 'tpr_info.yaml'
    if yaml_path.exists():
        proj_path.config.write_text(
                pytomlpp.dumps(
                    yaml.safe_load(
                        yaml_path.read_text())))
        yaml_path.unlink()

# TODO: refactor this
# - have option positional argument for listing / descriptions?
# - write descriptions into packages, and write access methods
@cli.command()
@click.argument('res_class',
        type=click.Choice(['citation', 'macro', 'format', 'template', 'repo']))
def info(res_class):
    """Retrieve program and template information."""
    if res_class == 'repo':
        click.echo(f"""TPR - TexPRoject (version {__version__})
Maintained by Alex Rutar ({REPO_FORMATTED}).
MIT License.""")
