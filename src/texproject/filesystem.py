"""TODO: write"""
from __future__ import annotations
from typing import TYPE_CHECKING
from importlib import resources

from . import defaults
from copy import copy
from pathlib import Path
import pytomlpp as toml
from xdg import XDG_DATA_HOME, XDG_CONFIG_HOME

from .base import (
    NAMES,
    constant,
    LinkMode,
    ModCommand,
    RemoveCommand,
    AddCommand,
    UpdateCommand,
)

if TYPE_CHECKING:
    from typing import Dict, Final, List, Optional


class TOMLLoader:
    @staticmethod
    def load(source: Path, missing_ok: bool = False) -> Dict:
        try:
            return toml.loads(source.read_text())
        except FileNotFoundError as err:
            if missing_ok:
                return {}
            else:
                raise err from None

    @staticmethod
    def default_template():
        return toml.loads(resources.read_text(defaults, "template.toml"))

    @staticmethod
    def default_config():
        return toml.loads(resources.read_text(defaults, "config.toml"))


def _merge_iter(*dcts: Dict):
    """TODO: write"""
    for k in set().union(*[set(dct.keys()) for dct in dcts]):
        dcts_with_key = [dct[k] for dct in dcts if k in dct.keys()]

        # last value always overrides
        if len(dcts_with_key) == 1 or any(
            not isinstance(dct, dict) for dct in dcts_with_key
        ):
            yield (k, dcts_with_key[-1])

        else:
            yield (k, {k: v for k, v in _merge_iter(*dcts_with_key)})


def _merge(*dcts: Dict) -> Dict:
    """TODO: write"""
    return {k: v for k, v in _merge_iter(*dcts)}


class TemplateDict(dict):
    def __init__(self, source: Path):
        return super().__init__(
            _merge(TOMLLoader.default_template(), TOMLLoader.load(source))
        )

    def dump(self, target: Path) -> None:
        target.write_text(toml.dumps(self))

    def apply_modification(self, mod: ModCommand):
        match mod:
            case RemoveCommand(mode, source):
                self[NAMES.convert_mode(mode)].remove(source)

            case AddCommand(mode, source, index):
                self[NAMES.convert_mode(mode)].insert(index, source)

            case UpdateCommand(mode, source, target):
                self[NAMES.convert_mode(mode)] = [
                    target if val == source else val
                    for val in self[NAMES.convert_mode(mode)]
                ]


class NamedTemplateDict(TemplateDict):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(template_linker.file_path(name) / NAMES.template_toml)


class Config:
    """TODO: write"""

    def __init__(self, working_dir: Path):
        """TODO: write"""
        self.working_dir = working_dir
        self._dct = _merge(
            TOMLLoader.default_config(),
            TOMLLoader.load(self.global_path, missing_ok=True),
            TOMLLoader.load(self.local_path, missing_ok=True),
        )
        self.user = self._dct["user"]
        self.render = self._dct["render"]
        self.process = self._dct["process"]
        self.github = self._dct["github"]

    @constant
    def global_path(self) -> Path:
        """TODO: write"""
        return XDG_CONFIG_HOME / "texproject" / "config.toml"

    @constant
    def local_path(self) -> Path:
        """TODO: write"""
        return self.working_dir / "config.toml"


class _DataPath:
    """TODO: write

    Data location constants
    """

    @constant
    def data_dir(self) -> Path:
        """TODO: write"""
        return XDG_DATA_HOME / "texproject"

    @constant
    def template_dir(self) -> Path:
        """TODO: write"""
        return self.data_dir / "templates"


class _JinjaTemplatePath:
    """TODO: write"""

    def template_doc(self, name: str) -> Path:
        """TODO: write"""
        return Path(name, NAMES.template_doc)

    @constant
    def project_macro(self) -> str:
        """TODO: write"""
        return "project_macro_file.tex"

    @constant
    def gitignore(self) -> str:
        """TODO: write"""
        return "gitignore"

    @constant
    def build_latex(self) -> str:
        """TODO: write"""
        return "build_latex.yml"

    @constant
    def pre_commit(self) -> str:
        """TODO: write"""
        return "pre-commit"

    @constant
    def classinfo(self) -> str:
        """TODO: write"""
        return "classinfo.tex"

    @constant
    def bibinfo(self) -> str:
        """TODO: write"""
        return "bibinfo.tex"

    @constant
    def bibliography(self) -> str:
        """TODO: write"""
        return "bibliography.tex"

    @constant
    def arxiv_autotex(self) -> str:
        """TODO: write"""
        return "arxiv_autotex.txt"


