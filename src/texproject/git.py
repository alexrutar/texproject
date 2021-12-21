from __future__ import annotations
import os
from typing import TYPE_CHECKING

import keyring

from .process import subproc_run
from .term import Secret

if TYPE_CHECKING:
    from .base import RepoVisibility
    from .filesystem import ProjectInfo


class GHRepo:
    def __init__(self, proj_info: ProjectInfo, repo_name: str):
        self.proj_info = proj_info
        self.name = repo_name

    def create(
        self,
        description: str,
        visibility: RepoVisibility = "private",
        wiki: bool = False,
        issues: bool = False,
    ):
        gh_command = [
            "gh",
            "repo",
            "create",
            "-d",
            description,
            "--source",
            str(self.proj_info.dir),
            "--remote",
            "origin",
            "--push",
            self.name,
            "--" + visibility,
        ]

        if not wiki:
            gh_command.append("--disable-wiki")

        if not issues:
            gh_command.append("--disable-issues")

        subproc_run(self.proj_info, gh_command)

    def write_api_token(self) -> None:
        env_token = os.environ.get("API_TOKEN_GITHUB", None)
        if env_token is not None:
            token = Secret(env_token)
        try:
            params = self.proj_info.config.github["keyring"]
            user_token = keyring.get_password(params["entry"], params["username"])
            token = Secret(user_token)
        except KeyError:
            token = None

        if token is not None:
            subproc_run(
                self.proj_info,
                [
                    "gh",
                    "secret",
                    "set",
                    "API_TOKEN_GITHUB",
                    "-b",
                    token,
                    "-r",
                    self.name,
                ],
            )
