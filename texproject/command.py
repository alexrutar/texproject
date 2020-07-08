import click
from pathlib import Path
import zipfile

from . import __version__, __repo__
from .template import ProjectTemplate
from .filesystem import (load_proj_dict, TPR_INFO_FILENAME, CONFIG,
        macro_linker, citation_linker, template_linker)

def check_valid_project(proj_path):
    if not (proj_path / TPR_INFO_FILENAME).exists():
        if proj_path == Path('.'):
            message = "Current directory is not a valid project folder."
        else:
            message = "Directory '{proj_path}' is not a valid project folder."
        raise click.ClickException(message)

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
@click.option('-w', 'output',
        default='',
        help='specify project directory')
def init(template, citation, frozen, output):
    """Initialize a new project in the current directory. The project is
    created using the template with name TEMPLATE and placed in the output
    folder OUTPUT. If the frozen flag is specified, support files are copied
    rather than symlinked.

    The path OUTPUT either must not exist or be an empty folder. Missing
    intermediate directories are automtically constructed."""
    output_path = Path(output)

    if output_path.exists():
        if not (output_path.is_dir() and len(list(output_path.iterdir())) == 0):
            raise click.ClickException(
                f"project path '{output_path}' already exists and is not an empty diretory.")
    try:
        proj_gen = ProjectTemplate.load_from_template(
                template,
                citation,
                frozen=frozen)
    except FileExistsError as err:
        raise click.ClickException(err.strerror)
    proj_gen.create_output_folder(output_path)


# add copy .bbl option?
@cli.command()
@click.option('-C', 'directory',
        type=click.Path(),
        default='',
        help="working directory")
@click.option('--compression',
        type=click.Choice(['zip','bzip2','lzma'],case_sensitive=False),
        show_default=True,
        default='zip',
        help="compression mode")
def export(directory, compression):
    """Create a compressed export of an existing project."""
    proj_path = Path(directory)

    comp_dict = {'zip': zipfile.ZIP_DEFLATED,
            'bzip2':zipfile.ZIP_BZIP2,
            'lzma':zipfile.ZIP_LZMA}

    try:
        proj_info = load_proj_dict(proj_path)
    except FileNotFoundError:
        if proj_path == Path('.'):
            message = "Current directory is not a valid project folder."
        else:
            message = "Directory '{proj_path}' is not a valid project folder."
        raise click.ClickException(message)

    export_zip = zipfile.ZipFile(proj_info['project']+'.' + compression,'w')

    custom_files = [
            f"{proj_info['project']}.tex",
            f"{CONFIG['classinfo_file']}.tex",
            f"{CONFIG['bibinfo_file']}.tex"]

    for p in proj_path.iterdir():
        if (p.suffix in CONFIG['export_suffixes'] and
                p.name not in custom_files):
            export_zip.write(p,
                    compress_type=comp_dict[compression])

    classinfo_text = (proj_path / f"{CONFIG['classinfo_file']}.tex").read_text()
    bibinfo_text = (proj_path / f"{CONFIG['bibinfo_file']}.tex").read_text()
    with open(proj_path / f"{proj_info['project']}.tex",'r') as project_tex_file:
        proj_text = "".join(
                classinfo_text if line.startswith(f"\\input{{{CONFIG['classinfo_file']}}}")
                else bibinfo_text if line.startswith(f"\\input{{{CONFIG['bibinfo_file']}}}")
                else line for line in project_tex_file.readlines())
        export_zip.writestr(f"{proj_info['project']}.tex",proj_text)
    export_zip.close()

@cli.command()
@click.option('-C', 'directory',
        type=click.Path(),
        default='',
        help="working directory")
@click.option('--force/--no-force',
        default=False,
        help="overwrite project files")
def refresh(directory,force):
    """Regenerate project macro and support files.
    Refresh reads information from the project information file .tpr_info and
    uses it to rebuild auto-generated files.

    Symbolic links are always overwritten, but if the project is frozen,
    existing files are unchanged. The force tag overwrites copied macro and
    citation files.
    """
    proj_path = Path(directory)
    try:
        proj_info = ProjectTemplate.load_from_project(proj_path)
    except FileNotFoundError:
        if proj_path == Path('.'):
            message = "Current directory is not a valid project folder."
        else:
            message = "Directory '{proj_path}' is not a valid project folder."
        raise click.ClickException(message)

    try:
        proj_info.write_tpr_files(proj_path,force=force)
    except FileNotFoundError as err:
        raise click.ClickException(
                err.strerror + ".")
    except FileExistsError as err:
        raise click.ClickException(
                f"Could not overwrite existing file at '{err.filename}'. Run with `--force` to override.")


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

# add tpr clean function (remove not-in-use files, aux files, etc?)
