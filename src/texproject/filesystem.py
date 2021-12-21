"""TODO: write"""
from __future__ import annotations
import contextlib
import errno
from importlib import resources
from pathlib import Path
import shutil
from typing import TYPE_CHECKING
import uuid

import pytomlpp as toml
from xdg import XDG_DATA_HOME, XDG_CONFIG_HOME

from .base import NAMES, constant
from .error import (
    BasePathError,
    ProjectExistsError,
    ProjectDataMissingError,
    ProjectMissingError,
    TemplateDataMissingError,
    SystemDataMissingError,
    GitExistsError,
    GitMissingError,
)
from .term import link_echo, rm_echo

if TYPE_CHECKING:
    from .base import Modes
    from typing import Optional, Tuple, Generator, List, Dict

# todo: do something else with this
def verbose_unlink(proj_info: ProjectInfo, path: Path):
    if proj_info.verbose and path.exists():
        rm_echo(path)
    if not proj_info.dry_run:
        try:
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
        except Exception as err:
            # todo: better error here
            print(f"Failed to delete '{path}'. Reason: {err}")


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

    # iterate over all keys in all dicts being merged
    for k in set().union(*[set(dct.keys()) for dct in dcts]):

        # for a specific key, we only want the values containing that key
        dcts_with_key = [dct[k] for dct in dcts if k in dct.keys()]

        # if there's only one, or one of the items is not a dict, the last value overrides
        if len(dcts_with_key) == 1 or any(
            not isinstance(dct, dict) for dct in dcts_with_key
        ):
            yield (k, dcts_with_key[-1])

        # otherwise, recurse
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
            toml.loads(resources.read_text(__package__, "config_defaults.toml")),
            toml_load(self.global_path, missing_ok=True),
            toml_load(self.local_path, missing_ok=True),
        )
        self.user = self._dct["user"]
        self.render = self._dct["render"]
        self.process = self._dct["process"]
        self.github = self._dct["github"]

    def set_no_hidden(self) -> None:
        """TODO: write"""
        # TODO: maybe do other stuff
        self.render["project_data_folder"] = self.render["project_data_folder"].lstrip(
            "."
        )

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
    def default_template(self) -> Path:
        """TODO: write"""
        return self.data_dir / "config" / "default_template.toml"

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
        return Path("templates", name, NAMES.template_doc)

    @constant
    def _template_resource_dir(self) -> Path:
        """TODO: write"""
        return Path("resources", "other")

    @constant
    def project_macro(self) -> Path:
        """TODO: write"""
        return self._template_resource_dir / "project_macro_file.tex"

    @constant
    def gitignore(self) -> Path:
        """TODO: write"""
        return self._template_resource_dir / "gitignore"

    @constant
    def build_latex(self) -> Path:
        """TODO: write"""
        return self._template_resource_dir / "build_latex.yml"

    @constant
    def pre_commit(self) -> Path:
        """TODO: write"""
        return self._template_resource_dir / "pre-commit"

    @constant
    def classinfo(self) -> Path:
        """TODO: write"""
        return self._template_resource_dir / "classinfo.tex"

    @constant
    def bibinfo(self) -> Path:
        """TODO: write"""
        return self._template_resource_dir / "bibinfo.tex"

    @constant
    def bibliography(self) -> Path:
        """TODO: write"""
        return self._template_resource_dir / "bibliography.tex"

    @constant
    def arxiv_autotex(self) -> Path:
        """TODO: write"""
        return self._template_resource_dir / "arxiv_autotex.txt"


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

    def validate(self, exists=True) -> None:
        """TODO: write"""
        if not exists and any(path.exists() for path in self.rootfiles):
            raise ProjectExistsError(self.working_dir)
        if exists and any(not path.exists() for path in self.minimal_files):
            raise ProjectMissingError(self.working_dir)

    def validate_git(self, exists=True) -> None:
        """TODO: write"""
        if not exists and any(path.exists() for path in self.gitfiles):
            raise GitExistsError(self.working_dir)
        if exists and any(not path.exists() for path in self.minimal_gitfiles):
            raise GitMissingError(self.working_dir)

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

    @constant
    def gitfiles(self) -> Tuple[Path, Path, Path]:
        """TODO: write"""
        return (self.pre_commit, self.github_home, self.gitignore)

    @constant
    def minimal_gitfiles(self) -> Tuple[Path]:
        """TODO: write"""
        return (self.git_home,)

    @constant
    def rootfiles(self) -> Tuple[Path, Path, Path]:
        """TODO: write"""
        return (self.main, self.project_macro, self.data_dir)

    @constant
    def minimal_files(self) -> Tuple[Path, Path]:
        """TODO: write"""
        return (self.main, self.data_dir)

    def mk_data_dir(self):
        for mode in NAMES.modes:
            (self.data_dir / NAMES.resource_subdir(mode)).mkdir(
                exist_ok=True, parents=True
            )

    @contextlib.contextmanager
    def temp_subpath(self) -> Generator:
        """TODO: write"""
        self.temp_dir.mkdir(exist_ok=True)
        path = self.temp_dir / uuid.uuid1().hex
        try:
            yield path
        finally:
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
            except Exception as err:
                # todo: better error here
                print(f"Failed to delete '{path}'. Reason: {err}")

    def clear_temp(self) -> None:
        """TODO: write"""
        if self.temp_dir.exists():
            for file_path in self.temp_dir.iterdir():
                try:
                    if file_path.is_file() or file_path.is_symlink():
                        file_path.unlink()
                    elif file_path.is_dir():
                        shutil.rmtree(file_path)
                except Exception as err:
                    # todo: better error here
                    print(f"Failed to delete '{file_path}'. Reason: {err}")


