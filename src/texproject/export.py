from __future__ import annotations
from typing import TYPE_CHECKING

from .filesystem import ProjectPath, JINJA_PATH
from .template import (
    remove_path,
    rename_path,
    JinjaTemplate,
    apply_template_dict_modification,
    TemplateDictLinker,
    CleanRepository,
    copy_directory,
    make_archive,
)
from .term import FORMAT_MESSAGE
from .process import compile_latex, copy_output
from .control import RuntimeClosure, AtomicIterable, RuntimeOutput

# from .template import LoadTemplate

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Literal, Iterable, Dict


class ArchiveWriter(AtomicIterable):
    def __init__(
        self,
        compression: str,
        output_file: Path,
        fmt: Literal["archive", "build", "source"] = "source",
    ):
        self._compression = compression
        self._output_file = output_file
        self._fmt = fmt

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        archive_dir = temp_dir / "archive"
        build_dir = temp_dir / "latex_compile"
        build_dir.mkdir()

        yield copy_directory(proj_path, proj_path.dir, archive_dir)

        # compile the tex files to get .bbl / .pdf
        if self._fmt in ("arxiv", "build"):
            if self._fmt == "arxiv":
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

        yield make_archive(archive_dir, self._output_file, self._compression)


class ModifyArxiv(AtomicIterable):
    def __init__(self, working_dir):
        self._working_dir = working_dir

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        # rename data directory to a filename with no dots and which does not exist
        new_data_dir_name = proj_path.data_dir.name.replace(".", "")
        while (self._working_dir / new_data_dir_name).exists():
            new_data_dir_name += "X"
        new_data_dir = self._working_dir / new_data_dir_name

        main_tex_path = self._working_dir / (
            proj_path.config.render["default_tex_name"] + ".tex"
        )

        yield rename_path(self._working_dir / proj_path.data_dir.name, new_data_dir)
        for st in ("classinfo_file", "bibinfo_file"):
            yield remove_path(new_data_dir / (proj_path.config.render[st] + ".tex"))

        # perform substitutions that arxiv does not like, respecting existing files
        yield apply_template_dict_modification(
            template_dict, ("macro", "update", "typesetting", "arxiv-typesetting")
        )
        yield from TemplateDictLinker(target_dir=new_data_dir)(
            proj_path, template_dict, state, temp_dir
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

        # todo: during dry run, temp_dir may not exist! in this situation, nothing will print...
        # todo: think about what sort of controls are required when interacting with temp
        # directories, or if it is fine for stuff to just fail. For example, when some commands
        # depend on modifications done by other commands / filesystem state, (e.g. cleaning here)
        # stuff will break very subtly
        yield from CleanRepository(new_data_dir)(
            proj_path, template_dict, state, temp_dir
        )
        yield RuntimeClosure(
            FORMAT_MESSAGE.info("Modifying main tex file."),
            True,
            _callable,
        )
        yield JinjaTemplate(JINJA_PATH.arxiv_autotex).write(
            proj_path, template_dict, state, self._working_dir / "000README.XXX"
        )
