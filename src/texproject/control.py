"""TODO: write docstring"""
from __future__ import annotations
from typing import TYPE_CHECKING

from types import SimpleNamespace
from dataclasses import dataclass, astuple, field, InitVar
from itertools import repeat
from pathlib import Path
import tempfile
import sys

import click

from .error import AbortRunner
from .filesystem import ProjectPath

if TYPE_CHECKING:
    from typing import Callable, Dict, Final, Iterable, Optional, Any, Tuple


@dataclass
class RuntimeOutput:
    exit_status: bool
    output: Optional[bytes] = None

    def message(self):
        if self.output is not None:
            return self.output.decode("ascii")


FAIL: Final = (False, lambda: RuntimeOutput(False))
SUCCESS: Final = (True, lambda: RuntimeOutput(True))


class CommandRunner:
    def __init__(
        self,
        proj_path: ProjectPath,
        template_dict: Optional[Dict],
        dry_run=False,
        verbose=True,
    ):
        self._proj_path: Final = proj_path
        self._template_dict: Final = template_dict if template_dict is not None else {}
        self._dry_run = dry_run
        self._verbose = verbose

    def atomic_outputs(
        self,
        command_iter: Iterable[AtomicIterable],
        state_init: Callable[[], Dict[str, Any]] = lambda: {},
    ) -> Iterable[Tuple[bool, RuntimeClosure]]:
        state = state_init()
        for at_iter in command_iter:
            with tempfile.TemporaryDirectory() as temp_dir_str:
                temp_dir = Path(temp_dir_str)
                yield from zip(
                    repeat(at_iter.abort_on_failure),
                    at_iter(self._proj_path, self._template_dict, state, temp_dir),
                )

    def process_output(self, rtc: RuntimeClosure, abort_on_failure: bool = False):
        inferred_success = rtc.success()
        if self._dry_run:
            click.echo(rtc.message())
            ret = inferred_success
        else:
            success, out = astuple(rtc.run())
            if self._verbose:
                if success:
                    click.echo(rtc.message())
                else:
                    click.secho(click.unstyle(rtc.message()), fg="red", err=True)

                if out is not None:
                    click.echo(out.decode("ascii"), err=not success)

            ret = success and inferred_success
        if abort_on_failure and ret is False:
            raise AbortRunner("aborting on failure")
        return ret

    def execute(
        self,
        command_iter: Iterable[AtomicIterable],
        state_init: Callable[[], Dict[str, str]] = lambda: {},
    ):
        try:
            outputs = [
                self.process_output(rtc, abort_on_failure=abort_on_failure)
                for abort_on_failure, rtc in self.atomic_outputs(
                    command_iter, state_init
                )
            ]
            if not all(outputs):
                click.secho(
                    "\nError: Runner completed, but one of the commands failed!",
                    err=True,
                    fg="red",
                )
                sys.exit(1)

        except AbortRunner as e:
            click.secho(
                f"Runner aborted with error message '{str(e)}'.",
                err=True,
                fg="red",
            )
            click.echo(e.stderr.decode("ascii"), err=True)
            sys.exit(1)


class RuntimeClosure:
    """RuntimeClosure is the return value of AtomicCommand: the idea is that AtomicCommand
    does some pre-processing to try to work out what has happened (and return a verbose message,
    and a best guess for the result), and then returns these values along with a (minimal) callable
    function which can be executed to perform changes (e.g. by running shell commands, or by changing
    the filesystem).
    """

    def __init__(
        self,
        message: str,
        status: bool,
        callable: Callable[[], RuntimeOutput],
    ):
        self._message = message
        self._status = status
        self._callable = callable

    def message(self) -> str:
        return self._message

    def success(self) -> bool:
        return self._status

    def run(self) -> RuntimeOutput:
        # only allow running once
        ret = self._callable()
        del self._callable
        return ret


@dataclass
class AtomicIterable:
    abort_on_failure: bool = field(default=False, init=False)

    @classmethod
    def with_abort(cls, *args, **kwargs):
        self = cls(*args, **kwargs)
        self.abort_on_failure = True
        return self

    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        raise NotImplementedError("Atomic iterable must have a registed callable!")
