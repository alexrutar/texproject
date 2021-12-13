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
    type=click.Path(exists=True, file_okay=False, dir_okay=True, writable=True, path_type=Path))

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
@click_proj_dir_option
def build(proj_dir):
    """Compile the current file, using 'latex_compile_command'.
    """
    proj_path = ProjectPath(proj_dir, exists=True)
    compile_tex(proj_path.dir)

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

# add copy .bbl option?
# option to specify out folder or output name?
# TODO: see https://click.palletsprojects.com/en/7.x/commands/#overriding-defaults
@cli.command()
@click_proj_dir_option
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
def export(proj_dir, compression, arxiv):
    """Create a compressed export of an existing project.

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
    create_export(proj_path, compression, arxiv)


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

# TODO: support multi-file tex commands
# .gitignore should include past .sty version?
# what happens if you call refresh? past versions might be broken
# need to build a complete copy of the directory at the given revision
@cli.command()
@click.argument('revision')
@click_proj_dir_option
def diff(revision, proj_dir):
    """Generate file diff.pdf which compares your current project with your
    revision version."""
    proj_path = ProjectPath(proj_dir)

    # find the corresponding main.tex
    git_show = subprocess.run(
            ['git', 'show', f"{revision}:{CONFIG['default_tex_name']}.tex"],
            capture_output=True)
    temp_subdir = proj_path.get_temp_subdir()

    revision_file = temp_subdir / 'diff_rev.tex'
    revision_file.write_text(str(git_show.stdout, 'utf-8'))

    current_file = temp_subdir / 'diff_cur.tex'
    current_file.write_text(proj_path.main.read_text())

    output_tex = temp_subdir / 'diff_out.tex'
    output_pdf = temp_subdir / 'diff_out.pdf'

    latexdiff = subprocess.run(
            ['latexdiff', revision_file.name, current_file.name],
            capture_output=True,
            cwd = temp_subdir)

    output_tex.write_text(
            str(latexdiff.stdout, 'utf-8'))

    proc = subprocess.run(shlex.split(CONFIG['latex_compile_command']) + \
            [str(output_tex)],
            cwd=proj_path.dir,
            capture_output=True)
    (proj_path.log_dir / 'temp.log').write_text(str(proc.stdout,'utf-8'))

    click.echo(f"Diff file written to '.texproject/aux/diff_out.pdf'")

