from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass
import shlex

from .base import UpdateCommand, LinkMode, ExportMode
from .control import RuntimeClosure, AtomicIterable, RuntimeOutput, TempDir
from .filesystem import JINJA_PATH, ProjectPath
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
    from .filesystem import TemplateDict
    from typing import Optional, Iterable
    from pathlib import Path


def compile_latex(
    proj_path: ProjectPath,
    build_dir: Path,
    check: bool = False,
) -> RuntimeClosure:
    """Compile the latex files located at build_dir"""

    short_cmd = [
        "latexmk",
        "-pdf",
        "-interaction=nonstopmode",
    ] + proj_path.config.process["latexmk_compile_options"]

    def _callable():
        out = run_cmd(
            short_cmd + [proj_path.config.render["default_tex_name"] + ".tex"],
            build_dir,
            check=check,
        )
        return out

    return RuntimeClosure(
        FORMAT_MESSAGE.info(
            "Compiling LaTeX file"
            f" '{build_dir}/{proj_path.config.render['default_tex_name']}.tex' with"
            f" command '{shlex.join(short_cmd)}'"
        ),
        True,
        _callable,
    )


def copy_output(proj_path: ProjectPath, build_dir: Path, output_map: dict[str, Path]):
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
    output_map: Optional[dict[str, Path]]

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: dict,
        temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        # copy files to a build directory and compile
        build_dir = temp_dir.provision()
        yield copy_directory(proj_path, proj_path.dir, build_dir)
        yield compile_latex(proj_path, build_dir)

        # copy the relevant output
        if self.output_map is not None and len(self.output_map) > 0:
            yield copy_output(proj_path, build_dir, output_map=self.output_map)


@dataclass
class ArchiveWriter(AtomicIterable):
    compression: str
    output_file: Path
    fmt: ExportMode = ExportMode.source

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: dict,
        temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        build_dir = temp_dir.provision()

        # must copy before ModifyArxiv
        yield copy_directory(proj_path, proj_path.dir, build_dir)

        # compile the tex files to get .bbl / .pdf
        if self.fmt in (ExportMode.arxiv, ExportMode.build):
            if self.fmt == ExportMode.arxiv:
                yield from ModifyArxiv(build_dir)(
                    proj_path, template_dict, state, temp_dir
                )
                output_map = {
                    ".bbl": build_dir
                    / (proj_path.config.render["default_tex_name"] + ".bbl")
                }
            else:
                output_map = {
                    ".pdf": build_dir
                    / (proj_path.config.render["default_tex_name"] + ".pdf")
                }
            yield compile_latex(proj_path, build_dir, check=True)
            yield copy_output(proj_path, build_dir, output_map)

        elif self.fmt == ExportMode.nohidden:
            yield from ModifyNoHidden(build_dir)(
                proj_path, template_dict, state, temp_dir
            )

        yield make_archive(build_dir, self.output_file, self.compression)


@dataclass
class ModifyArxiv(AtomicIterable):
    working_dir: Path

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: dict,
        temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        # rename data directory to a filename with no dots and which does not exist
        new_data_dir_name = proj_path.data_dir.name.replace(".", "")
        while (self.working_dir / new_data_dir_name).exists():
            new_data_dir_name += "X"
        new_data_dir = self.working_dir / new_data_dir_name

        main_tex_path = self.working_dir / (
            proj_path.config.render["default_tex_name"] + ".tex"
        )
        new_proj_path = ProjectPath(self.working_dir, data_dir=new_data_dir)

        yield rename_path(self.working_dir / proj_path.data_dir.name, new_data_dir)
        for st in ("classinfo_file", "bibinfo_file"):
            yield remove_path(new_data_dir / (proj_path.config.render[st] + ".tex"))

        # perform substitutions that arxiv does not like, respecting existing files
        yield apply_template_dict_modification(
            template_dict,
            UpdateCommand(LinkMode.macro, "typesetting", "arxiv-typesetting"),
        )
        yield from TemplateDictLinker()(
            new_proj_path,
            template_dict,
            state,
            temp_dir,
        )

        # todo: during dry run, temp_dir may not exist! in this situation, nothing will
        # print... todo: think about what sort of controls are required when interacting
        # with temp directories, or if it is fine for stuff to just fail. For example,
        # when some commands depend on modifications done by other commands / filesystem
        # state, (e.g. cleaning here) stuff will break very subtly
        yield from CleanProject()(new_proj_path, template_dict, state, temp_dir)

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


@dataclass
class ModifyNoHidden(AtomicIterable):
    working_dir: Path

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: dict,
        temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        # rename data directory to a filename with no dots and which does not exist
        new_data_dir_name = proj_path.data_dir.name.replace(".", "")
        while (self.working_dir / new_data_dir_name).exists():
            new_data_dir_name += "X"
        new_data_dir = self.working_dir / new_data_dir_name

        main_tex_path = self.working_dir / (
            proj_path.config.render["default_tex_name"] + ".tex"
        )
        new_proj_path = ProjectPath(self.working_dir, data_dir=new_data_dir)

        yield rename_path(self.working_dir / proj_path.data_dir.name, new_data_dir)
        for st in ("classinfo_file", "bibinfo_file"):
            yield remove_path(new_data_dir / (proj_path.config.render[st] + ".tex"))

        yield from TemplateDictLinker()(
            new_proj_path,
            template_dict,
            state,
            temp_dir,
        )

        # todo: during dry run, temp_dir may not exist! in this situation, nothing will
        # print... todo: think about what sort of controls are required when interacting
        # with temp directories, or if it is fine for stuff to just fail. For example,
        # when some commands depend on modifications done by other commands / filesystem
        # state, (e.g. cleaning here) stuff will break very subtly
        yield from CleanProject(remove_git_files=True)(
            new_proj_path, template_dict, state, temp_dir
        )

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
