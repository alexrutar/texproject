"""TODO: write"""
from __future__ import annotations
import datetime
import errno
import os
import stat
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from .error import SystemDataMissingError
from .filesystem import (DATA_PATH, JINJA_PATH,
        toml_dump, toml_load_local_template,
        macro_linker, format_linker, citation_linker, template_linker)
from .term import render_echo, init_echo

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Optional, Iterable, Dict
    from jinja2 import Template
    from .filesystem import Config, ProjectInfo, _FileLinker


def safe_name(name: str, style: str) -> str:
    """Safe namer for use in templates."""
    if style == 'macro':
        return macro_linker.safe_name(name)
    if style == 'citation':
        return citation_linker.safe_name(name)
    if style == 'format':
        return format_linker.safe_name(name)
    return name


class GenericTemplate:
    """TODO: write"""
    def __init__(self, template_dict: Dict) -> None:
        """TODO: write"""
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


    def render_template(self, template: Template, config: Config) -> str:
        """Render template and return template text."""
        bibtext = '\\input{' + \
                f"{config.render['project_data_folder']}/{config.render['bibinfo_file']}" + \
                '}'
        return template.render(
            user = config.user,
            template = self.template_dict,
            config = config.render,
            bibliography = bibtext,
            replace = config.render['replace_text'],
            date=datetime.date.today())

    def write_template(self, template_path: Path, target_path: Path, config: Config,
            force:bool=False, verbose=False) -> None:
        """Write template at location template_path to file at location
        target_path. Overwrite target_path when force=True."""
        if target_path.exists() and not force:
            raise FileExistsError(
                    errno.EEXIST,
                    "Template write location aready exists",
                    str(target_path.resolve()))
        try:
            if verbose:
                if target_path.exists():
                    render_echo(template_path, target_path, overwrite=True)
                else:
                    render_echo(template_path, target_path, overwrite=False)

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(
                self.render_template(
                    self.env.get_template(str(template_path)),
                    config))

        except TemplateNotFound as err:
            raise SystemDataMissingError(template_path) from err


class ProjectTemplate(GenericTemplate):
    """TODO: write"""
    @classmethod
    def from_dict(cls, template_dict: Dict) -> ProjectTemplate:
        """TODO: write"""
        return cls(template_dict)

    def write_template_with_info(self, proj_info: ProjectInfo,
            template_path: Path, target_path: Path,
            force:bool=False, executable:bool=False) -> None:
        """TODO: write"""
        if not proj_info.dry_run:
            self.write_template(
                    template_path,
                    target_path,
                    proj_info.config,
                    force=force,
                    verbose=proj_info.verbose)
            if executable:
                os.chmod(target_path, stat.S_IXUSR |  stat.S_IWUSR | stat.S_IRUSR)

    def write_tpr_files(self, proj_info: ProjectInfo) -> None:
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

    def write_git_files(self, proj_info: ProjectInfo, force: bool=False) -> None:
        """TODO: write"""
        self.write_template_with_info(proj_info,
                JINJA_PATH.gitignore,
                proj_info.gitignore,
                force=force)
        self.write_template_with_info(proj_info,
                JINJA_PATH.build_latex,
                proj_info.build_latex,
                force=force)
        self.write_template_with_info(proj_info,
                JINJA_PATH.pre_commit,
                proj_info.pre_commit,
                executable=True,
                force=force)

    def write_arxiv_autotex(self, proj_info: ProjectInfo) -> None:
        """TODO: write"""
        self.write_template_with_info(proj_info,
                JINJA_PATH.arxiv_autotex,
                proj_info.arxiv_autotex)

class InitTemplate(ProjectTemplate):
    """TODO: write"""
    def __init__(self, template_name: str, citations: Iterable[str]):
        """Load the template generator from a template name."""
        template_dict = template_linker.load_template(template_name)
        template_dict['citations'].extend(citations)
        self.template_name = template_name
        super().__init__(template_dict)

    def create_output_folder(self, proj_info: ProjectInfo) -> None:
        """Write top-level files into the project path."""
        if proj_info.dry_run or proj_info.verbose:
            init_echo(proj_info.dir)

        if not proj_info.dry_run:
            # initialize texproject directory
            proj_info.data_dir.mkdir(exist_ok=True, parents=True)
            toml_dump(
                    proj_info.template,
                    self.template_dict)

        self.write_template_with_info(proj_info,
                JINJA_PATH.template_doc(self.template_name),
                proj_info.main)

        self.write_template_with_info(proj_info,
                JINJA_PATH.project_macro,
                proj_info.project_macro)


class LoadTemplate(ProjectTemplate):
    """TODO: write"""
    def __init__(self, proj_info: ProjectInfo) -> None:
        """Load the template generator from an existing project."""
        template_dict = toml_load_local_template(proj_info.template)
        super().__init__(template_dict)


class PackageLinker:
    """TODO: write"""
    def __init__(self, proj_info: ProjectInfo,
            force:bool=False, silent_fail:bool=True,
            is_path:bool=False) -> None:
        """TODO: write"""
        self.proj_info = proj_info
        self.force = force
        self.silent_fail = silent_fail
        self.is_path = is_path

    def make_link(self, linker: _FileLinker, name: str) -> None:
        """Helper function for linking."""
        if not self.proj_info.dry_run:
            linker.link_name(name,
                    self.proj_info.data_dir,
                    is_path=self.is_path,
                    force=self.force,
                    silent_fail=self.silent_fail,
                    verbose=self.proj_info.verbose)

    def link_macros(self, macro_list: Iterable[str]) -> None:
        """TODO: write"""
        for macro in macro_list:
            self.make_link(macro_linker, macro)

    def link_citations(self, citation_list: Iterable[str]) -> None:
        """TODO: write"""
        for cit in citation_list:
            self.make_link(citation_linker, cit)

    def link_format(self, fmt: Optional[str]) -> None:
        """TODO: write"""
        if fmt is not None:
            self.make_link(format_linker, fmt)
