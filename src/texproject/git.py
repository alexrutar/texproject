from __future__ import annotations
import os
from typing import TYPE_CHECKING

import keyring

from .control import AtomicIterable, RuntimeClosure
from .term import Secret
from .process import _CmdRunCommand

if TYPE_CHECKING:
    from .base import RepoVisibility
    from .filesystem import ProjectPath
    from typing import Optional, Iterable, Dict
    from pathlib import Path


class CreateGithubRepo(AtomicIterable):
    def __init__(
        self,
        repo_name: str,
        description: str,
        visibility: RepoVisibility,
        wiki: bool,
        issues: bool,
    ) -> None:
        self._repo_name = repo_name
        self._description = description
        self._visibility = visibility
        self._wiki = wiki
        self._issues = issues

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        gh_command = [
            "gh",
            "repo",
            "create",
            "-d",
            self._description,
            "--source",
            str(proj_path.dir),
            "--remote",
            "origin",
            "--push",
            self._repo_name,
            "--" + self._visibility,
        ]

        if not self._wiki:
            gh_command.append("--disable-wiki")

        if not self._issues:
            gh_command.append("--disable-issues")

        yield _CmdRunCommand(gh_command).get_ato(proj_path, template_dict, state)


class WriteGithubApiToken(AtomicIterable):
    def __init__(self, repo_name: str):
        self._repo_name = repo_name

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
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
            yield _CmdRunCommand(
                [
                    "gh",
                    "secret",
                    "set",
                    "API_TOKEN_GITHUB",
                    "-b",
                    token,
                    "-r",
                    self._repo_name,
                ]
            ).get_ato(proj_path, template_dict, state)
