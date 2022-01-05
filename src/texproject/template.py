"""TODO: write"""
from __future__ import annotations
from typing import TYPE_CHECKING

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

from .base import NAMES
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
    LINKER_MAP,
    toml_dump,
)

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Iterable, Dict, Optional

    from .base import LinkMode, ModCommand
    from .filesystem import ProjectPath, _FileLinker


def data_name(name: str, mode: LinkMode) -> str:
    return str(NAMES.rel_data_path(name, mode))


def _apply_modification(mod: ModCommand, template_dict: Dict):
    match mod:
        case (mode, "remove", name):
            template_dict[NAMES.convert_mode(mode)].remove(name)

        case (mode, "add", name, index):
            template_dict[NAMES.convert_mode(mode)].insert(index, name)

        case (mode, "update", name, new_name):
            template_dict[NAMES.convert_mode(mode)] = [
                new_name if val == name else val
                for val in template_dict[NAMES.convert_mode(mode)]
            ]


def apply_template_dict_modification(
    template_dict: Dict, mod: ModCommand
) -> RuntimeClosure:
    def _callable():
        try:
            _apply_modification(mod, template_dict)
            return RuntimeOutput(True)
        except ValueError:
            # TODO: better error here!
            return RuntimeOutput(False)

    match mod:
        case mode, "remove", name:
            msg = f"Remove {mode} '{name}' from template dict."
        case mode, "add", name, index:
            msg = f"Add {mode} '{name}' to template dict in position {index}."
        case (mode, "update", name, new_name):
            msg = f"Update {mode} {name} to {new_name}"
        case _:
            # todo: fix this
            msg = "Something bad happened"

    # todo: return error here if trying to remove a macro that does not exist, or something
    # or some sort of issue with inserting
    return RuntimeClosure(FORMAT_MESSAGE.info(msg), True, _callable)


class ApplyModificationSequence(AtomicIterable):
    def __init__(self, mods: Iterable[ModCommand]):
        self._mods = mods

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        for mod in self._mods:
            yield apply_template_dict_modification(template_dict, mod)


class ApplyStateModifications(AtomicIterable):
    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        for mod in state["template_modifications"]:
            yield apply_template_dict_modification(template_dict, mod)

        # TODO: fix this, should not modify global state outside callable
        state["template_modifications"] = []


class JinjaTemplate:
    _env = Environment(
        loader=ChoiceLoader(
            [
                PackageLoader(__name__.split(".")[0], "templates"),
                FileSystemLoader(searchpath=(DATA_PATH.data_dir / "templates")),
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

    def __init__(
        self,
        template_path: Path,
        force: bool = False,
        executable: bool = False,
    ):
        self._template_path = template_path
        self._force = force
        self._executable = executable

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
        return self._env.get_template(str(self._template_path)).render(
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
        if target_path.exists() and not self._force:
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
                if self._executable:
                    os.chmod(target_path, stat.S_IXUSR | stat.S_IWUSR | stat.S_IRUSR)
                return RuntimeOutput(True)

            return RuntimeClosure(
                FORMAT_MESSAGE.render(
                    self._template_path,
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
        state["template_modifications"].append((linker.mode, "remove", name))
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


class NameSequenceLinker(AtomicIterable):
    def __init__(
        self,
        mode: LinkMode,
        name_list: Iterable[str],
        force: bool = False,
        target_dir: Optional[Path] = None,
    ) -> None:
        """TODO: write"""
        self._mode = mode
        self._name_list = name_list
        self._force = force
        self._target_dir = target_dir

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        yield from (
            link_name(
                proj_path,
                state,
                LINKER_MAP[self._mode],
                name,
                force=self._force,
                target_dir=self._target_dir,
            )
            for name in self._name_list
        )


class PathSequenceLinker(AtomicIterable):
    def __init__(
        self,
        mode: LinkMode,
        path_list: Iterable[Path],
        force: bool = False,
    ) -> None:
        """TODO: write"""
        self._mode = mode
        self._path_list = path_list
        self._force = force

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        yield from (
            link_path(proj_path, state, LINKER_MAP[self._mode], path, force=self._force)
            for path in self._path_list
        )


class TemplateDictLinker(AtomicIterable):
    def __init__(self, force: bool = False, target_dir=None) -> None:
        self._force = force
        self._target_dir = target_dir

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        for mode in NAMES.modes:
            yield from NameSequenceLinker(
                mode,
                template_dict[NAMES.convert_mode(mode)],
                force=self._force,
                target_dir=self._target_dir,
            )(proj_path, template_dict, state, temp_dir)


class InfoFileWriter(AtomicIterable):
    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        yield from ApplyStateModifications()(proj_path, template_dict, state, temp_dir)

        for source, target in [
            (JINJA_PATH.classinfo, proj_path.classinfo),
            (JINJA_PATH.bibinfo, proj_path.bibinfo),
        ]:
            yield JinjaTemplate(source, force=True).write(
                proj_path, template_dict, state, target
            )


def write_template_dict(proj_path: ProjectPath, template_dict: Dict) -> RuntimeClosure:
    def _callable():
        proj_path.mk_data_dir()
        toml_dump(proj_path.template, template_dict)
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
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        yield write_template_dict(proj_path, template_dict)


class OutputFolderCreator(AtomicIterable):
    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        """Write top-level files into the project path."""
        yield write_template_dict(proj_path, template_dict)
        for source, target in [
            (JINJA_PATH.template_doc(state["template"]), proj_path.main),
            (JINJA_PATH.project_macro, proj_path.project_macro),
        ]:
            yield JinjaTemplate(source).write(proj_path, template_dict, state, target)
