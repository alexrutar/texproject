import click
from pathlib import Path
import zipfile

from . import __version__, __repo__
from .template import GenericTemplate, NewProjectTemplate
from .filesystem import (load_config_dict, load_proj_dict, TPR_INFO_FILENAME,
        TEMPLATE_DIR, MACRO_DIR, CITATION_DIR,
        list_macros, list_citations, list_templates)

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
        #  help='the name of the template to use')
@click.argument('output', type=click.Path())
        #  help='directory for new project')
@click.option('--citation','-c',
        multiple=True)
        #  help='specify a citation file')
def new(template, output, citation):
    """Create a new project."""
    output_path = Path(output)
    if output_path.exists():
        raise click.ClickException(
            f"project directory '{output_path}' already exists")
    proj_gen = NewProjectTemplate(template, output_path.name, citation)
    proj_gen.create_output_folder(output_path)


@cli.command()
@click.option('--directory',
        type=click.Path(),
        default='')
        #  help="project directory (leave empty for current)")
@click.option('--compression',
        type=click.Choice(['zip','bzip2','lzma'],case_sensitive=False),
        show_default=True,
        default='zip')
        #  help="specify compression algorithm")
def export(directory, compression):
    """Create a compressed export of an existing project."""
    proj_path = Path(directory)
    check_valid_project(proj_path)

    comp_dict = {'zip': zipfile.ZIP_DEFLATED,
            'bzip2':zipfile.ZIP_BZIP2,
            'lzma':zipfile.ZIP_LZMA}

    conf_info = load_config_dict()
    proj_info = load_proj_dict(proj_path)

    export_zip = zipfile.ZipFile(proj_info['project']+'.zip','w')

    for p in proj_path.iterdir():
        if p.suffix in conf_info['export_suffixes']:
            export_zip.write(p,
                    compress_type=comp_dict[compression])

    export_zip.close()

@cli.command()
@click.option('--directory',
        type=click.Path(),
        default='')
        #  help="project directory (leave empty for current)")
def refresh(directory):
    """Regenerate project symbolic links."""
    proj_path = Path(directory)
    check_valid_project(proj_path)

    conf_info = load_config_dict()
    proj_info = load_proj_dict(proj_path)

    tpl = GenericTemplate()

    # clear existing links
    for p in proj_path.iterdir():
        if p.stem.startswith(conf_info['macro_prefix']) or p.stem.startswith(conf_info['citation_prefix']):
            p.unlink()

    # add new macro links
    if proj_info['macros'] is not None:
        for pack in proj_info['macros']:
            tpl.link_macro(pack, proj_path)

    # add new citation links
    if proj_info['citations'] is not None:
        for cit in proj_info['citations']:
            tpl.link_citation(cit, proj_path)

@cli.command()
@click.option('--list','-l', 'listfiles',
        type=click.Choice(['C','M','T']),
        multiple=True,
        default=[])
@click.option('--show-all', is_flag=True)
def info(listfiles,show_all):
    """Retrieve program and template information."""
    if show_all or len(listfiles) == 0:
        click.echo(f"""
TPR - TexPRoject (version {__version__})
Maintained by Alex Rutar ({click.style(__repo__,fg='bright_blue')}).
MIT License.
""")

    if show_all:
        listfiles = ['C','M','T']

    lookup = {'C':(CITATION_DIR, "citation files", list_citations),
            'M':(MACRO_DIR, "macro files", list_macros),
            'T':(TEMPLATE_DIR, "templates", list_templates)}

    for code in listfiles:
        click.echo(f"{code}{lookup[code][1][1:]} stored in '{lookup[code][0]}'.")
        click.echo(f"Available {lookup[code][1]}:")
        click.secho("  "+"\t".join(lookup[code][2]()) + "\n")

