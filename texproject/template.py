from jinja2 import Environment, FileSystemLoader
import datetime
from pathlib import Path

from .filesystem import (DATA_DIR, TPR_INFO_FILENAME,
        load_config_dict, load_user_dict, load_template_dict, 
        macro_path, citation_path, formatting_path)

class GenericTemplate:
    def __init__(self):

        # initialize some parameters
        self.conventions = load_config_dict()
        self.user_dict = load_user_dict()
        self.local_dict = {}
        self.template_dict = {}
        self.bibliography = ""


        self.env = Environment(
                # jinja2 does not support PathLib objects
                loader=FileSystemLoader(searchpath=DATA_DIR),
                block_start_string="<*",
                block_end_string="*>",
                variable_start_string="<+",
                variable_end_string="+>",
                comment_start_string="<#",
                comment_end_string="#>",
                trim_blocks=True
                )


    def pref_macro(self, macro):
        return f"{self.conventions['macro_prefix']}-{macro}"

    def pref_citation(self, cit):
        return f"{self.conventions['citation_prefix']}-{cit}"

    def pref_formatting(self, form):
        return f"{self.conventions['formatting_prefix']}-{form}"

    def link_macro(self, macro, rel_path):
        (rel_path / (self.pref_macro(macro) + '.sty')).symlink_to(
                macro_path(macro))

    def link_citation(self, cit, rel_path):
        (rel_path / (self.pref_citation(cit) + '.bib')).symlink_to(
                citation_path(cit))

    def link_formatting(self, form, rel_path):
        (rel_path / (self.pref_formatting(form) + '.sty')).symlink_to(
                formatting_path(form))

    def render_template(self, template):
        return template.render(
            user = self.user_dict, # user parameters
            local = self.local_dict, # local parameters
            template = self.template_dict, # template parameters
            conventions = self.conventions, # general filename conventions
            bibliography = self.bibliography,
            date=datetime.date.today())


class NewProjectTemplate(GenericTemplate):
    def __init__(self, template_name, project_name, citations):
        super().__init__()
        self.template_dict = load_template_dict(template_name)

        self.local_dict = {
                'project' : project_name,
                'citations': citations,
                'template': template_name,
                'formatting_name': self.pref_formatting(
                    self.template_dict['formatting']),
                'macro_names': [self.pref_macro(macro)
                    for macro in self.template_dict['macros']],
                'citation_names': [self.pref_citation(cit)
                    for cit in citations]
                }



    def create_output_folder(self, out_folder):
        out_folder.mkdir()

        # write local files
        (out_folder / f"{self.local_dict['project']}.tex").write_text(
             self.render_template(self.env.get_template(
                 str(Path('templates', self.local_dict['template'], 'document.tex')))))
        (out_folder / TPR_INFO_FILENAME).write_text(
             self.render_template(self.env.get_template(
                 str(Path('resources', 'other', 'tpr_link_info.yaml')))))
        (out_folder / f"{self.conventions['project_macro_file']}.sty").write_text(
             self.conventions['project_macro_file_contents'])

        # link macro, formatting, and citation files from resources
        for macro in self.template_dict['macros']:
            self.link_macro(macro, out_folder)
        for cit in self.local_dict['citations']:
            self.link_citation(cit, out_folder)
        self.link_formatting(self.template_dict['formatting'],out_folder)
