from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass


from .control import AtomicIterable, RuntimeClosure, SUCCESS, FAIL
from .error import AbortRunner
from .filesystem import JINJA_PATH
from .utils import run_command
from .template import JinjaTemplate
from .term import FORMAT_MESSAGE
import subprocess

if TYPE_CHECKING:
    from .base import RepoVisibility
    from .control import TempDir
    from .filesystem import ProjectPath, TemplateDict
    from typing import Iterable
    from pathlib import Path


def is_git_repo(path: Path) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=path, capture_output=True
        ).returncode
        == 0
    )


def git_has_remote(path: Path) -> bool:
    return (
        subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=path,
            capture_output=True,
        ).returncode
        == 0
    )


@dataclass
class InitializeGitRepo(AtomicIterable):
    def __call__(
        self,
        proj_path: ProjectPath,
        _template_dict: TemplateDict,
        _state: dict,
        _temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        if is_git_repo(proj_path.dir):
            yield RuntimeClosure(
                FORMAT_MESSAGE.info("Using existing git repository"), *SUCCESS
            )
        else:
            for command in [
                ["git", "init"],
                ["git", "add", "-A"],
                ["git", "commit", "-m", "Initialize new texproject repository."],
            ]:
                yield run_command(proj_path, command)


@dataclass
class CreateGithubRepo(AtomicIterable):
    repo_name: str
    description: str
    visibility: RepoVisibility
    wiki: bool
    issues: bool

    def __call__(
        self,
        proj_path: ProjectPath,
        _template_dict: TemplateDict,
        _state: dict,
        _temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        if git_has_remote(proj_path.dir):
            yield RuntimeClosure(
                FORMAT_MESSAGE.error("Remote repository already exists!"), *FAIL
            )
        else:
            gh_command = [
                "gh",
                "repo",
                "create",
                "--d",
                self.description,
                "--source",
                str(proj_path.dir),
                "--remote",
                "origin",
                "--push",
                _format_repo_name(self.repo_name, proj_path),
                "--" + self.visibility,
            ]

            if not self.wiki:
                gh_command.append("--disable-wiki")

            if not self.issues:
                gh_command.append("--disable-issues")

            yield run_command(proj_path, gh_command)


def _format_repo_name(repo: str, proj_path: ProjectPath) -> str:
    org = proj_path.config.github.get("org", None)
    repo_parts = len(repo.split("/"))
    if repo_parts == 2:
        return repo
    elif repo_parts == 1 and org is not None:
        return f"{org}/{repo}"
    else:
        raise AbortRunner("Invalid remote repository name!")


def get_repo_name_from_remote_url(path: Path) -> str:
    # todo: fix this!
    url_ret = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"], cwd=path, capture_output=True
    )
    if url_ret.returncode != 0:
        raise AbortRunner("Could not read remote repository!")
    url = url_ret.stdout.decode("ascii").strip()
    if url.startswith("git@github.com:") and url.endswith(".git"):
        return url[15:-4]
    else:
        raise AbortRunner("Could not determine remote repository name!")


@dataclass
class GitignoreWriter(AtomicIterable):
    force: bool = False

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: dict,
        _temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        yield JinjaTemplate(JINJA_PATH.gitignore, force=self.force).write(
            proj_path, template_dict, state, proj_path.gitignore
        )


@dataclass
class PrecommitWriter(AtomicIterable):
    force: bool = False

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: dict,
        _temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        yield JinjaTemplate(
            JINJA_PATH.pre_commit,
            executable=True,
            force=self.force,
        ).write(proj_path, template_dict, state, proj_path.pre_commit)


@dataclass
class GitFileWriter(AtomicIterable):
    force: bool = False

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: dict,
        _temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        for template, target in [
            (
                JinjaTemplate(JINJA_PATH.gitignore, force=self.force),
                proj_path.gitignore,
            ),
            (
                JinjaTemplate(JINJA_PATH.build_latex, force=self.force),
                proj_path.build_latex,
            ),
            (
                JinjaTemplate(
                    JINJA_PATH.pre_commit,
                    executable=True,
                    force=self.force,
                ),
                proj_path.pre_commit,
            ),
        ]:
            yield template.write(proj_path, template_dict, state, target)


@dataclass
class LatexBuildWriter(AtomicIterable):
    force: bool

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: dict,
        _temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        yield JinjaTemplate(JINJA_PATH.build_latex, force=self.force).write(
            proj_path, template_dict, state, proj_path.build_latex
        )
