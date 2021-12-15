from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import datetime
import errno
import os
import stat

from .filesystem import (CONFIG, CONFIG_PATH, DATA_PATH, JINJA_PATH,
        toml_load, toml_dump, toml_load_local_template,
        macro_linker, format_linker, citation_linker, template_linker)

from .term import render_echo, link_echo, init_echo

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
        self.user_dict = toml_load(CONFIG_PATH.user)
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
            local = self.template_dict,
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
            # recursively create parent directories, if needed
            target_path.parent.mkdir(parents=True, exist_ok=True)
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
    def load_from_project(cls, proj_info):
        """Load the template generator from an existing project."""
        template_dict = toml_load_local_template(proj_info.config)
        return cls(template_dict)

    @classmethod
    def from_dict(cls, template_dict):
        return cls(template_dict)

    def write_template_with_info(self, proj_info, template_path, target_path, force=False, executable=False):
        if proj_info.verbose:
            render_echo(template_path, target_path)
        if not proj_info.dry_run:
            self.write_template(
                    template_path,
                    target_path,
                    force=force)
            if executable:
                os.chmod(target_path, stat.S_IXUSR |  stat.S_IWUSR | stat.S_IRUSR)

    def write_tpr_files(self, proj_info):
        """Create texproject project data directory and write files."""
        self.write_template_with_info(proj_info,
                JINJA_PATH.classinfo,
                proj_info.classinfo,
                force=True)
        self.write_template_with_info(proj_info,
                JINJA_PATH.bibinfo,
                proj_info.bibinfo,
                force=True)

        linker = PackageLinker(proj_info, force=False, silent_fail=True)
        linker.link_macros(self.template_dict['macros'])
        linker.link_citations(self.template_dict['citations'])
        linker.link_format(self.template_dict['format'])

    def create_output_folder(self, proj_info):
        """Write top-level files into the project path."""
        if proj_info.dry_run or proj_info.verbose:
            init_echo(proj_info.dir)

        if not proj_info.dry_run:
            # initialize texproject directory
            proj_info.data_dir.mkdir(exist_ok=True, parents=True)
            toml_dump(
                    proj_info.config,
                    self.template_dict)

        self.write_template_with_info(proj_info,
                JINJA_PATH.template_doc(self.template_name),
                proj_info.main)

        self.write_template_with_info(proj_info,
                JINJA_PATH.project_macro,
                proj_info.project_macro)

    def write_git_files(self, proj_info):
        self.write_template_with_info(proj_info,
                JINJA_PATH.gitignore,
                proj_info.gitignore)
        self.write_template_with_info(proj_info,
                JINJA_PATH.build_latex,
                proj_info.build_latex)
        self.write_template_with_info(proj_info,
                JINJA_PATH.pre_commit,
                proj_info.pre_commit,
                executable=True)

    def write_arxiv_autotex(self, proj_info):
        self.write_template_with_info(proj_info,
                JINJA_PATH.arxiv_autotex,
                proj_info.arxiv_autotex)


class PackageLinker:
    def __init__(self, proj_info, force=False, silent_fail=True, is_path=False):
        self.proj_info = proj_info
        self.force = force
        self.silent_fail = silent_fail
        self.is_path = is_path

    def make_link(self, linker, name):
        """Helper function for linking."""
        if self.proj_info.verbose:
            link_echo(linker, name, self.proj_info.data_dir)
        if not self.proj_info.dry_run:
            linker.link_name(name,
                    self.proj_info.data_dir,
                    is_path=self.is_path,
                    force=self.force,
                    silent_fail=self.silent_fail)

    def link_macros(self, macro_list):
        for macro in macro_list:
            self.make_link(macro_linker, macro)

    def link_citations(self, citation_list):
        for cit in citation_list:
            self.make_link(citation_linker, cit)

    def link_format(self, format):
        if format is not None:
            self.make_link(format_linker, format)
