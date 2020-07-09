import click
from pathlib import Path
#  from shutil import make_archive, copytree, copyfile
import shutil

from . import __version__, __repo__
from .template import ProjectTemplate
from .filesystem import (CONFIG, PROJ_PATH, CONFIG_PATH,
        macro_linker, citation_linker, template_linker)

@click.group()
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
        help="create frozen project")
@click.option('-C', 'output',
        default='',
        help='working directory')
def init(template, citation, frozen, output):
    """Initialize a new project in the current directory. The project is
    created using the template with name TEMPLATE and placed in the output
    folder OUTPUT. If the frozen flag is specified, support files are copied
    rather than symlinked.

    The path OUTPUT either must not exist or be an empty folder. Missing
    intermediate directories are automatically constructed."""
    output_path = Path(output)

    # TODO: just write in project files with no overwriting
    #  if output_path.exists():
        #  if not (output_path.is_dir() and len(list(output_path.iterdir())) == 0):
            #  raise click.ClickException(
                #  f"project path '{output_path}' already exists and is not an empty diretory.")
    try:
        proj_gen = ProjectTemplate.load_from_template(
                template,
                citation,
                frozen=frozen)
    except FileExistsError as err:
        raise click.ClickException(err.strerror)
    proj_gen.create_output_folder(output_path)


# add copy .bbl option?
# option to specify out folder or output name?
@cli.command()
@click.option('-C', 'output',
        type=click.Path(),
        default='',
        help="working directory")
@click.option('--compression',
        type=click.Choice([ar[0] for ar in shutil.get_archive_formats()],
            case_sensitive=False),
        show_default=True,
        default=CONFIG['default_compression'],
        help="compression mode")
def export(output, compression):
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
    root_dir = Path(output).resolve()
    temp_dir = root_dir / Path('.texproject', 'tmp', 'output')
    shutil.copytree(root_dir,
            temp_dir,
            copy_function=shutil.copyfile,
            ignore=shutil.ignore_patterns(*CONFIG['export_ignore_patterns']))


    shutil.make_archive(root_dir / root_dir.name,
            compression,
            temp_dir)

    shutil.rmtree(temp_dir)



@cli.command()
@click.option('-C', 'output',
        type=click.Path(),
        default='',
        help="working directory")
@click.option('--force/--no-force',
        default=False,
        help="overwrite project files")
def refresh(output,force):
    """Regenerate project macro and support files.
    Refresh reads information from the project information file .tpr_info and
    uses it to rebuild auto-generated files.

    Symbolic links are always overwritten, but if the project is frozen,
    existing files are unchanged. The force tag overwrites copied macro and
    citation files.
    """
    proj_path = Path(output)
    try:
        proj_info = ProjectTemplate.load_from_project(proj_path)
    except FileNotFoundError:
        if proj_path == Path('.'):
            message = "Current output is not a valid project folder."
        else:
            message = "output '{proj_path}' is not a valid project folder."
        raise click.ClickException(message)

    try:
        proj_info.write_tpr_files(proj_path,force=force)
    except FileNotFoundError as err:
        raise click.ClickException(
                err.strerror + ".")
    except FileExistsError as err:
        raise click.ClickException(
                f"Could not overwrite existing file at '{err.filename}'. Run with `--force` to override.")


@cli.command()
@click.option('--project', 'config_file', flag_value='project',
        default=True)
@click.option('--user', 'config_file', flag_value='user')
@click.option('--system', 'config_file', flag_value='system')
@click.option('-C', 'output',
        type=click.Path(),
        default='',
        help='working directory')
def config(config_file, output):
    """Edit texproject configuration files. This opens the corresponding file
    in your $EDITOR. By default, edit the project configuration file; this
    requires the current directory (or the directory specified by -C) to be
    a texproject directory."""
    out_path = Path(output)
    dispatch = {
            'project': PROJ_PATH.config(out_path),
            'user': CONFIG_PATH.user,
            'system': CONFIG_PATH.system
            }
    click.edit(filename=str(dispatch[config_file]))



# refactor this
# have option positional argument for listing / descriptions?
# write descriptions into packages, and write access methods
@cli.command()
@click.option('--list','-l', 'listfiles',
        type=click.Choice(['C','M','T']),
        multiple=True,
        default=[])
@click.option('--description','-d',
        type=click.Choice(['C','M','T']))
@click.option('--show-all', is_flag=True)
def info(listfiles,description,show_all):
    """Retrieve program and template information."""
    if show_all or len(listfiles) == 0:
        click.echo(f"""
TPR - TexPRoject (version {__version__})
Maintained by Alex Rutar ({click.style(__repo__,fg='bright_blue')}).
MIT License.
""")

    if show_all:
        listfiles = ['C','M','T']

    linker = {'C': citation_linker,
            'M': macro_linker,
            'T': template_linker}

    for code in listfiles:
        ld = linker[code]
        click.echo(f"Directory for {ld.user_str}s: '{ld.dir_path}'.")
        click.echo(f"Available {ld.user_str}s:")
        click.echo("\t"+"\t".join(ld.list_names()) + "\n")


