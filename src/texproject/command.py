"""TODO: write docstring"""
from __future__ import annotations
from typing import TYPE_CHECKING
import sys

from functools import update_wrapper
from pathlib import Path

import click

from .base import (
    SHUTIL_ARCHIVE_FORMATS,
    SHUTIL_ARCHIVE_SUFFIX_MAP,
    AddCommand,
    RemoveCommand,
    LinkMode,
    LinkCommand,
    ExportMode,
)
from .control import CommandRunner
from .filesystem import (
    ProjectPath,
    NAMES,
    TemplateDict,
    style_linker,
    macro_linker,
    citation_linker,
    template_linker,
)
from .git import (
    InitializeGitRepo,
    CreateGithubRepo,
    PrecommitWriter,
    GitignoreWriter,
    GitFileWriter,
    LatexBuildWriter,
)
from .utils import FileEditor, CleanProject
from .output import ArchiveWriter, LatexCompiler
from .template import (
    OutputFolderCreator,
    InfoFileWriter,
    TemplateDictLinker,
    NameSequenceLinker,
    PathSequenceLinker,
    ApplyModificationSequence,
    TemplateDictWriter,
)
from .term import FORMAT_MESSAGE

if TYPE_CHECKING:
    from click import Context
    from click.decorators import FC
    from .base import RepoVisibility
    from typing import Optional, Iterable, Literal, Callable, Any
    from .control import AtomicIterable


def _run_command(
    ctx: Context,
    template_dict: TemplateDict,
    f: Callable[..., Iterable[AtomicIterable]],
    *args: Any,
    **kwargs: Any,
) -> None:
    def state_constructor() -> dict:
        return {"template_modifications": []}

    CommandRunner(
        ctx.obj["proj_path"],
        template_dict,
        dry_run=ctx.obj["dry_run"],
        verbose=ctx.obj["verbose"],
        debug=ctx.obj["debug"],
    ).execute(ctx.invoke(f, *args, **kwargs), state_init=state_constructor)


def process_atoms_init(
    f: Callable[[str], Iterable[AtomicIterable]]
) -> Callable[[Context, str], None]:
    @click.pass_context
    def wrapper_with_template(ctx: Context, template: str) -> None:
        _run_command(ctx, TemplateDict.from_name(template), f, template)

    return update_wrapper(wrapper_with_template, f)


def process_atoms(
    load_template: bool = True,
) -> Callable[[Callable[..., Iterable[AtomicIterable]]], Callable[..., None]]:
    """Custom decorator which passes the object after performing some state verification
    on it."""

    def decorator(f: Callable[..., Iterable[AtomicIterable]]) -> Callable[..., None]:
        @click.pass_context
        def wrapper(ctx: Context, *args: Any, **kwargs: Any) -> None:
            if not load_template:
                template_dict = TemplateDict()
            else:
                try:
                    template_dict = TemplateDict(source=ctx.obj["proj_path"].template)
                except FileNotFoundError:
                    click.secho("error: not a texproject folder", err=True)
                    sys.exit(1)

            _run_command(ctx, template_dict, f, *args, **kwargs)

        return update_wrapper(wrapper, f)

    return decorator


@click.group()
@click.version_option(prog_name="tpr (texproject)")
@click.option(
    "-C",
    "proj_dir",
    default=".",
    show_default=True,
    help="working directory",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, writable=True, path_type=Path
    ),
)
@click.option(
    "-n",
    "--dry-run",
    "dry_run",
    is_flag=True,
    default=False,
    help="Describe changes but do not execute",
)
@click.option("--verbose/--silent", "-v/-V", "verbose", default=True, help="Be verbose")
@click.option("--debug/--no-debug", "debug", default=False, help="Debug mode")
@click.pass_context
def cli(
    ctx: Context, proj_dir: Path, dry_run: bool, verbose: bool, debug: bool
) -> None:
    """TexProject is a tool to help streamline the creation and distribution of files
    written in LaTeX.
    """
    ctx.obj = {
        "proj_path": ProjectPath(proj_dir),
        "dry_run": dry_run,
        "verbose": verbose,
        "debug": debug,
    }


