"""TODO: write"""
from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass
import datetime
import shutil
import os
from pathlib import Path
import stat

from jinja2 import (
    Environment,
    ChoiceLoader,
    PackageLoader,
    FileSystemLoader,
    TemplateNotFound,
)

from .base import NAMES, AddCommand, RemoveCommand, UpdateCommand, LinkMode
from .term import FORMAT_MESSAGE
from .control import (
    RuntimeClosure,
    AtomicIterable,
    FAIL,
    SUCCESS,
    RuntimeOutput,
)
from .filesystem import (
    DATA_PATH,
    JINJA_PATH,
    TemplateDict,
    NamedTemplateDict,
    _FileLinker,
    LINKER_MAP,
)

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Iterable, Optional, ClassVar, Dict

    from .base import ModCommand
    from .filesystem import ProjectPath


def data_name(name: str, mode: LinkMode) -> str:
    return str(NAMES.rel_data_path(name, mode))


# def _apply_modification(mod: ModCommand, template_dict: TemplateDict):
#     match mod:
#         case RemoveCommand(mode, source):
#             template_dict[NAMES.convert_mode(mode)].remove(source)

#         case AddCommand(mode, source, index):
#             template_dict[NAMES.convert_mode(mode)].insert(index, source)

#         case UpdateCommand(mode, source, target):
#             template_dict[NAMES.convert_mode(mode)] = [
#                 target if val == source else val
#                 for val in template_dict[NAMES.convert_mode(mode)]
#             ]


def apply_template_dict_modification(
    template_dict: TemplateDict, mod: ModCommand
) -> RuntimeClosure:
    def _callable():
        try:
            template_dict.apply_modification(mod)
            return RuntimeOutput(True)
        except ValueError:
            return RuntimeOutput(False)

    match mod:
        case RemoveCommand(mode, source):
            msg = f"Remove {mode} '{source}' from template dict."
        case AddCommand(mode, source, index):
            msg = f"Add {mode} '{source}' to template dict in position {index}."
        case UpdateCommand(mode, source, target):
            msg = f"Update {mode} {source} to {target}"
        case _:
            return RuntimeClosure("Invalid template dict modification!", *FAIL)

    return RuntimeClosure(FORMAT_MESSAGE.info(msg), True, _callable)


@dataclass
class ApplyModificationSequence(AtomicIterable):
    mods: Iterable[ModCommand]

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        for mod in self.mods:
            yield apply_template_dict_modification(template_dict, mod)


class ApplyStateModifications(AtomicIterable):
    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        while len(state["template_modifications"]) > 0:
            yield apply_template_dict_modification(
                template_dict, state["template_modifications"].pop(0)
            )


@dataclass
class JinjaTemplate:
    template_path: Path
    force: bool = False
    executable: bool = False

    _env: ClassVar[Environment] = Environment(
        loader=ChoiceLoader(
            [
                PackageLoader(__name__.split(".")[0], "templates"),
                FileSystemLoader(searchpath=(DATA_PATH.template_dir)),
            ]
        ),
        block_start_string="<*",
        block_end_string="*>",
        variable_start_string="<+",
        variable_end_string="+>",
        comment_start_string="<#",
        comment_end_string="#>",
        trim_blocks=True,
    )
    _env.filters["data_name"] = data_name

    def get_text(self, proj_path, template_dict, render_mods=None):
        config = proj_path.config
        if render_mods is not None:
            render = {
                k: render_mods[k] if k in render_mods else v
                for k, v in config.render.items()
            }
        else:
            render = config.render

        bibtext = (
            "\\input{"
            + f"{render['project_data_folder']}/{render['bibinfo_file']}"
            + "}"
        )
        return self._env.get_template(str(self.template_path)).render(
            user=config.user,
            template=template_dict,
            config=render,
            github=config.github,
            process=config.process,
            bibliography=bibtext,
            replace=render["replace_text"],
            date=datetime.date.today(),
        )

    def write(
        self,
        proj_path: ProjectPath,
        template_dict: Dict,
        state: Dict,
        target_path: Path,
    ) -> RuntimeClosure:
        if target_path.exists() and not self.force:
            return RuntimeClosure(
                FORMAT_MESSAGE.info(
                    f"Using existing rendered template at '{target_path}'."
                ),
                *SUCCESS,
            )
        try:
            output = self.get_text(proj_path, template_dict, state)

            def _callable():
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(output)
                # catch chmod failure
                if self.executable:
                    os.chmod(target_path, stat.S_IXUSR | stat.S_IWUSR | stat.S_IRUSR)
                return RuntimeOutput(True)

            return RuntimeClosure(
                FORMAT_MESSAGE.render(
                    self.template_path,
                    target_path,
                    overwrite=target_path.exists(),
                ),
                True,
                _callable,
            )

        except TemplateNotFound:
            return RuntimeClosure(
                f"Missing template file at location '{target_path}'", *FAIL
            )