JINJA_PATH: Final = _JinjaTemplatePath()
DATA_PATH: Final = _DataPath()


def relative(base: str):
    """TODO: write"""

    def fset(self, value) -> None:
        del self, value
        raise AttributeError("Cannot change constant values")

    def decorator(func):
        def fget(self) -> Path:
            return {
                "root": self.working_dir / func(self),
                "data": (
                    self.working_dir
                    / self.config.render["project_data_folder"]
                    / func(self)
                ),
                "gh_actions": self.working_dir / ".github" / "workflows" / func(self),
                "git_hooks": self.working_dir / ".git" / "hooks" / func(self),
            }[base]

        return property(fget, fset)

    return decorator


class ProjectPath:
    def __init__(self, working_dir: Path):
        """If exists is False, check that there are no conflicts"""
        self.working_dir = working_dir.resolve()
        self.config = Config(working_dir)
        self.name = self.dir.name

    @relative("data")
    def template(self) -> str:
        """TODO: write"""
        return "template.toml"

    @relative("data")
    def classinfo(self) -> str:
        """TODO: write"""
        return f"{self.config.render['classinfo_file']}.tex"

    @relative("data")
    def bibinfo(self) -> str:
        """TODO: write"""
        return f"{self.config.render['bibinfo_file']}.tex"

    @relative("root")
    def dir(self) -> str:
        """TODO: write"""
        return ""

    @relative("data")
    def data_dir(self) -> str:
        """TODO: write"""
        return ""

    @relative("data")
    def temp_dir(self) -> str:
        """TODO: write"""
        return "tmp"

    @relative("root")
    def main(self) -> str:
        """TODO: write"""
        return f"{self.config.render['default_tex_name']}.tex"

    @relative("root")
    def arxiv_autotex(self) -> str:
        """TODO: write"""
        return "000README.XXX"

    @relative("root")
    def project_macro(self) -> str:
        """TODO: write"""
        return f"{self.config.render['project_macro_file']}.sty"

    @relative("root")
    def gitignore(self) -> str:
        """TODO: write"""
        return ".gitignore"

    @relative("root")
    def git_home(self) -> str:
        """TODO: write"""
        return ".git"

    @relative("root")
    def github_home(self) -> str:
        """TODO: write"""
        return ".github"

    @relative("gh_actions")
    def build_latex(self) -> str:
        """TODO: write"""
        return "build_latex.yml"

    @relative("git_hooks")
    def pre_commit(self) -> str:
        """TODO: write"""
        return "pre-commit"

    def mk_data_dir(self):
        for mode in LinkMode:
            (self.data_dir / NAMES.resource_subdir(mode)).mkdir(
                exist_ok=True, parents=True
            )


class _BaseLinker:
    """TODO: write"""

    def __init__(self, dir_path: Path, suffix: str, user_str: str) -> None:
        """TODO: write"""
        self.user_str: Final = user_str
        self.dir_path: Final = dir_path
        self.suffix: Final = suffix

    def valid_path(self, path: Path) -> bool:
        """TODO: write"""
        return path.suffix == self.suffix

    def list_names(self) -> List[str]:
        """TODO: write"""
        return sorted(
            [path.stem for path in self.dir_path.iterdir() if self.valid_path(path)]
        )

    def file_path(self, name: str) -> Path:
        """TODO: write"""
        return self.dir_path / f"{name}{self.suffix}"


class _FileLinker(_BaseLinker):
    """TODO: write"""

    def __init__(self, suffix: str, user_str: str, mode: LinkMode) -> None:
        """TODO: write"""
        super().__init__(
            DATA_PATH.data_dir / NAMES.resource_subdir(mode), suffix, user_str
        )
        self.mode = mode


class _TemplateLinker(_BaseLinker):
    """TODO: write"""

    def load_template(self, name: str) -> TemplateDict:
        """TODO: write"""
        return TemplateDict.from_path(self.file_path(name) / NAMES.template_toml)

    def valid_path(self, path: Path):
        """TODO: write"""
        return (
            super().valid_path(path)
            and (path / NAMES.template_doc).exists()
            and (path / NAMES.template_toml).exists()
        )


macro_linker: Final = _FileLinker(".sty", "macro file", LinkMode.macro)
citation_linker: Final = _FileLinker(".bib", "citation file", LinkMode.citation)
style_linker: Final = _FileLinker(".sty", "style file", LinkMode.style)
template_linker: Final = _TemplateLinker(DATA_PATH.template_dir, "", "template")

LINKER_MAP: Final = {
    LinkMode.macro: macro_linker,
    LinkMode.citation: citation_linker,
    LinkMode.style: style_linker,
    "template": template_linker,
}
