"""TODO: write"""
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Optional, NoReturn
    from subprocess import CalledProcessError
    from pathlib import Path

# def assert_never(value: NoReturn) -> NoReturn:
def assert_never(value) -> NoReturn:
    assert False, f'Unhandled value: {value} ({type(value).__name__})'

class SubcommandError(Exception):
    """TODO: write"""
    def __init__(self, proc_error: CalledProcessError):
        self.message = f"Subcommand returned exit code {proc_error.returncode}."
        self.cmd = proc_error.cmd
        self.stdout = proc_error.stdout.decode('ascii')
        self.stderr = proc_error.stderr.decode('ascii')
        super().__init__(self.message)

class LaTeXCompileError(Exception):
    """TODO: write"""
    def __init__(self, message:str = "Project compilation failed!"):
        self.message = message
        super().__init__(message)

class BasePathError(Exception):
    """TODO: write"""
    def __init__(self, path: Path, message:str = "Error involving path."):
        self.path = path
        self.message = message
        super().__init__(message)

class DataMissingError(BasePathError):
    """TODO: write"""

class TemplateDataMissingError(DataMissingError):
    """TODO: write"""
    def __init__(self, path: Path, user_str: str, name:Optional[str] = None):
        if name is not None:
            message = f"The {user_str} '{name}' does not exist."
        else:
            message = f"The {user_str} does not exist."
        super().__init__(path, message=message)

class SystemDataMissingError(DataMissingError):
    """TODO: write"""
    def __init__(self, path: Path):
        message = ("System data files are missing or not up to date.")

        super().__init__(path, message=message)

class ProjectDataMissingError(DataMissingError):
    """TODO: write"""

class ProjectMissingError(BasePathError):
    """TODO: write"""
    def __init__(self, path: Path):
        message = "The working directory is not a valid project."
        super().__init__(path, message=message)

class ProjectExistsError(BasePathError):
    """TODO: write"""
    def __init__(self, path: Path):
        message = "Conflicting files already exist in the working directory."
        super().__init__(path, message=message)

class GitMissingError(BasePathError):
    """TODO: write"""
    def __init__(self, path: Path):
        message = "The working directory is not a valid git repository."
        super().__init__(path, message=message)

class GitExistsError(BasePathError):
    """TODO: write"""
    def __init__(self, path: Path):
        message = "Conflicting git files already exist in the working directory."
        super().__init__(path, message=message)
