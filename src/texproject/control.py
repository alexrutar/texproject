"""TODO: write docstring"""
from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass, field
from functools import singledispatch
from itertools import repeat
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
import sys
from uuid import uuid1

import click

from .error import AbortRunner
from .filesystem import ProjectPath

if TYPE_CHECKING:
    from typing import Callable, Final, Iterable, Any
    from .filesystem import TemplateDict


@singledispatch
def _as_str(_) -> Optional[str]:
    return None


@_as_str.register
def _(msg: bytes) -> Optional[str]:
    return msg.decode("ascii")


@_as_str.register
def _(msg: str) -> Optional[str]:
    return msg


@dataclass
class RuntimeOutput:
    success: bool
    output: Optional[bytes | str] = None

    def message(self):
        return _as_str(self.output)


FAIL: Final = (False, lambda: RuntimeOutput(False))
SUCCESS: Final = (True, lambda: RuntimeOutput(True))


class TempDir:
    def __init__(self, temp_dir_name: str):
        self.path: Final = Path(temp_dir_name)

    def provision(self) -> Path:
        return self.path / uuid1().hex


class CommandRunner:
    def __init__(
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        dry_run=False,
        verbose=True,
        debug=False,
    ):
        self._proj_path: Final = proj_path
        self._template_dict: Final = template_dict
        self._dry_run = dry_run
        self._verbose = verbose
        self._debug = debug

    def atomic_outputs(
        self,
        command_iter: Iterable[AtomicIterable],
        state_init: Callable[[], dict[str, Any]] = lambda: {},
    ) -> Iterable[tuple[bool, RuntimeClosure]]:
        state = state_init()
        for at_iter in command_iter:
            with TemporaryDirectory() as temp_dir_str:
                temp_dir = TempDir(temp_dir_str)
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
            click.echo(rtc.message(), nl=False)
            rto = rtc.run()
            if self._verbose:
                if rto.success:
                    click.echo()
                else:
                    # overwrite the current line
                    click.echo("\x1b[1K\r", nl=False)
                    click.secho(click.unstyle(rtc.message()), fg="red", err=True)

                if rto.message() is not None:
                    click.echo(rto.message(), err=not rto.success)

            ret = rto.success and inferred_success
        if abort_on_failure and ret is False:
            raise AbortRunner("aborting on failure")
        return ret

    def execute(
        self,
        command_iter: Iterable[AtomicIterable],
        state_init: Callable[[], dict[str, str]] = lambda: {},
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
            click.echo()  # newline required since initial message print does not have it
            click.secho(
                f"Runner aborted with error message '{str(e)}'.",
                err=True,
                fg="red",
            )
            click.echo(e.stderr.decode("ascii"), err=True)
            sys.exit(1)


class RuntimeClosure:
    """RuntimeClosure is the return value of AtomicCommand: the idea is that
    AtomicCommand does some pre-processing to try to work out what has happened (and
    return a verbose message, and a best guess for the result), and then returns these
    values along with a (minimal) callable function which can be executed to perform
    changes (e.g. by running shell commands, or by changing the filesystem).
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
        self,
        proj_path: ProjectPath,
        template_dict: TemplateDict,
        state: dict,
        temp_dir: TempDir,
    ) -> Iterable[RuntimeClosure]:
        raise NotImplementedError("Atomic iterable must have a registed callable!")