@cli.command(short_help="Initialize a new project.")
@click.argument(
    "template",
    type=click.Choice(template_linker.list_names()),
    metavar="TEMPLATE",
)
@process_atoms_init
def init(template: str) -> Iterable[AtomicIterable]:
    """Initialize a new project in the working directory. The project is created using
    the template with name TEMPLATE and placed in the output folder OUTPUT.

    The working directory either must not exist or be an empty folder. Missing
    intermediate directories are automatically constructed.
    """
    yield OutputFolderCreator.with_abort(template=template)
    yield TemplateDictLinker()
    yield InfoFileWriter()


@cli.command()
@click.option(
    "--local", "config_file", flag_value="local", help="Edit local configuration."
)
@click.option(
    "--global",
    "config_file",
    flag_value="global",
    help="Edit global configuration.",
    default=True,
)
@process_atoms(load_template=False)
def config(config_file: Literal["local", "global"]) -> Iterable[AtomicIterable]:
    """Edit configuration files. This opens the corresponding file in your
    $EDITOR. By default, edit the global configuration file.
    """
    yield FileEditor(config_file)


def _link_option(mode: LinkMode) -> Callable[[FC], FC]:
    linker = {
        LinkMode.macro: macro_linker,
        LinkMode.citation: citation_linker,
        LinkMode.style: style_linker,
    }
    return click.option(
        f"--{mode}",
        f"{NAMES.convert_mode(mode)}",
        multiple=True,
        type=click.Choice(linker[mode].list_names()),
        help=f"{mode} file",
        show_default=False,
    )


def _path_option(mode: LinkMode) -> Callable[[FC], FC]:
    return click.option(
        f"--{mode}-path",
        f"{mode}_paths",
        multiple=True,
        type=click.Path(
            exists=True, file_okay=True, dir_okay=False, writable=False, path_type=Path
        ),
        help=f"{mode} file path",
    )


@cli.command("import")
@_link_option(LinkMode.macro)
@_link_option(LinkMode.citation)
@_link_option(LinkMode.style)
@_path_option(LinkMode.macro)
@_path_option(LinkMode.citation)
@_path_option(LinkMode.style)
@click.option(
    "--gitignore",
    "gitignore",
    is_flag=True,
    default=False,
    help="auto-generated gitignore",
)
@click.option(
    "--pre-commit",
    "pre_commit",
    is_flag=True,
    default=False,
    help="auto-generated pre-commit",
)
@click.option(
    "--build",
    "build",
    is_flag=True,
    default=False,
    help="latex build workflow",
)
@process_atoms(load_template=False)
def import_(
    macros: Iterable[str],
    citations: Iterable[str],
    styles: Iterable[str],
    macro_paths: Iterable[Path],
    citation_paths: Iterable[Path],
    style_paths: Iterable[Path],
    gitignore: bool,
    pre_commit: bool,
    build: bool,
) -> Iterable[AtomicIterable]:
    """Import macro, citation, and style files. This command will replace existing
    files. Note that this command does not import the files into the main .tex file.

    The --{macro, citation, style}-path options allow macro and citation files to be
    specified as paths to existing files. This enables imports which are not installed
    in the texproject data directory.
    """
    for mode, names, paths in [
        (LinkMode.macro, macros, macro_paths),
        (LinkMode.citation, citations, citation_paths),
        (LinkMode.style, styles, style_paths),
    ]:
        yield NameSequenceLinker(LinkCommand.replace, mode, names)
        yield PathSequenceLinker(LinkCommand.replace, mode, paths)

    if gitignore:
        yield GitignoreWriter(force=True)
    if pre_commit:
        yield PrecommitWriter(force=True)
    if build:
        yield LatexBuildWriter(force=True)


@cli.command()
@click.option(
    "--pdf",
    "pdf",
    help="write .pdf to file",
    type=click.Path(exists=False, writable=True, path_type=Path),
)
@click.option(
    "--logfile",
    help="write .log to file",
    type=click.Path(exists=False, writable=True, path_type=Path),
)
@process_atoms()
def validate(pdf: Optional[Path], logfile: Optional[Path]) -> Iterable[AtomicIterable]:
    """Check for compilation errors. Compilation is performed by the 'latexmk' command.
    Save the resulting pdf with the '--pdf' argument, or the log file with the
    '--logfile' argument. These options, if specified, will overwrite existing files.
    """
    yield LatexCompiler(
        output_map={
            k: v for k, v in {".pdf": pdf, ".log": logfile}.items() if v is not None
        }
    )


