from __future__ import annotations
import subprocess
import shlex
from typing import TYPE_CHECKING

from .control import AtomicCommand, RuntimeClosure, AtomicIterable, RuntimeOutput
from .term import FORMAT_MESSAGE
from .error import AbortRunner

if TYPE_CHECKING:
    from .filesystem import ProjectPath
    from typing import Dict, Optional, Iterable, Tuple, List
    from pathlib import Path


def run_cmd(
    command: List[str], working_dir: Path, check: bool = False
) -> RuntimeOutput:
    # deal with missing command (catch FileNotFoundError)
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


class _CmdRunCommand(AtomicCommand):
    def __init__(self, command):
        self._command = command

    def get_ato(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict
    ) -> RuntimeClosure:
        def _callable():
            return run_cmd(self._command, proj_path.dir)

        return RuntimeClosure(FORMAT_MESSAGE.cmd(self._command), True, _callable)


class RunCommand(AtomicIterable):
    def __init__(self, command):
        self._command = command

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        yield _CmdRunCommand(self._command).get_ato(proj_path, template_dict, state)


class InitializeGitRepo(AtomicIterable):
    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        for writer in [
            _CmdRunCommand(["git", "init"]),
            _CmdRunCommand(["git", "add", "-A"]),
            _CmdRunCommand(
                ["git", "commit", "-m", "Initialize new texproject repository."]
            ),
        ]:
            yield writer.get_ato(proj_path, template_dict, state)


class _CmdCompileLatex(AtomicCommand):
    def __init__(self, build_dir: Path, tex_dir=None, check: bool = False):
        self._build_dir = build_dir
        self._check = check
        self._tex_dir = tex_dir

    def get_ato(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict
    ) -> RuntimeClosure:
        if self._tex_dir is None:
            dir = proj_path.dir
        else:
            dir = self._tex_dir

        def _callable():
            out = run_cmd(
                ["latexmk", "-pdf", "-interaction=nonstopmode"]
                + proj_path.config.process["latexmk_compile_options"]
                + [
                    f"-outdir={str(self._build_dir)}",
                    proj_path.config.render["default_tex_name"] + ".tex",
                ],
                dir,
                check=self._check,
            )
            return out

        return RuntimeClosure(
            FORMAT_MESSAGE.info(
                f"Compiling LaTeX file '{dir}/{proj_path.config.render['default_tex_name']}.tex' with command '{shlex.join(['latexmk', '-pdf', '-interaction=nonstopmode'] + proj_path.config.process['latexmk_compile_options'])}'"
            ),
            True,
            _callable,
        )


class _CmdCopyOutput(AtomicCommand):
    def __init__(self, build_dir: Path, output_map: Dict[str, Path]):
        self._build_dir = build_dir
        self._output_map = output_map

    def get_ato(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict
    ) -> RuntimeClosure:
        def _callable():
            for filetype, target in self._output_map.items():
                try:
                    (
                        self._build_dir
                        / (proj_path.config.render["default_tex_name"] + filetype)
                    ).rename(target)
                except FileNotFoundError:
                    pass
            # todo: catch the case where something cannot be copied, even when requested!
            return RuntimeOutput(True)

        return RuntimeClosure(
            FORMAT_MESSAGE.info(
                "Creating output files: "
                + ", ".join(f"'{path.name}'" for path in self._output_map.values())
            ),
            True,
            _callable,
        )


class LatexCompiler(AtomicIterable):
    def __init__(self, output_map: Optional[Dict[str, Path]] = None):
        self._output_map = output_map

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        yield _CmdCompileLatex(temp_dir).get_ato(proj_path, template_dict, state)
        if self._output_map is not None and len(self._output_map) > 0:
            yield _CmdCopyOutput(temp_dir, output_map=self._output_map).get_ato(
                proj_path, template_dict, state
            )
