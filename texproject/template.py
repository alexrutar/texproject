from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import datetime
from pathlib import Path
import os
import errno

from .filesystem import (CONFIG, CONFIG_PATH, DATA_PATH, JINJA_PATH,
        ProjectPath, yaml_load, yaml_dump, yaml_load_local_template,
        macro_linker, format_linker, citation_linker, template_linker)

from .error import SystemDataMissingError

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
    def __init__(self, template_dict, template_name=None):
        self.user_dict = yaml_load(CONFIG_PATH.user)
        self.template_dict = template_dict
        self.template_name = template_name

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
            replace = CONFIG['replace_text'],
            date=datetime.date.today())

    def write_template(self, template_path, target_path, force=False):
        """Write template at location template_path to file at location
        target_path. Overwrite target_path when force=True."""
        if target_path.exists() and not force:
            raise FileExistsError(
                    errno.EEXIST,
                    f"Template write location aready exists",
                    str(target_path.resolve()))
        try:
            target_path.write_text(
                self.render_template(
                    self.env.get_template(str(template_path))))
        except TemplateNotFound:
            raise SystemDataMissingError(template_path)


class ProjectTemplate(GenericTemplate):
    @classmethod
    def load_from_template(cls, template_name, citations):
        """Load the template generator from a template name."""
        template_dict = template_linker.load_template(template_name)
        template_dict['citations'].extend(citations)
        self = cls(template_dict, template_name)
        return self

    @classmethod
    def load_from_project(cls, proj_path):
        """Load the template generator from an existing project."""
        template_dict = yaml_load_local_template(proj_path.config)
        return cls(template_dict)

    @classmethod
    def from_dict(cls, template_dict):
        return cls(template_dict)

    def write_tpr_files(self, proj_path, write_template=False):
        """Create texproject project data directory and write files."""

        # initialize resource directories
        for dir in proj_path.data_subdirs:
            dir.mkdir(exist_ok=True, parents=True)

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

        linker = PackageLinker(proj_path, force=False, silent_fail=True)
        linker.link_macros(self.template_dict['macros'])
        linker.link_citations(self.template_dict['citations'])

    def create_output_folder(self, proj_path):
        """Write user-visible output folder files into the project path."""
        self.write_template(
                JINJA_PATH.template_doc(self.template_name),
                proj_path.main)

        self.write_template(
                JINJA_PATH.project_macro,
                proj_path.project_macro)

    def write_git_files(self, proj_path):
        self.write_template(
                JINJA_PATH.gitignore,
                proj_path.gitignore)

    def write_arxiv_autotex(self, proj_path):
        self.write_template(
                JINJA_PATH.arxiv_autotex,
                proj_path.arxiv_autotex)


class PackageLinker:
    def __init__(self, proj_path, force=False, silent_fail=True):
        self.proj_path = proj_path
        self.force = force
        self.silent_fail = silent_fail

    def make_link(self, linker, name):
            """Helper function for linking."""
            linker.link_name(name,
                    self.proj_path.data_dir,
                    force=self.force,
                    silent_fail=self.silent_fail)

    def link_macros(self, macro_list):
        for macro in macro_list:
            self.make_link(macro_linker, macro)

    def link_citations(self, citation_list):
        for cit in citation_list:
            self.make_link(citation_linker, cit)