class ProjectInfo(ProjectPath):
    """TODO: write"""

    def __init__(self, proj_dir: Path, dry_run: bool, verbose: bool):
        """TODO: write"""
        self.dry_run = dry_run
        self.force = False
        self.verbose = verbose or dry_run  # always verbose during dry_run
        super().__init__(proj_dir)


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

    def __init__(self, suffix: str, user_str: str, mode: Modes):
        """TODO: write"""
        super().__init__(
            DATA_PATH.resource_dir / NAMES.resource_subdir(mode), suffix, user_str
        )
        self.mode = mode  # type: Modes

    def link_path(
        self,
        path: Path,
        rel_path: Path,
        force: bool = False,
        silent_fail: bool = True,
        verbose=False,
        dry_run=False,
    ) -> bool:
        source_path = path.resolve()
        if source_path.suffix != self.suffix:
            raise BasePathError(
                source_path, message=f"Filetype '{source_path.suffix}' is invalid!"
            )
        target_path = rel_path / NAMES.rel_data_path(source_path.name, self.mode)

        return self._link_helper(
            source_path,
            target_path,
            rel_path,
            str(path),
            force=force,
            silent_fail=silent_fail,
            verbose=verbose,
            dry_run=dry_run,
        )

    def link_name(
        self,
        name: str,
        rel_path: Path,
        force: bool = False,
        silent_fail: bool = True,
        verbose=False,
        dry_run=False,
    ) -> bool:
        """Return True if the link succeeds (either bc exists, or copied in), and False otherwise"""
        source_path = self.file_path(name).resolve()
        target_path = rel_path / NAMES.rel_data_path(name + self.suffix, self.mode)

        return self._link_helper(
            source_path,
            target_path,
            rel_path,
            name,
            force=force,
            silent_fail=silent_fail,
            verbose=verbose,
            dry_run=dry_run,
        )

    def _link_helper(
        self,
        source_path: Path,
        target_path: Path,
        rel_path: Path,
        echo_name: str,
        force: bool = False,
        silent_fail: bool = True,
        verbose=False,
        dry_run=False,
    ) -> bool:

        if not (source_path.exists() or target_path.exists()):
            if verbose:
                link_echo(self, echo_name, rel_path, mode="fail")
            return False
            # raise TemplateDataMissingError(
            #         source_path,
            #         user_str=self.user_str,
            #         name=name)

        if target_path.exists() and not force:
            if verbose:
                link_echo(self, echo_name, rel_path, mode="exists")
            if silent_fail:
                return True
            raise FileExistsError(
                errno.EEXIST, "Link target already exists", str(target_path.resolve())
            )

        # only print the message if the target path doesn't exist, or it if does and
        # forced replace
        # todo: same pattern as write_template (abstract out?)
        if verbose:
            if target_path.exists():
                link_echo(self, echo_name, rel_path, mode="overwrite")
            else:
                link_echo(self, echo_name, rel_path, mode="new")

        if not dry_run:
            shutil.copyfile(str(source_path), str(target_path.resolve()))
            return True
        return False


def _load_default_template() -> Dict:
    """TODO: write"""
    try:
        default_template = toml_load(DATA_PATH.default_template)
    except FileNotFoundError as err:
        raise SystemDataMissingError(DATA_PATH.default_template) from err
    return default_template


def toml_load_local_template(path: Path) -> Dict:
    """TODO: write"""
    default_template = _load_default_template()
    try:
        template = toml_load(path)
    except FileNotFoundError as err:
        raise ProjectDataMissingError(
            path, message="The local template file is missing."
        ) from err
    return {**default_template, **template}


def toml_load_system_template(path: Path, user_str: str, name: Optional[str] = None):
    """TODO: write"""
    default_template = _load_default_template()
    try:
        template = toml_load(path)
    except FileNotFoundError as err:
        raise TemplateDataMissingError(path, user_str=user_str, name=name) from err
    return {**default_template, **template}


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
