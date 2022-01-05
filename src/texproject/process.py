from __future__ import annotations
import subprocess
import shlex
from typing import TYPE_CHECKING

from .error import AbortRunner
from .control import RuntimeClosure, AtomicIterable, RuntimeOutput
from .term import FORMAT_MESSAGE

if TYPE_CHECKING:
    from .filesystem import ProjectPath
    from typing import Dict, Optional, Iterable, List
    from pathlib import Path


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
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        yield run_command(proj_path, self._command)


def compile_latex(
    proj_path: ProjectPath, build_dir: Path, tex_dir: Path = None, check: bool = False
):
    if tex_dir is None:
        dir = proj_path.dir
    else:
        dir = tex_dir

    def _callable():
        out = run_cmd(
            ["latexmk", "-pdf", "-interaction=nonstopmode"]
            + proj_path.config.process["latexmk_compile_options"]
            + [
                f"-outdir={str(build_dir)}",
                proj_path.config.render["default_tex_name"] + ".tex",
            ],
            dir,
            check=check,
        )
        return out

    return RuntimeClosure(
        FORMAT_MESSAGE.info(
            f"Compiling LaTeX file '{dir}/{proj_path.config.render['default_tex_name']}.tex' with command '{shlex.join(['latexmk', '-pdf', '-interaction=nonstopmode'] + proj_path.config.process['latexmk_compile_options'])}'"
        ),
        True,
        _callable,
    )


def copy_output(proj_path: ProjectPath, build_dir: Path, output_map: Dict[str, Path]):
    def _callable():
        for filetype, target in output_map.items():
            try:
                (
                    build_dir / (proj_path.config.render["default_tex_name"] + filetype)
                ).rename(target)
            except FileNotFoundError:
                pass
        # todo: catch the case where something cannot be copied, even when requested!
        return RuntimeOutput(True)

    return RuntimeClosure(
        FORMAT_MESSAGE.info(
            "Creating output files: "
            + ", ".join(f"'{path.name}'" for path in output_map.values())
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
        yield compile_latex(proj_path, temp_dir)
        if self._output_map is not None and len(self._output_map) > 0:
            yield copy_output(proj_path, temp_dir, output_map=self._output_map)