@cli.command(short_help="Create compressed exports.")
@click.option(
    "--format",
    "compression",
    type=click.Choice(SHUTIL_ARCHIVE_FORMATS, case_sensitive=False),
    help="compression mode",
)
@click.option(
    "--mode",
    "mode",
    type=click.Choice(ExportMode),  # type: ignore
    default="source",
    show_default=True,
    help="specify what to export",
)
@click.argument("output", type=click.Path(exists=False, writable=True, path_type=Path))
@process_atoms()
def archive(
    compression: str, mode: ExportMode, output: Path
) -> Iterable[AtomicIterable]:
    """Create a compressed export with name OUTPUT. If the 'arxiv' or 'build' options
    are chosen, 'latexmk' is used to compile additional required files.

    The --format option specifies the format of the resulting archive. If unspecified,
    the format is inferred from the resulting filename if possible. Otherwise, the
    output format is 'tar'.

    If the format is not inferred from the filename, the archive file suffix is appended
    automatically.

    \b
    Archive modes:
     arxiv: format source files for arxiv (https://arxiv.org)
     build: compile the .pdf and export
     source: export

    \b
    Compression:
     bztar: bzip2'ed tar-file
     gztar: gzip'ed tar-file
     tar: uncompressed tar-file
     xztar: xz'ed tar-file
     zip: ZIP file

    Note that some compression modes may not be available on your system. The available
    options are listed below.
    """
    if compression is None:
        try:
            compression = SHUTIL_ARCHIVE_SUFFIX_MAP[output.suffix]
            output = output.parent / output.stem
        except KeyError:
            compression = "tar"

    yield ArchiveWriter(compression, output, fmt=mode)


@cli.group()
def template() -> None:
    """Modify the template dictionary."""


@template.command()
@_link_option(LinkMode.macro)
@_link_option(LinkMode.citation)
@_link_option(LinkMode.style)
@click.option(
    "--append/--prepend", "-a/-p", "append", default=True, help="append or prepend"
)
@process_atoms()
def add(
    macros: list[str],
    citations: list[str],
    styles: list[str],
    append: bool,
) -> Iterable[AtomicIterable]:
    """Add entries to the template dictionary. Existing entries with the same name will
    be replaced. To specify locations other than the end or beginning, run `tpr template
    edit`.
    """
    for mode, names in [
        (LinkMode.macro, macros),
        (LinkMode.citation, citations),
        (LinkMode.style, styles),
    ]:
        yield ApplyModificationSequence(
            AddCommand(mode, name, append) for name in names
        )
    yield TemplateDictWriter()
    yield TemplateDictLinker()
    yield InfoFileWriter()


@template.command()
@_link_option(LinkMode.macro)
@_link_option(LinkMode.citation)
@_link_option(LinkMode.style)
@process_atoms()
def remove(
    macros: list[str], citations: list[str], styles: list[str]
) -> Iterable[AtomicIterable]:
    """Remove entries from the template dictionary."""
    for mode, names in [
        (LinkMode.macro, macros),
        (LinkMode.citation, citations),
        (LinkMode.style, styles),
    ]:
        yield ApplyModificationSequence(RemoveCommand(mode, name) for name in names)
    yield TemplateDictWriter()
    yield TemplateDictLinker()
    yield InfoFileWriter()


@template.command()
@process_atoms()
def edit() -> Iterable[AtomicIterable]:
    """Open the template dictionary in your $EDITOR."""
    yield FileEditor("template")
    yield TemplateDictLinker()
    yield InfoFileWriter()


@cli.group()
def git() -> None:
    """Manage git and GitHub repositories."""


