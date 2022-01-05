"""TODO: write"""
from __future__ import annotations
from importlib import resources
from typing import TYPE_CHECKING

from pathlib import Path
import pytomlpp as toml
from xdg import XDG_DATA_HOME, XDG_CONFIG_HOME

from . import defaults
from .base import NAMES, constant
from .error import (
    ProjectDataMissingError,
    TemplateDataMissingError,
)

if TYPE_CHECKING:
    from .base import LinkMode
    from typing import Optional, List, Dict


def toml_load(path_obj: Path, missing_ok: bool = False) -> Dict:
    """TODO: write"""
    # add branch to check if the file exists / fails loading
    try:
        return toml.loads(path_obj.read_text())
    except FileNotFoundError as err:
        if missing_ok:
            return {}
        else:
            raise err from None


def toml_dump(path_obj: Path, dct: Dict) -> None:
    """TODO: write"""
    path_obj.write_text(toml.dumps(dct))


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


class Config:
    """TODO: write"""

    def __init__(self, working_dir: Path):
        """TODO: write"""
        self.working_dir = working_dir
        self._dct = _merge(
            DefaultLoader.config(),
            toml_load(self.global_path, missing_ok=True),
            toml_load(self.local_path, missing_ok=True),
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
    def resource_dir(self) -> Path:
        """TODO: write"""
        return XDG_DATA_HOME / "texproject" / "resources"

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


def relative(base: str):
    """TODO: write"""

    def fset(self, value) -> None:
        del self, value
        raise AttributeError("Cannot change constant values")

    def decorator(func):
        def fget(self) -> Path:
            if base == "root":
                return self.working_dir / func(self)
            elif base == "data":
                return (
                    self.working_dir
                    / self.config.render["project_data_folder"]
                    / func(self)
                )

            elif base == "gh_actions":
                return self.working_dir / ".github" / "workflows" / func(self)

            elif base == "git_hooks":
                return self.working_dir / ".git" / "hooks" / func(self)
            # TODO: fix
            raise Exception("something bad")

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
        for mode in NAMES.modes:
            (self.data_dir / NAMES.resource_subdir(mode)).mkdir(
                exist_ok=True, parents=True
            )


JINJA_PATH = _JinjaTemplatePath()
DATA_PATH = _DataPath()


class _BaseLinker:
    """TODO: write"""

    def __init__(self, dir_path: Path, suffix: str, user_str: str):
        """TODO: write"""
        self.user_str = user_str
        self.dir_path = dir_path
        self.suffix = suffix

    def valid_path(self, path: Path) -> bool:
        """TODO: write"""
        return path.suffix == self.suffix

    def list_names(self) -> List:
        """TODO: write"""
        return sorted(
            [path.stem for path in self.dir_path.iterdir() if self.valid_path(path)]
        )

    def file_path(self, name: str) -> Path:
        """TODO: write"""
        return self.dir_path / f"{name}{self.suffix}"


class _FileLinker(_BaseLinker):
    """TODO: write"""

    def __init__(self, suffix: str, user_str: str, mode: LinkMode):
        """TODO: write"""
        super().__init__(
            DATA_PATH.resource_dir / NAMES.resource_subdir(mode), suffix, user_str
        )
        self.mode = mode  # type: LinkMode


class DefaultLoader:
    @staticmethod
    def template() -> Dict:
        return toml.loads(resources.read_text(defaults, "template.toml"))

    @staticmethod
    def config() -> Dict:
        return toml.loads(resources.read_text(defaults, "config.toml"))


def toml_load_local_template(path: Path) -> Dict:
    """TODO: write"""
    try:
        template = toml_load(path)
    except FileNotFoundError as err:
        raise ProjectDataMissingError(
            path, message="The local template file is missing."
        ) from err
    return _merge(DefaultLoader.template(), template)


def toml_load_system_template(path: Path, user_str: str, name: Optional[str] = None):
    """TODO: write"""
    try:
        template = toml_load(path)
    except FileNotFoundError as err:
        raise TemplateDataMissingError(path, user_str=user_str, name=name) from err
    return _merge(DefaultLoader.template(), template)


class _TemplateLinker(_BaseLinker):
    """TODO: write"""

    def load_template(self, name: str) -> Dict:
        """TODO: write"""
        return toml_load_system_template(
            self.file_path(name) / NAMES.template_toml, self.user_str, name=name
        )

    def valid_path(self, path: Path):
        """TODO: write"""
        return (
            super().valid_path(path)
            and (path / NAMES.template_doc).exists()
            and (path / NAMES.template_toml).exists()
        )


macro_linker = _FileLinker(".sty", "macro file", "macro")
style_linker = _FileLinker(".sty", "style file", "style")
citation_linker = _FileLinker(".bib", "citation file", "citation")
template_linker = _TemplateLinker(DATA_PATH.template_dir, "", "template")

LINKER_MAP = {
    "citation": citation_linker,
    "macro": macro_linker,
    "style": style_linker,
    "template": template_linker,
}