def _link_helper(
    linker, name, source_path, target_path, force, state
) -> RuntimeClosure:
    def _callable():
        shutil.copyfile(str(source_path), str(target_path))
        return RuntimeOutput(True)

    def _fail_callable():
        state["template_modifications"].append(RemoveCommand(linker.mode, name))
        return RuntimeOutput(False)

    message_args = (linker, name, target_path.parent)

    if not (source_path.exists() or target_path.exists()):
        return RuntimeClosure(
            FORMAT_MESSAGE.link(*message_args, mode="fail"), False, _fail_callable
        )
    if target_path.exists() and not force:
        return RuntimeClosure(
            FORMAT_MESSAGE.link(*message_args, mode="exists"), *SUCCESS
        )
    if target_path.exists():
        return RuntimeClosure(
            FORMAT_MESSAGE.link(*message_args, mode="overwrite"),
            True,
            _callable,
        )
    return RuntimeClosure(
        FORMAT_MESSAGE.link(*message_args, mode="new"),
        True,
        _callable,
    )


def link_name(
    proj_path: ProjectPath,
    state: Dict,
    linker: _FileLinker,
    name: str,
    force: bool = False,
    target_dir: Optional[Path] = None,
) -> RuntimeClosure:
    return _link_helper(
        linker,
        name,
        linker.file_path(name).resolve(),
        (target_dir if target_dir is not None else proj_path.data_dir)
        / NAMES.rel_data_path(name + linker.suffix, linker.mode),
        force,
        state,
    )


def link_path(
    proj_path: ProjectPath,
    state: Dict,
    linker: _FileLinker,
    source_path: Path,
    force: bool = False,
) -> RuntimeClosure:
    # also check for wrong suffix
    if source_path.suffix != linker.suffix:
        return RuntimeClosure(f"Filetype '{source_path.suffix}' is invalid!", *FAIL)
    return _link_helper(
        linker,
        source_path.name,
        source_path.resolve(),
        proj_path.data_dir / NAMES.rel_data_path(source_path.name, linker.mode),
        force,
        state,
    )


@dataclass
class NameSequenceLinker(AtomicIterable):
    mode: LinkMode
    name_list: Iterable[str]
    force: bool = False
    target_dir: Optional[Path] = None

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        yield from (
            link_name(
                proj_path,
                state,
                LINKER_MAP[self.mode],
                name,
                force=self.force,
                target_dir=self.target_dir,
            )
            for name in self.name_list
        )


@dataclass
class PathSequenceLinker(AtomicIterable):
    mode: LinkMode
    path_list: Iterable[Path]
    force: bool = False

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        yield from (
            link_path(proj_path, state, LINKER_MAP[self.mode], path, force=self.force)
            for path in self.path_list
        )


@dataclass
class TemplateDictLinker(AtomicIterable):
    force: bool = False
    target_dir: Optional[Path] = None

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        for mode in LinkMode:
            yield from NameSequenceLinker(
                mode,
                template_dict[NAMES.convert_mode(mode)],
                force=self.force,
                target_dir=self.target_dir,
            )(proj_path, template_dict, state, temp_dir)


class InfoFileWriter(AtomicIterable):
    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        yield from ApplyStateModifications()(proj_path, template_dict, state, temp_dir)

        for source, target in [
            (JINJA_PATH.classinfo, proj_path.classinfo),
            (JINJA_PATH.bibinfo, proj_path.bibinfo),
        ]:
            yield JinjaTemplate(source, force=True).write(
                proj_path, template_dict, state, target
            )


def write_template_dict(
    proj_path: ProjectPath, template_dict: TemplateDict
) -> RuntimeClosure:
    def _callable():
        proj_path.mk_data_dir()
        template_dict.dump(proj_path.template)
        return RuntimeOutput(True)

    return RuntimeClosure(
        FORMAT_MESSAGE.template_dict(
            proj_path.data_dir, overwrite=proj_path.template.exists()
        ),
        True,
        _callable,
    )


class TemplateDictWriter(AtomicIterable):
    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        yield write_template_dict(proj_path, template_dict)


class OutputFolderCreator(AtomicIterable):
    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: NamedTemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        """Write top-level files into the project path."""
        yield write_template_dict(proj_path, template_dict)
        for source, target in [
            (JINJA_PATH.template_doc(template_dict.name), proj_path.main),
            (JINJA_PATH.project_macro, proj_path.project_macro),
        ]:
            yield JinjaTemplate(source).write(proj_path, template_dict, state, target)
