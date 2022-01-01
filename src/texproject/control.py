# atomic commands:
# - write_template_dict
# - write_template_with_info
# - linking stuff
# - removing files
# - creating files

# every atomic command must perform no actions until __call__'ed
# when called, must return an RuntimeClosure class

# all the stuff in this file causes changes to the filesystem

# use yield, yield from
# every top-level command returns a generator which can be consumed
from __future__ import annotations
from typing import List, Callable, Dict, Final, Iterable, Optional, Tuple
from .filesystem import ProjectPath
import click
from itertools import chain
from dataclasses import dataclass
from .error import AbortRunner


@dataclass
class RuntimeOutput:
    exit_status: bool
    output: Optional[bytes] = None

    def message(self):
        if self.output is not None:
            return self.output.decode("ascii")


FAIL: Final = (False, lambda: RuntimeOutput(False))
SUCCESS: Final = (True, lambda: RuntimeOutput(True))


class RuntimeClosure:
    """RuntimeClosure is the return value of AtomicCommand: the idea is that AtomicCommand
    does some pre-processing to try to work out what has happened (and return a verbose message,
    and a best guess for the result), and then returns these values along with a (minimal) callable
    function which can be executed to perform changes (e.g. by running shell commands, or by changing
    the filesystem).
    """

    # fix the typing here
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

    # todo: rename to inferred_success?
    def success(self) -> bool:
        return self._status

    def run(self) -> RuntimeOutput:
        # only allow running once!
        ret = self._callable()
        del self._callable
        return ret


# also include a "general information string", indicating what the sequence is doing
# todo: delete this thing!
class AtomicCommand:
    def get_ato(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict
    ) -> RuntimeClosure:
        raise NotImplementedError("Atomic command must have a registed callable!")


class AtomicIterable:
    def __call__(
        self, proj_path: ProjectPath, template_dict: Dict, state: Dict, temp_dir: Path
    ) -> Iterable[RuntimeClosure]:
        raise NotImplementedError("Atomic command must have a registed callable!")
