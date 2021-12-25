from __future__ import annotations
import shutil
from typing import TYPE_CHECKING

from .base import NAMES
from .filesystem import ProjectPath, JINJA_PATH
from .template import (
    NameSequenceLinker,
    InfoFileWriter,
    TemplateWriter,
    _CmdApplyModification,
    TemplateDictLinker,
)
from .term import FORMAT_MESSAGE
from .process import _CmdCompileLatex, _CmdCopyOutput
from .control import AtomicCommand, RuntimeClosure, AtomicIterable, RuntimeOutput

# from .template import LoadTemplate

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Literal, Iterable, Dict


class _CmdCopyDirectory(AtomicCommand):
    def __init__(self, source_dir: Path, target_dir: Path):
        self._source = source_dir
        self._target = target_dir

    def get_ato(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict
    ) -> RuntimeClosure:
        def _callable():
            shutil.copytree(
                self._source,
                self._target,
                copy_function=shutil.copy,
                ignore=shutil.ignore_patterns(
                    *proj_path.config.process["ignore_patterns"]
                ),
            )
            return RuntimeOutput(True)

        return RuntimeClosure(
            FORMAT_MESSAGE.copy(self._source, self._target), True, _callable
        )


class _CmdMakeArchive(AtomicCommand):
    def __init__(self, source_dir, output_file, compression):
        self._source_dir = source_dir
        self._target_file = output_file
        self._compression = compression

    def get_ato(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict
    ) -> RuntimeClosure:
        def _callable():
            shutil.make_archive(
                str(self._target_file), self._compression, self._source_dir
            )
            return RuntimeOutput(True)

        # todo: format if overwriting
        # todo: add the file extension to the name
        return RuntimeClosure(
            FORMAT_MESSAGE.info(
                f"Create compressed archive '{self._target_file}' with compression '{self._compression}'."
            ),
            True,
            _callable,
        )


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

        yield _CmdCopyDirectory(proj_path.dir, archive_dir).get_ato(
            proj_path, template_dict, state
        )

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
            yield _CmdCompileLatex(build_dir, archive_dir, check=True).get_ato(
                proj_path, template_dict, state
            )
            yield _CmdCopyOutput(build_dir, output_map).get_ato(
                proj_path, template_dict, state
            )

        yield _CmdMakeArchive(
            archive_dir, self._output_file, self._compression
        ).get_ato(proj_path, template_dict, state)


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

        def _rename_callable():
            (self._working_dir / proj_path.data_dir.name).rename(new_data_dir)
            (
                new_data_dir / (proj_path.config.render["classinfo_file"] + ".tex")
            ).unlink()
            (new_data_dir / (proj_path.config.render["bibinfo_file"] + ".tex")).unlink()
            return RuntimeOutput(True)

        yield RuntimeClosure(
            FORMAT_MESSAGE.info(
                f"Rename file {self._working_dir / proj_path.data_dir.name} to {new_data_dir}."
            ),
            True,
            _rename_callable,
        )

        # perform substitutions that arxiv does not like, respecting existing files
        yield _CmdApplyModification(
            ("macro", "update", "typesetting", "arxiv-typesetting")
        ).get_ato(proj_path, template_dict, state)
        yield from TemplateDictLinker(target_dir=new_data_dir)(
            proj_path, template_dict, state, temp_dir
        )

        # replace \input{...classinfo.tex} and \input{...bibinfo.tex}
        # with the contents of the corresponding files

        def _callable():
            with open(main_tex_path, "r", encoding="utf-8") as texfile:
                new_contents = texfile.read()

                # TODO: write new TemplateWriter function to only get output
                for end, writer in [
                    (
                        proj_path.config.render["classinfo_file"],
                        TemplateWriter(JINJA_PATH.classinfo, None),
                    ),
                    (
                        proj_path.config.render["bibinfo_file"],
                        TemplateWriter(JINJA_PATH.bibinfo, None),
                    ),
                ]:
                    new_contents = new_contents.replace(
                        r"\input{" + proj_path.data_dir.name + "/" + end + r"}" + "\n",
                        writer.get_render_text(
                            proj_path,
                            template_dict,
                            state,
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
        yield TemplateWriter(
            JINJA_PATH.arxiv_autotex, self._working_dir / "000README.XXX"
        ).get_ato(proj_path, template_dict, state)
