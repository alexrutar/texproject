from __future__ import annotations
from typing import TYPE_CHECKING

import shutil
import subprocess

import click

from .base import NAMES, LinkMode
from .control import RuntimeOutput, RuntimeClosure, AtomicIterable, SUCCESS, FAIL
from .error import AbortRunner
from .term import FORMAT_MESSAGE

if TYPE_CHECKING:
    from pathlib import Path
    from typing import List, Iterable, Dict, Literal
    from .filesystem import ProjectPath, TemplateDict


def remove_path(target: Path) -> RuntimeClosure:
    def _callable():
        target.unlink()
        return RuntimeOutput(True)

    return RuntimeClosure(FORMAT_MESSAGE.remove(target), True, _callable)


def rename_path(source: Path, target: Path) -> RuntimeClosure:
    def _callable():
        source.rename(target)
        return RuntimeOutput(True)

    return RuntimeClosure(FORMAT_MESSAGE.rename(source, target), True, _callable)


def copy_directory(
    proj_path: ProjectPath, source: Path, target: Path
) -> RuntimeClosure:
    def _callable():
        shutil.copytree(
            source,
            target,
            copy_function=shutil.copy,
            ignore=shutil.ignore_patterns(*proj_path.config.process["ignore_patterns"]),
        )
        return RuntimeOutput(True)

    return RuntimeClosure(FORMAT_MESSAGE.copy(source, target), True, _callable)


def make_archive(source_dir, target_file, compression) -> RuntimeClosure:
    def _callable():
        shutil.make_archive(str(target_file), compression, source_dir)
        return RuntimeOutput(True)

    return RuntimeClosure(
        FORMAT_MESSAGE.info(
            f"Create compressed archive '{target_file}' with compression '{compression}'."
        ),
        True,
        _callable,
    )


def run_cmd(
    command: List[str], working_dir: Path, check: bool = False
) -> RuntimeOutput:
    try:
        proc = subprocess.run(command, cwd=working_dir, capture_output=True)
        if check and proc.returncode != 0:
            raise AbortRunner(
                f"subcommand returned non-zero exit code.", stderr=proc.stderr
            )

        return (
            RuntimeOutput(True, proc.stdout)
            if proc.returncode == 0
            else RuntimeOutput(False, proc.stderr)
        )
    except FileNotFoundError:
        raise AbortRunner(f"could not find command '{command[0]}'")


def run_command(proj_path: ProjectPath, command: List[str]) -> RuntimeClosure:
    def _callable():
        return run_cmd(command, proj_path.dir)

    return RuntimeClosure(FORMAT_MESSAGE.cmd(command), True, _callable)


class RunCommand(AtomicIterable):
    def __init__(self, command):
        self._command = command

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        yield run_command(proj_path, self._command)


class FileEditor(AtomicIterable):
    def __init__(self, config_file: Literal["local", "global", "template"]):
        self._config_file = config_file

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
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


class CleanProject(AtomicIterable):
    def __init__(self, working_dir=None):
        self._working_dir = working_dir

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, *_
    ) -> Iterable[RuntimeClosure]:
        if self._working_dir is None:
            dir = proj_path.data_dir
        else:
            dir = self._working_dir

        for mode in LinkMode:
            for path, name in NAMES.existing_template_files(dir, mode):
                if name not in template_dict[NAMES.convert_mode(mode)]:
                    yield remove_path(path)


class UpgradeProject(AtomicIterable):
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
