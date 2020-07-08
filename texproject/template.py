from jinja2 import Environment, FileSystemLoader
import datetime
from pathlib import Path
import os
import errno

from .filesystem import (DATA_DIR, TPR_INFO_FILENAME, CONFIG,
        _TEMPLATE_DOC_NAME, _PROJECT_MACRO_TEMPLATE,
        _CLASSINFO_TEMPLATE,_BIBINFO_TEMPLATE,_BIBLIOGRAPHY_TEMPLATE,
        TEMPLATE_RESOURCE_DIR, load_user_dict, yaml_dump_proj_info, load_proj_dict,
        macro_linker, format_linker, citation_linker, template_linker)

# special renamed function for use in templates
def safe_name(name, style):
    if style == 'macro':
        return macro_linker.safe_name(name)
    elif style == 'citation':
        return citation_linker.safe_name(name)
    elif style == 'format':
        return format_linker.safe_name(name)
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
        # bootstrap bibliography content
        self.bibtext = self.env.get_template(
                str(_BIBLIOGRAPHY_TEMPLATE)).render(config = CONFIG)


    def render_template(self, template):
        return template.render(
            user = self.user_dict, # user parameters
            template = self.template_dict, # template parameters
            config = CONFIG, # general filename conventions
            bibliography = self.bibtext,
            date=datetime.date.today())


    def write_template(self, template_path, target_path, force=False):
        if target_path.exists() and not force:
            raise FileExistsError(
                    errno.EEXIST,
                    f"Template write location aready exists",
                    str(target_path.resolve()))
        target_path.write_text(
            self.render_template(
                self.env.get_template(str(template_path))))

class ProjectTemplate(GenericTemplate):
    @classmethod
    def load_from_template(cls, template_name, citations, frozen=False):
        template_dict = template_linker.load_template(template_name)
        template_dict['citations'].extend(citations)
        template_dict['frozen'] = frozen
        self = cls(template_dict)
        self.template_path = Path('templates', template_name, _TEMPLATE_DOC_NAME)
        return self

    @classmethod
    def load_from_project(cls, proj_path):
        template_dict = load_proj_dict(proj_path)
        return cls(template_dict)


    def write_tpr_files(self, out_folder,force=False,write_template=False):
        project_folder = out_folder / CONFIG['project_folder']
        project_folder.mkdir(exist_ok=True)
        # write project information file
        if write_template:
            yaml_dump_proj_info(out_folder, self.template_dict)

        # write templates
        self.write_template(
                _CLASSINFO_TEMPLATE,
                project_folder / f"{CONFIG['classinfo_file']}.tex",
                force=True)
        self.write_template(
                _BIBINFO_TEMPLATE,
                project_folder / f"{CONFIG['bibinfo_file']}.tex",
                force=True)

        # link macro, format, and citation files from resources
        for macro in self.template_dict['macros']:
            macro_linker.link_name(macro, project_folder,
                    frozen=self.template_dict['frozen'],
                    force=force)
        for cit in self.template_dict['citations']:
            citation_linker.link_name(cit, project_folder,
                    frozen=self.template_dict['frozen'],force=force)
        format_linker.link_name(
                self.template_dict['format'],
                project_folder,
                frozen=self.template_dict['frozen'],force=force)

    def create_output_folder(self, out_folder):
        project_folder = out_folder / CONFIG['project_folder']

        # write local files from templates
        self.write_template(
                self.template_path,
                out_folder / f"{CONFIG['default_tex_name']}.tex")
        self.write_template(
                _PROJECT_MACRO_TEMPLATE,
                out_folder / f"{CONFIG['project_macro_file']}.sty")

        self.write_tpr_files(out_folder,write_template=True)
