import click
from pathlib import Path
import zipfile

from .template import GenericTemplate, NewProjectTemplate
from .filesystem import load_config_dict, load_proj_dict, TPR_INFO_FILENAME

def check_valid_project(proj_path):
    if not (proj_path / TPR_INFO_FILENAME).exists():
        if proj_path == Path('.'):
            message = "Current directory is not a valid project folder."
        else:
            message = "Directory '{proj_path}' is not a valid project folder."
        raise click.ClickException(message)

@click.group()
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
            f"project directory '{path_obj}' already exists")
    proj_gen = NewProjectTemplate(template, output_path.name, citation)
    proj_gen.create_output_folder(output_path)


@cli.command()
@click.option('--directory',
        type=click.Path(),
        default='.')
        #  help="project directory (leave empty for current)")
@click.option('--compression',
        type=click.Choice(['ZIP','BZIP2','LZMA'],case_sensitive=False),
        show_default=True,
        default='ZIP')
        #  help="specify compression algorithm")
def export(directory, compression):
    """Create a compressed export of an existing project."""
    proj_path = Path(directory)
    check_valid_project(proj_path)

    comp_dict = {'ZIP': zipfile.ZIP_DEFLATED,
            'BZIP2':zipfile.ZIP_BZIP2,
            'LZMA':zipfile.ZIP_LZMA}

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
        default='.')
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
