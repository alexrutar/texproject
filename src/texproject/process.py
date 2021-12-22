from __future__ import annotations
from pathlib import Path
import subprocess
from typing import TYPE_CHECKING

from .error import SubcommandError, LaTeXCompileError

if TYPE_CHECKING:
    from .filesystem import ProjectInfo, List


def compile_tex(proj_info: ProjectInfo, outdir: Path = Path.cwd(), output_map=None):
    """TODO: write"""
    if output_map is None:
        output_map = {}
    try:
        subproc_run(
            proj_info,
            ["latexmk", "-pdf", "-interaction=nonstopmode"]
            + proj_info.config.process["latexmk_compile_options"]
            + [
                f"-outdir={str(outdir)}",
                proj_info.config.render["default_tex_name"] + ".tex",
            ],
        )
    except SubcommandError as err:
        raise LaTeXCompileError() from err
    finally:
        for filetype, target in output_map.items():
            if target is not None:
                try:
                    (
                        outdir
                        / (proj_info.config.render["default_tex_name"] + filetype)
                    ).rename(target)
                except FileNotFoundError:
                    pass


def subproc_run(proj_info: ProjectInfo, command: List[str]):
    """TODO: write"""
    proj_info.echoer.cmd(command)

    if not proj_info.dry_run:
        try:
            proc = subprocess.run(
                command, cwd=proj_info.dir, check=True, capture_output=True
            )
        except subprocess.CalledProcessError as err:
            raise SubcommandError(err) from err

        proj_info.echoer.binary(proc.stdout)
