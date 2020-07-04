from jinja2 import Environment, FileSystemLoader
import datetime
from pathlib import Path

from .filesystem import (DATA_DIR, TPR_INFO_FILENAME, CONVENTIONS,
        TEMPLATE_RESOURCE_DIR, load_user_dict, 
        macro_loader, formatting_loader, citation_loader, template_loader)

class GenericTemplate:
    def __init__(self):

        # initialize some parameters
        self.user_dict = load_user_dict()
        self.local_dict = {}
        self.template_dict = {}


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


    def render_template(self, template):
        return template.render(
            user = self.user_dict, # user parameters
            local = self.local_dict, # local parameters
            template = self.template_dict, # template parameters
            conventions = CONVENTIONS, # general filename conventions
            bibliography = f"\\input{{{CONVENTIONS['bibinfo_file']}}}",
            date=datetime.date.today())


    def write_template(self, template_path, target_path):
        return target_path.write_text(
                self.render_template(
                    self.env.get_template(str(template_path))))

class NewProjectTemplate(GenericTemplate):
    def __init__(self, template_name, project_name, citations):
        super().__init__()
        self.template_dict = template_loader.load_template(template_name)

        self.local_dict = {
                'project' : project_name,
                'citations': citations,
                'template': template_name,
                'formatting_name': formatting_loader.safe_name(
                    self.template_dict['formatting']),
                'macro_names': [macro_loader.safe_name(macro)
                    for macro in self.template_dict['macros']],
                'citation_names': [citation_loader.safe_name(cit)
                    for cit in citations]
                }



    def create_output_folder(self, out_folder):
        out_folder.mkdir()

        # write local files
        self.write_template(
                Path('templates', self.local_dict['template'], 'document.tex'),
                out_folder / f"{self.local_dict['project']}.tex")
        self.write_template(
                TEMPLATE_RESOURCE_DIR / 'classinfo.tex',
                out_folder / f"{CONVENTIONS['classinfo_file']}.tex")
        self.write_template(
                TEMPLATE_RESOURCE_DIR / 'bibinfo.tex',
                out_folder / f"{CONVENTIONS['bibinfo_file']}.tex")
        self.write_template(
                TEMPLATE_RESOURCE_DIR / 'tpr_link_info.yaml',
                out_folder / TPR_INFO_FILENAME)
        self.write_template(
                TEMPLATE_RESOURCE_DIR / 'project_macro_file.tex',
                out_folder / f"{CONVENTIONS['project_macro_file']}.sty")

        # link macro, formatting, and citation files from resources
        for macro in self.template_dict['macros']:
            macro_loader.link_name(macro, out_folder)
        for cit in self.local_dict['citations']:
            citation_loader.link_name(cit, out_folder)
        formatting_loader.link_name(
                self.template_dict['formatting'],
                out_folder)
