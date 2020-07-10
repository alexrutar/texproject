from jinja2 import Environment, FileSystemLoader
import datetime
from pathlib import Path
import os
import errno

from .filesystem import (CONFIG, CONFIG_PATH, DATA_PATH, JINJA_PATH,
        ProjectPath, yaml_load, yaml_dump, yaml_load_with_default_template,
        macro_linker, format_linker, citation_linker, template_linker)


def safe_name(name, style):
    """Safe namer for use in templates."""
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
        self.user_dict = yaml_load(CONFIG_PATH.user)
        self.template_dict = template_dict

        self.env = Environment(
                loader=FileSystemLoader(searchpath=DATA_PATH.data_dir),
                block_start_string="<*",
                block_end_string="*>",
                variable_start_string="<+",
                variable_end_string="+>",
                comment_start_string="<#",
                comment_end_string="#>",
                trim_blocks=True)

        self.env.filters['safe_name'] = safe_name

        # bootstrap bibliography content for render_template
        self.bibtext = self.env.get_template(
                str(JINJA_PATH.bibliography)).render(config = CONFIG)

    def render_template(self, template):
        """Render template and return template text."""
        return template.render(
            user = self.user_dict,
            template = self.template_dict,
            config = CONFIG,
            bibliography = self.bibtext,
            date=datetime.date.today())

    def write_template(self, template_path, target_path, force=False):
        """Write template at location template_path to file at location
        target_path. Overwrite target_path when force=True."""
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
        """Load the tempalte generator from a template name."""
        template_dict = template_linker.load_template(template_name)
        template_dict['citations'].extend(citations)
        template_dict['frozen'] = frozen
        self = cls(template_dict)
        self.template_path = JINJA_PATH.template_doc(template_name)
        return self

    @classmethod
    def load_from_project(cls, proj_path):
        """Load the template generator from an existing project."""
        template_dict = yaml_load_with_default_template(proj_path.config)
        return cls(template_dict)


    def write_tpr_files(self, proj_path, force=False, write_template=False):
        """Create texproject project data directory and write files."""
        proj_path.temp_dir.mkdir(exist_ok=True,parents=True)

        if write_template:
            yaml_dump(
                    proj_path.config,
                    self.template_dict)

        self.write_template(
                JINJA_PATH.classinfo,
                proj_path.classinfo,
                force=True)
        self.write_template(
                JINJA_PATH.bibinfo,
                proj_path.bibinfo,
                force=True)

        def make_link(linker, name):
            """Helper function for linking."""
            linker.link_name(name,
                    proj_path.data_dir,
                    frozen=self.template_dict['frozen'],
                    force=force)

        for macro in self.template_dict['macros']:
            make_link(macro_linker, macro)

        for cit in self.template_dict['citations']:
            make_link(citation_linker, cit)

        make_link(format_linker, self.template_dict['format'])

    def create_output_folder(self, proj_path):
        """Write user-visible output folder files into the project path."""
        self.write_template(
                self.template_path,
                proj_path.main)

        self.write_template(
                JINJA_PATH.project_macro,
                proj_path.macro_proj)
