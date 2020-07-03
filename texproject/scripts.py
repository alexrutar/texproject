from pathlib import Path
from zipfile import ZipFile

from .template import GenericTemplate, NewProjectTemplate
from .filesystem import load_config_dict, load_proj_dict



    #  def check_errors(self):
        #  pass
        # TODO errors to check:
        #  - template yaml file has all required components
        #  - all the macro files exist
        #  - all the formatting files exist

        #  - tpr update: pull new source files from github
        # info file: macros, citations, template
        # issue note to add new lines to tex file / remove lines?
        # could regen file (and put old file in archive)?



        # TODO: argument parsing, script creation, and packaging on pypi
        # TODO: bibliography management
        # - argument in .yaml file specifying bibliography style
        #   - if this argument exists
        #     - generate bibliography code within the latex automatically at the end
        #     - always create a citations.bib file (see bib source below)
        #     - create Makefile citation management argument
        #   - if this argument does not exist, do not create any of the above
        # - command line argument specifying the bibliography source
        #   - if this argument exists, link the citation source
        #   - if this argument does not exist, create an empty citations.bib file
        #   - if the argument exists but does yield something correct, warn and create an empty citations.bib file

        # TODO: maybe include a python script to do project management? (instead of makefile)
        #   - this would have to be a global script that can detect local params ... or a local copy of the script
        #   - or maybe generate some .tpr_project_info file? that lets you specify the values directly
        #     - then can run some global script to rebuild the corresponding pieces
        # - see Path.unlink and shutil.make_archive

        # TODO: migrate other template files to new templater

        # installation script?


def create_new_project(template_name, project_name, citations):
    proj_gen = NewProjectTemplate(template_name, project_name, citations)
    proj_gen.create_output_folder(Path(project_name))



# TODO: support custom export scripts (bzip2, lzma)
def create_export(proj_path=Path('.')):
    conf_info = load_config_dict()
    proj_info = load_proj_dict(proj_path)

    export_zip = ZipFile(proj_info['project']+'.zip','w')

    for p in proj_path.iterdir():
        if p.suffix in conf_info['export_suffixes']:
            export_zip.write(p)

    export_zip.close()


def refresh_links(proj_path=Path('.')):
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
