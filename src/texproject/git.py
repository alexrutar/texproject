from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass
import os

import keyring

from .control import AtomicIterable, RuntimeClosure, SUCCESS, FAIL
from .filesystem import JINJA_PATH
from .utils import run_command
from .template import JinjaTemplate
from .term import Secret, FORMAT_MESSAGE
import subprocess

if TYPE_CHECKING:
    from .base import RepoVisibility
    from .filesystem import ProjectPath, TemplateDict
    from typing import Iterable, Dict
    from pathlib import Path


def is_git_repo(path: Path):
    return (
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=path, capture_output=True
        ).returncode
        == 0
    )


def git_has_remote(path: Path):
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
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
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
                run_command(proj_path, command)


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
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        org = proj_path.config.github.get("org", None)
        if git_has_remote(proj_path.dir):
            yield RuntimeClosure(
                FORMAT_MESSAGE.error("Remote repository already exists!"), *FAIL
            )
        else:
            if org is not None:
                repo_name = f"{org}/{self.repo_name}"
            else:
                repo_name = self.repo_name
            gh_command = [
                "gh",
                "repo",
                "create",
                "-d",
                self.description,
                "--source",
                str(proj_path.dir),
                "--remote",
                "origin",
                "--push",
                repo_name,
                "--" + self.visibility,
            ]

            if not self.wiki:
                gh_command.append("--disable-wiki")

            if not self.issues:
                gh_command.append("--disable-issues")

            yield run_command(proj_path, gh_command)


@dataclass
class WriteGithubApiToken(AtomicIterable):
    repo_name: str

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        env_token = os.environ.get("API_TOKEN_GITHUB", None)
        if env_token is not None:
            token = Secret(env_token)
        try:
            params = proj_path.config.github["keyring"]
            user_token = keyring.get_password(params["entry"], params["username"])
            token = Secret(user_token)
        except KeyError:
            token = None

        if token is not None:
            yield run_command(
                proj_path,
                [
                    "gh",
                    "secret",
                    "set",
                    "API_TOKEN_GITHUB",
                    "-b",
                    token,
                    "-r",
                    self.repo_name,
                ],
            )


@dataclass
class GitignoreWriter(AtomicIterable):
    force: bool = False

    def __call__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: Dict,
        temp_dir: Path,
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
        state: Dict,
        temp_dir: Path,
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
        state: Dict,
        temp_dir: Path,
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
        state: Dict,
        temp_dir: Path,
    ) -> Iterable[RuntimeClosure]:
        yield JinjaTemplate(JINJA_PATH.build_latex, force=self.force).write(
            proj_path, template_dict, state, proj_path.build_latex
        )
