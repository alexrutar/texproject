"""TODO: write"""
from __future__ import annotations
import datetime
import errno
import os
from pathlib import Path
import stat
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from .error import SystemDataMissingError
from .filesystem import (
    DATA_PATH,
    JINJA_PATH,
    NAMES,
    LINKER_MAP,
    toml_dump,
    toml_load_local_template,
    template_linker,
)

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Iterable, Dict, List
    from jinja2 import Template
    from .filesystem import Config, ProjectInfo, _FileLinker
    from .base import Modes
    from .term import VerboseEcho


def data_name(name: str, mode: Modes) -> str:
    return str(NAMES.rel_data_path(name, mode))


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
            trim_blocks=True,
        )

        self.env.filters["data_name"] = data_name

    def add(self, mode: Modes, name, index: int = 0) -> None:
        """TODO: write"""
        name_list = self.template_dict[NAMES.convert_mode(mode)]
        if name in name_list:
            name_list.remove(name)
        name_list.insert(index, name)

    def remove(self, mode: Modes, name) -> None:
        """TODO: write"""
        try:
            self.template_dict[NAMES.convert_mode(mode)].remove(name)
        except ValueError:
            pass

    def render_template(self, template: Template, config: Config) -> str:
        """Render template and return template text."""
        bibtext = (
            "\\input{"
            + f"{config.render['project_data_folder']}/{config.render['bibinfo_file']}"
            + "}"
        )
        return template.render(
            user=config.user,
            template=self.template_dict,
            config=config.render,
            process=config.process,
            bibliography=bibtext,
            replace=config.render["replace_text"],
            date=datetime.date.today(),
        )

    def write_template(
        self,
        template_path: Path,
        target_path: Path,
        config: Config,
        echoer: VerboseEcho,
        force: bool = False,
        dry_run=False,
    ) -> None:
        """Write template at location template_path to file at location
        target_path. Overwrite target_path when force=True."""
        if target_path.exists() and not force:
            raise FileExistsError(
                errno.EEXIST,
                "Template write location aready exists",
                str(target_path.resolve()),
            )
        # todo: same pattern as _link_helper (abstract out?)
        if target_path.exists():
            echoer.render(template_path, target_path, overwrite=True)
        else:
            echoer.render(template_path, target_path, overwrite=False)
        try:
            if not dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(
                    self.render_template(
                        self.env.get_template(str(template_path)), config
                    )
                )

        except TemplateNotFound as err:
            raise SystemDataMissingError(template_path) from err


class ProjectTemplate(GenericTemplate):
    """TODO: write"""

    @classmethod
    def from_dict(cls, template_dict: Dict) -> ProjectTemplate:
        """TODO: write"""
        return cls(template_dict)

    def write_template_with_info(
        self,
        proj_info: ProjectInfo,
        template_path: Path,
        target_path: Path,
        force: bool = False,
        executable: bool = False,
    ) -> None:
        """TODO: write"""
        self.write_template(
            template_path,
            target_path,
            proj_info.config,
            proj_info.echoer,
            force=force,
            dry_run=proj_info.dry_run,
        )
        if not proj_info.dry_run and executable:
            os.chmod(target_path, stat.S_IXUSR | stat.S_IWUSR | stat.S_IRUSR)

    def write_tpr_files(self, proj_info: ProjectInfo, force: bool = False) -> None:
        """Create texproject project data directory and write files."""
        linker = PackageLinker(proj_info, force=force, silent_fail=True)

        # careful: side effects are important!
        failed = {
            NAMES.convert_mode(mode): linker.link(
                mode, self.template_dict[NAMES.convert_mode(mode)]
            )
            for mode in NAMES.modes
        }

        # update the template
        for key, failed_names in failed.items():
            self.template_dict[key] = [
                name for name in self.template_dict[key] if name not in failed_names
            ]

        self.write_template_with_info(
            proj_info, JINJA_PATH.classinfo, proj_info.classinfo, force=True
        )
        self.write_template_with_info(
            proj_info, JINJA_PATH.bibinfo, proj_info.bibinfo, force=True
        )

        # todo: if something failed, still must raise an exception here
        # that way, the return code is correct

    def write_git_files(self, proj_info: ProjectInfo, force: bool = False) -> None:
        """TODO: write"""
        self.write_template_with_info(
            proj_info, JINJA_PATH.gitignore, proj_info.gitignore, force=force
        )
        self.write_template_with_info(
            proj_info, JINJA_PATH.build_latex, proj_info.build_latex, force=force
        )
        self.write_template_with_info(
            proj_info,
            JINJA_PATH.pre_commit,
            proj_info.pre_commit,
            executable=True,
            force=force,
        )

    def write_arxiv_autotex(self, proj_info: ProjectInfo) -> None:
        """TODO: write"""
        self.write_template_with_info(
            proj_info, JINJA_PATH.arxiv_autotex, proj_info.arxiv_autotex
        )

    def write_template_dict(self, proj_info: ProjectInfo):
        proj_info.echoer.write_template(
            proj_info.data_dir, overwrite=proj_info.template.exists()
        )

        if not proj_info.dry_run:
            # initialize texproject directory
            proj_info.mk_data_dir()
            toml_dump(proj_info.template, self.template_dict)


class InitTemplate(ProjectTemplate):
    """TODO: write"""

    def __init__(self, template_name: str):
        """Load the template generator from a template name."""
        template_dict = template_linker.load_template(template_name)
        self.template_name = template_name
        super().__init__(template_dict)

    def create_output_folder(self, proj_info: ProjectInfo) -> None:
        """Write top-level files into the project path."""
        proj_info.echoer.init(proj_info.dir)

        self.write_template_dict(proj_info)
        self.write_template_with_info(
            proj_info, JINJA_PATH.template_doc(self.template_name), proj_info.main
        )
        self.write_template_with_info(
            proj_info, JINJA_PATH.project_macro, proj_info.project_macro
        )


class LoadTemplate(ProjectTemplate):
    """TODO: write"""

    def __init__(self, proj_info: ProjectInfo) -> None:
        """Load the template generator from an existing project."""
        template_dict = toml_load_local_template(proj_info.template)
        super().__init__(template_dict)


class PackageLinker:
    """TODO: write"""

    def __init__(
        self, proj_info: ProjectInfo, force: bool = False, silent_fail: bool = True
    ) -> None:
        """TODO: write"""
        self.proj_info = proj_info
        self.force = force
        self.silent_fail = silent_fail

    def make_link(self, linker: _FileLinker, name: str) -> bool:
        """Helper function for linking. Returns True if the link was created, False if it failed,
        and None if no attempt was made"""
        return linker.link_name(
            name,
            self.proj_info.data_dir,
            force=self.force,
            echoer=self.proj_info.echoer,
            silent_fail=self.silent_fail,
            dry_run=self.proj_info.dry_run,
        )

    def make_path_link(self, linker: _FileLinker, name: Path) -> bool:
        """Helper function for linking. Returns True if the link was created, False if it failed,
        and None if no attempt was made"""
        return linker.link_path(
            name,
            self.proj_info.data_dir,
            force=self.force,
            echoer=self.proj_info.echoer,
            silent_fail=self.silent_fail,
            dry_run=self.proj_info.dry_run,
        )

    def link(self, mode: Modes, name_list: Iterable[str]) -> List[str]:
        return [
            name for name in name_list if not self.make_link(LINKER_MAP[mode], name)
        ]

    def link_paths(self, mode: Modes, path_list: Iterable[Path]) -> List[bool]:
        """TODO: write"""
        return [self.make_path_link(LINKER_MAP[mode], path) for path in path_list]
