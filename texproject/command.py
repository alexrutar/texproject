import click
from pathlib import Path
import zipfile

from . import __version__, __repo__
from .template import ProjectTemplate
from .filesystem import (load_proj_dict, TPR_INFO_FILENAME, CONFIG,
        macro_loader, citation_loader, template_loader)

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
@click.argument('output', type=click.Path())
@click.option('--citation','-c',
        multiple=True)
@click.option('--frozen/--no-frozen',
        default=False)
def new(template, output, citation, frozen):
    """Create a new project. The project is created using the template with
    name TEMPLATE and placed in the output folder OUTPUT. Citation files can be
    specified by the citation flag, with multiple invocations for multiple
    files. The frozen flag copies the project macro files directly rather than
    creating symlinks.

    The path OUTPUT either must not exist or be an empty folder. Missing
    intermediate directories are automtically constructed."""
    output_path = Path(output)

    if output_path.exists():
        if not (output_path.is_dir() and len(list(output_path.iterdir())) == 0):
            raise click.ClickException(
                f"project path '{output_path}' already exists and is not an empty diretory.")
    proj_gen = ProjectTemplate.load_from_template(
            template,
            output_path.name.lstrip('.'),
            citation,
            frozen=frozen)
    proj_gen.create_output_folder(output_path)


# add copy .bbl option?
@cli.command()
@click.option('--directory',
        type=click.Path(),
        default='')
@click.option('--compression',
        type=click.Choice(['zip','bzip2','lzma'],case_sensitive=False),
        show_default=True,
        default='zip')
def export(directory, compression):
    """Create a compressed export of an existing project. The compression
    flag allows specification of the compression algorithm to be used.
    The directory flag allows the program to specify the project directory,
    and defaults to the current directory."""
    proj_path = Path(directory)
    check_valid_project(proj_path)

    comp_dict = {'zip': zipfile.ZIP_DEFLATED,
            'bzip2':zipfile.ZIP_BZIP2,
            'lzma':zipfile.ZIP_LZMA}

    proj_info = load_proj_dict(proj_path)

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
@click.option('--directory',
        type=click.Path(),
        default='')
@click.option('--force/--no-force',
        default=False)
def refresh(directory,force):
    """Regenerate project symbolic links."""
    proj_path = Path(directory)
    check_valid_project(proj_path)

    proj_info = ProjectTemplate.load_from_project(proj_path)
    proj_info.write_tpr_files(proj_path,force=force)


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

    loader = {'C': citation_loader,
            'M': macro_loader,
            'T': template_loader}

    for code in listfiles:
        ld = loader[code]
        click.echo(f"Directory for {ld.user_str}s: '{ld.dir_path}'.")
        click.echo(f"Available {ld.user_str}s:")
        click.echo("\t"+"\t".join(ld.list_names()) + "\n")

# add tpr clean function (remove not-in-use files, aux files, etc?)
