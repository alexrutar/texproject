import click
from pathlib import Path
import subprocess
import shutil
import shlex

from . import __version__, __repo__
from .template import ProjectTemplate
from .filesystem import (CONFIG, ProjectPath, CONFIG_PATH,
        macro_linker, citation_linker, template_linker)
from .export import create_export

from .error import BasePathError
from .term import REPO_FORMATTED, err_echo


click_proj_dir_option = click.option(
    '-C', 'proj_dir',
    default='.',
    show_default=True,
    help='working directory')

class CatchPathExceptions(click.Group):
    def __call__(self, *args, **kwargs):
        try:
            return self.main(*args, **kwargs)
        except BasePathError as err:
            err_echo(err.message)

@click.group(cls=CatchPathExceptions)
@click.version_option(prog_name="tpr (texproject)")
def cli():
    pass

@cli.command()
@click.argument('template')
@click.option('--citation','-c',
        multiple=True,
        help="include citation file")
@click.option('--frozen/--no-frozen',
        default=False,
        show_default=True,
        help="create frozen project")
@click.option('--git/--no-git',
        default=True,
        show_default=True,
        help="initialize with git repo")
@click_proj_dir_option
def init(template, citation, frozen, proj_dir, git):
    """Initialize a new project in the current directory. The project is
    created using the template with name TEMPLATE and placed in the output
    folder OUTPUT. If the frozen flag is specified, support files are copied
    rather than symlinked.

    The path OUTPUT either must not exist or be an empty folder. Missing
    intermediate directories are automatically constructed."""
    proj_path = ProjectPath(proj_dir, exists=False)

    proj_gen = ProjectTemplate.load_from_template(
            template,
            citation,
            frozen=frozen)

    proj_gen.create_output_folder(proj_path,git=git)
    proj_gen.write_tpr_files(proj_path, write_template=True)

    # initialize git
    if git:
        subprocess.run(
                ['git', 'init'],
                cwd=proj_path.dir,
                capture_output=True) # ? keep or no? depends on verbosity...


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



@cli.command()
@click.option('--project', 'config_file', flag_value='project',
        default=True)
@click.option('--user', 'config_file', flag_value='user')
@click.option('--system', 'config_file', flag_value='system')
@click.option('--force/--no-force',
        default=False,
        help="overwrite project files")
@click.option('--edit/--no-edit',
        default=True,
        help="edit the file")
@click_proj_dir_option
def config(config_file, proj_dir):
    """Edit texproject configuration files. This opens the corresponding file
    in your $EDITOR. By default, edit the project configuration file; this
    requires the current directory (or the directory specified by -C) to be
    a texproject directory.
    """
    proj_path = ProjectPath(proj_dir)

    if edit:
        dispatch = {
                'project': proj_path.config,
                'user': CONFIG_PATH.user,
                'system': CONFIG_PATH.system
                }
        click.edit(filename=str(dispatch[config_file]))

    # force refresh if the project file is edited
    if config_file == 'project':
        proj_info = ProjectTemplate.load_from_project(proj_path)

        try:
            proj_info.write_tpr_files(proj_path,force=force)
        except FileExistsError as err:
            raise click.ClickException(
                    (f"Could not overwrite existing file at '{err.filename}'. "
                        f"Run with `--force` to override."))

        proj_path.clear_temp()



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

