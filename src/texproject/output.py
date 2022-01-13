from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass
import shlex

from .base import UpdateCommand, LinkMode, ExportMode
from .control import RuntimeClosure, AtomicIterable, RuntimeOutput
from .filesystem import ProjectPath, JINJA_PATH
from .template import (
    JinjaTemplate,
    apply_template_dict_modification,
    TemplateDictLinker,
)
from .term import FORMAT_MESSAGE
from .utils import (
    run_cmd,
    remove_path,
    rename_path,
    copy_directory,
    make_archive,
    CleanProject,
)

if TYPE_CHECKING:
    from .filesystem import ProjectPath, TemplateDict
    from typing import Dict, Optional, Iterable
    from pathlib import Path


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


@dataclass
class LatexCompiler(AtomicIterable):
    output_map: Optional[Dict[str, Path]]

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        yield compile_latex(proj_path, temp_dir)
        if self.output_map is not None and len(self.output_map) > 0:
            yield copy_output(proj_path, temp_dir, output_map=self.output_map)


@dataclass
class ArchiveWriter(AtomicIterable):
    compression: str
    output_file: Path
    fmt: ExportMode = ExportMode.source

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        archive_dir = temp_dir / "archive"
        build_dir = temp_dir / "latex_compile"
        build_dir.mkdir()

        yield copy_directory(proj_path, proj_path.dir, archive_dir)

        # compile the tex files to get .bbl / .pdf
        if self.fmt in (ExportMode.arxiv, ExportMode.build):
            if self.fmt == "arxiv":
                # must copy first to ensure additional files are also moved
                yield from ModifyArxiv(archive_dir)(
                    proj_path, template_dict, state, temp_dir
                )
                output_map = {
                    ".bbl": archive_dir
                    / (proj_path.config.render["default_tex_name"] + ".bbl")
                }
            else:
                output_map = {
                    ".pdf": archive_dir
                    / (proj_path.config.render["default_tex_name"] + ".pdf")
                }
            yield compile_latex(proj_path, build_dir, archive_dir, check=True)
            yield copy_output(proj_path, build_dir, output_map)

        yield make_archive(archive_dir, self.output_file, self.compression)


@dataclass
class ModifyArxiv(AtomicIterable):
    working_dir: Path

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        # rename data directory to a filename with no dots and which does not exist
        new_data_dir_name = proj_path.data_dir.name.replace(".", "")
        while (self.working_dir / new_data_dir_name).exists():
            new_data_dir_name += "X"
        new_data_dir = self.working_dir / new_data_dir_name

        main_tex_path = self.working_dir / (
            proj_path.config.render["default_tex_name"] + ".tex"
        )

        yield rename_path(self.working_dir / proj_path.data_dir.name, new_data_dir)
        for st in ("classinfo_file", "bibinfo_file"):
            yield remove_path(new_data_dir / (proj_path.config.render[st] + ".tex"))

        # perform substitutions that arxiv does not like, respecting existing files
        yield apply_template_dict_modification(
            template_dict,
            UpdateCommand(LinkMode.macro, "typesetting", "arxiv-typesetting"),
        )
        yield from TemplateDictLinker(target_dir=new_data_dir)(
            proj_path, template_dict, state, temp_dir
        )

        # todo: during dry run, temp_dir may not exist! in this situation, nothing will print...
        # todo: think about what sort of controls are required when interacting with temp
        # directories, or if it is fine for stuff to just fail. For example, when some commands
        # depend on modifications done by other commands / filesystem state, (e.g. cleaning here)
        # stuff will break very subtly
        yield from CleanProject(new_data_dir)(proj_path, template_dict, state, temp_dir)

        # replace \input{...classinfo.tex} and \input{...bibinfo.tex}
        # with the contents of the corresponding files
        def _callable():
            with open(main_tex_path, "r", encoding="utf-8") as texfile:
                new_contents = texfile.read()

                for end, writer in [
                    (
                        proj_path.config.render["classinfo_file"],
                        JinjaTemplate(JINJA_PATH.classinfo),
                    ),
                    (
                        proj_path.config.render["bibinfo_file"],
                        JinjaTemplate(JINJA_PATH.bibinfo),
                    ),
                ]:
                    new_contents = new_contents.replace(
                        r"\input{" + proj_path.data_dir.name + "/" + end + r"}" + "\n",
                        writer.get_text(
                            proj_path,
                            template_dict,
                            render_mods={"project_data_folder": new_data_dir_name},
                        ),
                    )
            with open(main_tex_path, "w", encoding="utf-8") as texfile:
                texfile.write(new_contents)
            return RuntimeOutput(True)

        yield RuntimeClosure(
            FORMAT_MESSAGE.info("Modifying main tex file."),
            True,
            _callable,
        )
        yield JinjaTemplate(JINJA_PATH.arxiv_autotex).write(
            proj_path, template_dict, state, self.working_dir / "000README.XXX"
        )
