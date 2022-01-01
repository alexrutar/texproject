"""TODO: write"""
from __future__ import annotations

import datetime
import shutil
import os
from pathlib import Path
import stat
from typing import TYPE_CHECKING

import click
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from .base import NAMES
from .term import FORMAT_MESSAGE
from .control import (
    AtomicCommand,
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
    from typing import Iterable, Dict, Literal, Optional

    from .base import Modes, ModCommand
    from .filesystem import ProjectPath, _FileLinker


def data_name(name: str, mode: Modes) -> str:
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


class _CmdApplyModification(AtomicCommand):
    def __init__(self, mod: ModCommand):
        self._mod = mod  # type: ModCommand

    def get_ato(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict
    ) -> RuntimeClosure:
        def _callable():
            try:
                _apply_modification(self._mod, template_dict)
                return RuntimeOutput(True)
            except ValueError:
                # TODO: better error here!
                return RuntimeOutput(False)

        match self._mod:
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
            yield _CmdApplyModification(mod).get_ato(proj_path, template_dict, state)


class ApplyStateModifications(AtomicIterable):
    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        for mod in state["template_modifications"]:
            yield _CmdApplyModification(mod).get_ato(proj_path, template_dict, state)

        # TODO: fix this, should not modify global state outside callable
        state["template_modifications"] = []


class TemplateWriter(AtomicCommand):
    _env = Environment(
        loader=FileSystemLoader(searchpath=DATA_PATH.data_dir),
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
        target_path: Path,
        force: bool = False,
        executable: bool = False,
    ):
        self._template_path = template_path
        self._target_path = target_path
        self._force = force
        self._executable = executable

    def get_render_text(self, proj_path, template_dict, state, render_mods=None):
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

    def get_ato(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict
    ) -> RuntimeClosure:
        if self._target_path.exists() and not self._force:
            return RuntimeClosure(
                FORMAT_MESSAGE.info(
                    f"Using existing rendered template at '{self._target_path}'."
                ),
                *SUCCESS,
            )
        try:
            output = self.get_render_text(proj_path, template_dict, state)

            def _callable():
                self._target_path.parent.mkdir(parents=True, exist_ok=True)
                self._target_path.write_text(output)
                # catch chmod failure
                if self._executable:
                    os.chmod(
                        self._target_path, stat.S_IXUSR | stat.S_IWUSR | stat.S_IRUSR
                    )
                return RuntimeOutput(True)

            return RuntimeClosure(
                FORMAT_MESSAGE.render(
                    self._template_path,
                    self._target_path,
                    overwrite=self._target_path.exists(),
                ),
                True,
                _callable,
            )

        except TemplateNotFound:
            return RuntimeClosure(
                f"Missing template file at location '{self._target_path}'", *FAIL
            )


class GitignoreWriter(AtomicIterable):
    def __init__(self, force: bool = False):
        self._force = force

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        yield TemplateWriter(
            JINJA_PATH.gitignore, proj_path.gitignore, force=self._force
        ).get_ato(proj_path, template_dict, state)


class PrecommitWriter(AtomicIterable):
    def __init__(self, force: bool = False):
        self._force = force

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        yield TemplateWriter(
            JINJA_PATH.pre_commit,
            proj_path.pre_commit,
            executable=True,
            force=self._force,
        ).get_ato(proj_path, template_dict, state)


def _link_helper(linker, name, source_path, target_path, force) -> RuntimeClosure:
    def _callable():
        shutil.copyfile(str(source_path), str(target_path))
        return RuntimeOutput(True)

    message_args = (linker, name, target_path.parent)

    if not (source_path.exists() or target_path.exists()):
        return RuntimeClosure(
            FORMAT_MESSAGE.link(*message_args, mode="fail"),
            *FAIL,
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


class _CmdNameLinker(AtomicCommand):
    def __init__(
        self,
        linker: _FileLinker,
        name: str,
        force: bool = False,
        target_dir: Optional[Path] = None,
    ) -> None:
        self.linker = linker
        self.name = name
        self.force = force
        self._target_dir = target_dir

    def get_ato(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict
    ) -> RuntimeClosure:
        ato = _link_helper(
            self.linker,
            self.name,
            self.linker.file_path(self.name).resolve(),
            (self._target_dir if self._target_dir is not None else proj_path.data_dir)
            / NAMES.rel_data_path(self.name + self.linker.suffix, self.linker.mode),
            force=self.force,
        )

        # TODO: fix this, cannot modify state outside callable!
        if not ato.success():
            state["template_modifications"].append(
                (self.linker.mode, "remove", self.name)
            )
        return ato


class _CmdPathLinker(AtomicCommand):
    def __init__(
        self,
        linker: _FileLinker,
        source_path: Path,
        force: bool = False,
    ) -> None:
        self.linker = linker
        self.source_path = source_path
        self.force = force

    def get_ato(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict
    ) -> RuntimeClosure:
        # also check for wrong suffix
        if self.source_path.suffix != self.linker.suffix:
            return RuntimeClosure(
                f"Filetype '{self.source_path.suffix}' is invalid!", *FAIL
            )
        name = self.source_path.name
        ato = _link_helper(
            self.linker,
            name,
            self.source_path.resolve(),
            proj_path.data_dir
            / NAMES.rel_data_path(self.source_path.name, self.linker.mode),
            force=self.force,
        )

        if not ato.success():
            state["template_modifications"].append(
                (NAMES.convert_mode(self.linker.mode), "remove", name)
            )

        return ato


class NameSequenceLinker(AtomicIterable):
    def __init__(
        self,
        mode: Modes,
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
            _CmdNameLinker(
                LINKER_MAP[self._mode],
                name,
                force=self._force,
                target_dir=self._target_dir,
            ).get_ato(proj_path, template_dict, state)
            for name in self._name_list
        )


class PathSequenceLinker(AtomicIterable):
    def __init__(
        self,
        mode: Modes,
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
            _CmdPathLinker(
                LINKER_MAP[self._mode],
                path,
                force=self._force,
            ).get_ato(proj_path, template_dict, state)
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

        for writer in [
            TemplateWriter(JINJA_PATH.classinfo, proj_path.classinfo, force=True),
            TemplateWriter(JINJA_PATH.bibinfo, proj_path.bibinfo, force=True),
        ]:
            yield writer.get_ato(proj_path, template_dict, state)


class _CmdWriteTemplateDict(AtomicCommand):
    def get_ato(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict
    ) -> RuntimeClosure:
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
        yield _CmdWriteTemplateDict().get_ato(proj_path, template_dict, state)


class OutputFolderCreator(AtomicIterable):
    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        """Write top-level files into the project path."""
        # proj_path.echoer.init(proj_path.dir)
        for writer in [
            _CmdWriteTemplateDict(),
            TemplateWriter(JINJA_PATH.template_doc(state["template"]), proj_path.main),
            TemplateWriter(JINJA_PATH.project_macro, proj_path.project_macro),
        ]:
            yield writer.get_ato(proj_path, template_dict, state)


class GitFileWriter(AtomicIterable):
    def __init__(self, force: bool = False) -> None:
        self.force = force

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        for writer in [
            TemplateWriter(JINJA_PATH.gitignore, proj_path.gitignore, force=self.force),
            TemplateWriter(
                JINJA_PATH.build_latex, proj_path.build_latex, force=self.force
            ),
            TemplateWriter(
                JINJA_PATH.pre_commit,
                proj_path.pre_commit,
                executable=True,
                force=self.force,
            ),
        ]:
            yield writer.get_ato(proj_path, template_dict, state)


class LatexBuildWriter(AtomicIterable):
    def __init__(self, force: bool = False) -> None:
        self.force = force

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        yield TemplateWriter(
            JINJA_PATH.build_latex, proj_path.build_latex, force=self.force
        ).get_ato(proj_path, template_dict, state)


class FileEditor(AtomicIterable):
    def __init__(self, config_file: Literal["local", "global", "template"]):
        self._config_file = config_file

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        match self._config_file:
            case "local":
                fpath = proj_path.config.local_path
            case "global":
                fpath = proj_path.config.global_path
            case "template":
                fpath = proj_path.template
            case _:
                yield RuntimeClosure(f"Invalid option for configuration file!", *FAIL)
                return

        try:
            click.edit(filename=str(fpath))
            yield RuntimeClosure(FORMAT_MESSAGE.edit(fpath), *SUCCESS)
        except click.UsageError:
            yield RuntimeClosure(
                FORMAT_MESSAGE.error("Could not open file for editing!"), *FAIL
            )


class _CmdRemovePath(AtomicCommand):
    def __init__(self, target: Path):
        self._target = target

    def get_ato(self, *_):
        def _callable():
            self._target.unlink()
            return RuntimeOutput(True)

        return RuntimeClosure(FORMAT_MESSAGE.remove(self._target), True, _callable)


class _CmdRenamePath(AtomicCommand):
    def __init__(self, source: Path, target: Path):
        self._source = source
        self._target = target

    def get_ato(self, *_):
        def _callable():
            self._source.rename(self._target)
            return RuntimeOutput(True)

        return RuntimeClosure(
            FORMAT_MESSAGE.rename(self._source, self._target), True, _callable
        )


class CleanRepository(AtomicIterable):
    def __init__(self, working_dir=None):
        self._working_dir = working_dir

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, *_
    ) -> Iterable[RuntimeClosure]:
        if self._working_dir is None:
            dir = proj_path.data_dir
        else:
            dir = self._working_dir

        for mode in NAMES.modes:
            for path, name in NAMES.existing_template_files(dir, mode):
                if name not in template_dict[NAMES.convert_mode(mode)]:
                    yield _CmdRemovePath(path).get_ato()


class UpgradeRepository(AtomicIterable):
    def __call__(self, proj_path: ProjectPath, *_) -> Iterable[RuntimeClosure]:
        import yaml
        import pytomlpp

        def _callable():
            yaml_path = proj_path.data_dir / "tpr_info.yaml"
            old_toml_path = proj_path.data_dir / "tpr_info.toml"
            if yaml_path.exists():
                proj_path.template.write_text(
                    pytomlpp.dumps(yaml.safe_load(yaml_path.read_text()))
                )
                yaml_path.unlink()
            if old_toml_path.exists():
                old_toml_path.rename(proj_path.template)

            # rename all the files
            for init, trg, end in [
                ("macro", "macros", ".sty"),
                ("citation", "citations", ".bib"),
                ("format", "style", ".sty"),
            ]:
                (proj_path.data_dir / trg).mkdir(exist_ok=True)
                for path in proj_path.data_dir.glob(f"{init}-*{end}"):
                    path.rename(
                        proj_path.data_dir
                        / trg
                        / ("local-" + "".join(path.name.split("-")[1:]))
                    )

            # rename style directory
            if (proj_path.data_dir / "style").exists():
                (proj_path.data_dir / "style").rename(proj_path.data_dir / "styles")

            # rename format / style key to list of styles
            for old_name in ("format", "style"):
                try:
                    tpl_dict = pytomlpp.load(proj_path.template)
                    tpl_dict["styles"] = [tpl_dict.pop(old_name)]
                    proj_path.template.write_text(pytomlpp.dumps(tpl_dict))
                except KeyError:
                    pass
            return RuntimeOutput(True)

        yield RuntimeClosure(
            FORMAT_MESSAGE.info("Upgrading repository files"),
            True,
            _callable,
        )