@git.command("init")
@click.option(
    "--repo-name",
    "repo_name",
    prompt=FORMAT_MESSAGE.prompt("Repository name"),
    help="Name of the repository",
    type=str,
)
@click.option(
    "--repo-description",
    "repo_desc",
    prompt=FORMAT_MESSAGE.prompt("Repository description"),
    help="Repository description",
    type=str,
)
@click.option(
    "--repo-visibility",
    "vis",
    prompt=FORMAT_MESSAGE.prompt("Repository visibility"),
    type=click.Choice(["public", "private"]),
    help="Specify public or private repository",
    default="private",
)
@click.option(
    "--wiki/--no-wiki",
    "wiki",
    prompt=FORMAT_MESSAGE.prompt("Include wiki?"),
    help="Create wiki",
    default=False,
)
@click.option(
    "--issues/--no-issues",
    "issues",
    prompt=FORMAT_MESSAGE.prompt("Include issues?"),
    help="Create issues page",
    default=False,
)
@process_atoms(load_template=False)
def git_init(
    repo_name: str,
    repo_desc: str,
    vis: RepoVisibility,
    wiki: bool,
    issues: bool,
) -> Iterable[AtomicIterable]:
    """Initialize git and a corresponding GitHub repository. If called with no options,
    this command will interactively prompt you in order to initialize the repo
    correctly. This command also creates a GitHub action with automatically compiles and
    releases the main .pdf file for tagged commits.
    """
    yield GitFileWriter()
    yield InitializeGitRepo.with_abort()
    yield CreateGithubRepo.with_abort(repo_name, repo_desc, vis, wiki, issues)


@git.command("init-files")
@click.option("--force/--no-force", "-f/-F", default=False, help="overwrite files")
@process_atoms()
def init_files(force: bool) -> Iterable[AtomicIterable]:
    """Create the git repository files. This does not create a local or remote git
    repository.
    """
    yield GitFileWriter(force=force)


@cli.group()
def util() -> None:
    """Miscellaneous utilities."""


@util.command()
@process_atoms()
def clean() -> Iterable[AtomicIterable]:
    """Clean the project directory. This deletes any template files that are not
    currently loaded in the template dictionary.
    """
    yield CleanProject()


@template.command("util")
@click.option("--force/--no-force", "-f/-F", default=False, help="overwrite files")
@process_atoms()
def refresh(force: bool) -> Iterable[AtomicIterable]:
    """Reload template files. If --force is specified, overwrite local template files
    with new versions from the template repository, if possible.
    """
    yield TemplateDictLinker(LinkCommand.replace if force else LinkCommand.copy)
    yield InfoFileWriter()


@util.command()
def show_config() -> None:
    """"""
    from . import defaults
    from importlib import resources

    click.echo(resources.read_text(defaults, "config.toml"), nl=False)


@cli.command("show")
@_link_option(LinkMode.macro)
@_link_option(LinkMode.citation)
@_link_option(LinkMode.style)
@_path_option(LinkMode.macro)
@_path_option(LinkMode.citation)
@_path_option(LinkMode.style)
@click.option(
    "--gitignore",
    "gitignore",
    is_flag=True,
    default=False,
    help="auto-generated gitignore",
)
@click.option(
    "--pre-commit",
    "pre_commit",
    is_flag=True,
    default=False,
    help="auto-generated pre-commit",
)
@click.option(
    "--diff/--no-diff",
    "diff",
    default=False,
    help="show differences to current file",
)
@process_atoms(load_template=False)
def show(
    macros: Iterable[str],
    citations: Iterable[str],
    styles: Iterable[str],
    macro_paths: Iterable[Path],
    citation_paths: Iterable[Path],
    style_paths: Iterable[Path],
    gitignore: bool,
    pre_commit: bool,
    diff: bool,
) -> Iterable[AtomicIterable]:
    """Print macro, citation, and style files to STDOUT. The --diff option displays
    the difference between the file and the current file which would be overwritten if
    imported.

    The --macro-path and --citation-path allow macro and citation files to be specified
    as paths to existing files. For example, this enables imports which are not
    installed in the texproject data directory.
    """
    cmd = LinkCommand.diff if diff else LinkCommand.show
    for mode, names, paths in [
        (LinkMode.macro, macros, macro_paths),
        (LinkMode.citation, citations, citation_paths),
        (LinkMode.style, styles, style_paths),
    ]:
        yield NameSequenceLinker(cmd, mode, names)
        yield PathSequenceLinker(cmd, mode, paths)

    if gitignore:
        yield GitignoreWriter(force=True)
    if pre_commit:
        yield PrecommitWriter(force=True)


@cli.command("list")
@click.argument(
    "res_class", type=click.Choice([e.value for e in LinkMode] + ["template"])
)
def list_(res_class: Literal["macro", "citation", "style", "template"]) -> None:
    """Retrieve program and template information."""
    linker_map = {
        LinkMode.citation.value: citation_linker,
        LinkMode.macro.value: macro_linker,
        LinkMode.style.value: style_linker,
        "template": template_linker,
    }

    click.echo("\n".join(linker_map[res_class].list_names()))
