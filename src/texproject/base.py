from __future__ import annotations
from typing import TYPE_CHECKING

from pathlib import Path
import shutil

if TYPE_CHECKING:
    from typing import Final, Iterable, Literal, Tuple, TypeVar

    LinkMode = TypeVar(
        "LinkMode", Literal["citation"], Literal["style"], Literal["macro"]
    )
    ModCommand = TypeVar(
        "ModCommand",
        Tuple[
            Literal["citation"] | Literal["style"] | Literal["macro"],
            Literal["remove"],
            str,
        ],
        Tuple[
            Literal["citation"] | Literal["style"] | Literal["macro"],
            Literal["add"],
            str,
            int,
        ],
        Tuple[
            Literal["citation"] | Literal["style"] | Literal["macro"],
            Literal["update"],
            str,
            str,
        ],
    )
    RepoVisibility = TypeVar("RepoVisibility", Literal["public"], Literal["private"])


_suffix_map_helper = {
    ".tar": "tar",
    ".tar.bz": "bztar",
    ".tar.gz": "gztar",
    ".tar.xz": "xztar",
    ".zip": "zip",
}
SHUTIL_ARCHIVE_FORMATS: Final = [ar[0] for ar in shutil.get_archive_formats()]
SHUTIL_ARCHIVE_SUFFIX_MAP: Final = {
    k: v for k, v in _suffix_map_helper.items() if v in SHUTIL_ARCHIVE_FORMATS
}


def constant(func):
    """TODO: write"""

    def fset(self, value):
        del self, value
        raise AttributeError("Cannot change constant values")

    def fget(self):
        return func(self)

    return property(fget, fset)


class _Naming:
    """TODO: write"""

    @constant
    def template_toml(self) -> str:
        """TODO: write"""
        return "template.toml"

    @constant
    def template_doc(self) -> str:
        """TODO: write"""
        return "document.tex"

    def convert_mode(self, mode: LinkMode) -> str:
        return {"citation": "citations", "style": "styles", "macro": "macros"}[mode]

    def resource_subdir(self, mode: LinkMode) -> Path:
        return Path(
            {"citation": "citations", "style": "styles", "macro": "macros"}[mode]
        )

    @constant
    def modes(self) -> tuple[str, str, str]:
        return ("citation", "style", "macro")

    def get_name(self, template_file_path: Path):
        fn = template_file_path.stem
        if fn.startswith("local-"):
            return "-".join(fn.split("-")[1:])
        else:
            raise Exception("Invalid template file path!")

    def existing_template_files(
        self, working_dir: Path, mode: LinkMode
    ) -> Iterable[Tuple[Path, str]]:
        for path in (working_dir / NAMES.resource_subdir(mode)).glob("local-*"):
            yield (path, NAMES.get_name(path))

    def rel_data_path(self, name: str, mode: LinkMode) -> Path:
        # prepend local- to minimize name collisions with existing packages
        return self.resource_subdir(mode) / ("local-" + name)

    @constant
    def prefix_separator(self) -> str:
        """TODO: write"""
        return "-"


NAMES: Final = _Naming()
