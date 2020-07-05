from jinja2 import Environment, FileSystemLoader
import datetime
from pathlib import Path

from .filesystem import (DATA_DIR, TPR_INFO_FILENAME, CONFIG,
        _TEMPLATE_DOC_NAME, _PROJECT_MACRO_TEMPLATE,
        _CLASSINFO_TEMPLATE,_BIBINFO_TEMPLATE,
        TEMPLATE_RESOURCE_DIR, load_user_dict, yaml_dump_proj_info, load_proj_dict,
        macro_loader, format_loader, citation_loader, template_loader)

# special renamed function for use in templates
def safe_name(name, style):
    if style == 'macro':
        return macro_loader.safe_name(name)
    elif style == 'citation':
        return citation_loader.safe_name(name)
    elif style == 'format':
        return format_loader.safe_name(name)
    else:
        return name

class GenericTemplate:
    def __init__(self, template_dict):

        # initialize some parameters
        self.user_dict = load_user_dict()
        self.template_dict = template_dict


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

        self.env.filters['safe_name'] = safe_name


    def render_template(self, template):
        return template.render(
            user = self.user_dict, # user parameters
            template = self.template_dict, # template parameters
            config = CONFIG, # general filename conventions
            bibliography = f"\\input{{{CONFIG['bibinfo_file']}}}",
            date=datetime.date.today())


    def write_template(self, template_path, target_path):
        # warn if file already exists??
        return target_path.write_text(
                self.render_template(
                    self.env.get_template(str(template_path))))

class ProjectTemplate(GenericTemplate):
    @classmethod
    def load_from_template(cls, template_name, project_name, citations,frozen=False):
        template_dict = template_loader.load_template(template_name)
        template_dict['citations'].extend(citations)
        template_dict['project'] = project_name
        template_dict['frozen'] = frozen
        self = cls(template_dict)
        self.template_path = Path('templates', template_name, _TEMPLATE_DOC_NAME)
        return self

    @classmethod
    def load_from_project(cls, proj_path):
        template_dict = load_proj_dict(proj_path)
        return cls(template_dict)


    def write_tpr_files(self, out_folder,force=False):
        # write templates
        self.write_template(
                _CLASSINFO_TEMPLATE,
                out_folder / f"{CONFIG['classinfo_file']}.tex")
        self.write_template(
                _BIBINFO_TEMPLATE,
                out_folder / f"{CONFIG['bibinfo_file']}.tex")

        # link macro, format, and citation files from resources
        for macro in self.template_dict['macros']:
            macro_loader.link_name(macro, out_folder,
                    frozen=self.template_dict['frozen'],force=force)
        for cit in self.template_dict['citations']:
            citation_loader.link_name(cit, out_folder,
                    frozen=self.template_dict['frozen'],force=force)
        format_loader.link_name(
                self.template_dict['format'],
                out_folder,
                frozen=self.template_dict['frozen'],force=force)

    def create_output_folder(self, out_folder):
        out_folder.mkdir(parents=True,exist_ok=True)

        # write local files from templates
        self.write_template(
                self.template_path,
                out_folder / f"{self.template_dict['project']}.tex")
        self.write_template(
                _PROJECT_MACRO_TEMPLATE,
                out_folder / f"{CONFIG['project_macro_file']}.sty")

        # write project information file
        yaml_dump_proj_info(out_folder, self.template_dict)

        self.write_tpr_files(out_folder)
