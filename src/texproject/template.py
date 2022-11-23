"""TODO: write"""
from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass
from difflib import unified_diff
import datetime
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

from .base import NAMES, AddCommand, RemoveCommand, UpdateCommand, LinkMode, LinkCommand
from .term import FORMAT_MESSAGE
from .control import (
    RuntimeClosure,
    AtomicIterable,
    FAIL,
    SUCCESS,
    RuntimeOutput,
    TempDir,
)
from .filesystem import (
    DATA_PATH,
    JINJA_PATH,
    TemplateDict,
    NamedTemplateDict,
    FileLinker,
    LINKER_MAP,
)
from .utils import touch_file

if TYPE_CHECKING:
    from typing import Iterable, ClassVar

    from .base import ModCommand
    from .filesystem import ProjectPath


def data_name(name: str, mode: LinkMode) -> str:
    return str(NAMES.rel_data_path(name, mode))


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
        case AddCommand(mode, source, append):
            msg = (
                f"{'Append' if append else 'Prepend'} {mode} '{source}' to template"
                " dict."
            )
        case UpdateCommand(mode, source, target):
            msg = f"Update {mode} {source} to {target}"
        case _:
            return RuntimeClosure("Invalid template dict modification!", *FAIL)

    return RuntimeClosure(FORMAT_MESSAGE.info(msg), True, _callable)


@dataclass
class ApplyModificationSequence(AtomicIterable):
    mods: Iterable[ModCommand]

    def __call__(
        self, proj_path: ProjectPath, template_dict: TemplateDict, *_
    ) -> Iterable[RuntimeClosure]:
        for mod in self.mods:
            yield apply_template_dict_modification(template_dict, mod)


class ApplyStateModifications(AtomicIterable):
    def __call__(
        self, proj_path: ProjectPath, template_dict: TemplateDict, state: dict, *_
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
            metadata=config.metadata,
            github=config.github,
            process=config.process,
            bibliography=bibtext,
            replace=render["replace_text"],
            date=datetime.date.today(),
        )

    def write(
        self,
        proj_path: ProjectPath,
        template_dict: dict,
        state: dict,
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
    op: LinkCommand,
    linker: FileLinker,
    name: str,
    source_path: Path,
    target_path: Path,
    state,
) -> RuntimeClosure:
    message_args = (linker, name, target_path.parent)
    if op == LinkCommand.show:

        def _callable():
            return RuntimeOutput(True, output=source_path.read_text())

        return RuntimeClosure(
            FORMAT_MESSAGE.show(linker, name, mode="no-diff"),
            True,
            _callable,
        )

    elif op == LinkCommand.diff:

        def _callable():
            try:
                from_str = target_path.read_text().strip()
            except FileNotFoundError:
                from_str = ""
            to_str = source_path.read_text().strip()

            return RuntimeOutput(
                True,
                output="\n".join(
                    unified_diff(
                        from_str.split("\n"),
                        to_str.split("\n"),
                        fromfile=f"{target_path}",
                        tofile=f"{linker.user_str} '{name}'",
                        lineterm="",
                    )
                ),
            )

        return RuntimeClosure(
            FORMAT_MESSAGE.show(linker, name, mode="diff"),
            True,
            _callable,
        )

    else:

        def _callable():
            target_path.write_text(source_path.read_text().strip())
            return RuntimeOutput(True)

        def _fail_callable():
            state["template_modifications"].append(RemoveCommand(linker.mode, name))
            return RuntimeOutput(False)

        if not (source_path.exists() or target_path.exists()):
            return RuntimeClosure(
                FORMAT_MESSAGE.link(*message_args, mode="fail"), False, _fail_callable
            )
        if target_path.exists() and op == LinkCommand.copy:
            return RuntimeClosure(
                FORMAT_MESSAGE.link(*message_args, mode="exists"), *SUCCESS
            )
        if target_path.exists() and op == LinkCommand.replace:
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
    op: LinkCommand,
    proj_path: ProjectPath,
    state: dict,
    linker: FileLinker,
    name: str,
) -> RuntimeClosure:
    return _link_helper(
        op,
        linker,
        name,
        linker.file_path(name).resolve(),
        proj_path.data_dir / NAMES.rel_data_path(name + linker.suffix, linker.mode),
        state,
    )


def link_path(
    op: LinkCommand,
    proj_path: ProjectPath,
    state: dict,
    linker: FileLinker,
    source_path: Path,
) -> RuntimeClosure:
    # also check for wrong suffix
    if source_path.suffix != linker.suffix:
        return RuntimeClosure(f"Filetype '{source_path.suffix}' is invalid!", *FAIL)
    return _link_helper(
        op,
        linker,
        source_path.name,
        source_path.resolve(),
        proj_path.data_dir / NAMES.rel_data_path(source_path.name, linker.mode),
        state,
    )


@dataclass
class NameSequenceLinker(AtomicIterable):
    op: LinkCommand
    mode: LinkMode
    name_list: Iterable[str]

    def __call__(
        self, proj_path: ProjectPath, template_dict: TemplateDict, state: dict, *_
    ) -> Iterable[RuntimeClosure]:
        yield from (
            link_name(
                self.op,
                proj_path,
                state,
                LINKER_MAP[self.mode],
                name,
            )
            for name in self.name_list
        )


@dataclass
class PathSequenceLinker(AtomicIterable):
    op: LinkCommand
    mode: LinkMode
    path_list: Iterable[Path]

    def __call__(
        self, proj_path: ProjectPath, template_dict: dict, state: dict, *_
    ) -> Iterable[RuntimeClosure]:
        yield from (
            link_path(
                self.op,
                proj_path,
                state,
                LINKER_MAP[self.mode],
                path,
            )
            for path in self.path_list
        )


@dataclass
class TemplateDictLinker(AtomicIterable):
    op: LinkCommand = LinkCommand.copy

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: dict,
        temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        for mode in LinkMode:
            yield from NameSequenceLinker(
                self.op,
                mode,
                template_dict[NAMES.convert_mode(mode)],
            )(proj_path, template_dict, state, temp_dir)


class InfoFileWriter(AtomicIterable):
    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: dict,
        temp_dir: TempDir,
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
    proj_path: ProjectPath, template_dict: TemplateDict, force=True
) -> RuntimeClosure:
    def _callable():
        proj_path.mk_data_dir()
        template_dict.dump(proj_path.template)
        return RuntimeOutput(True)

    if proj_path.template.exists() and not force:
        return RuntimeClosure(
            FORMAT_MESSAGE.error("Template dict already exists!"), *FAIL
        )

    return RuntimeClosure(
        FORMAT_MESSAGE.template_dict(
            proj_path.data_dir, overwrite=proj_path.template.exists()
        ),
        True,
        _callable,
    )


class TemplateDictWriter(AtomicIterable):
    def __call__(
        self, proj_path: ProjectPath, template_dict: TemplateDict, *_
    ) -> Iterable[RuntimeClosure]:
        yield write_template_dict(proj_path, template_dict)


@dataclass
class OutputFolderCreator(AtomicIterable):
    force: bool = False

    def __call__(
        self, proj_path: ProjectPath, template_dict: NamedTemplateDict, state: dict, *_
    ) -> Iterable[RuntimeClosure]:
        """Write top-level files into the project path."""
        yield write_template_dict(proj_path, template_dict, force=self.force)
        for source, target in [
            (JINJA_PATH.template_doc(template_dict.name), proj_path.main),
            (JINJA_PATH.project_macro, proj_path.project_macro),
        ]:
            yield JinjaTemplate(source).write(proj_path, template_dict, state, target)
        yield touch_file(proj_path.latexmain)
