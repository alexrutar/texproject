"""TODO: write docstring"""
from __future__ import annotations
from pathlib import Path
import sys
from typing import TYPE_CHECKING

import click

from . import __version__, __repo__
from .error import BasePathError, SubcommandError, LaTeXCompileError, assert_never
from .export import create_archive
from .filesystem import (
    ProjectInfo,
    JINJA_PATH,
    SHUTIL_ARCHIVE_FORMATS,
    SHUTIL_ARCHIVE_SUFFIX_MAP,
    style_linker,
    macro_linker,
    citation_linker,
    template_linker,
)
from .process import subproc_run, compile_tex, get_github_api_token
from .template import LoadTemplate, InitTemplate, PackageLinker
from .term import err_echo

if TYPE_CHECKING:
    from typing import Optional, Iterable, Any


class CatchInternalExceptions(click.Group):
    """Catch some special errors which occur during program execution, and print them out nicely."""

    def __call__(self, *args, **kwargs) -> Any:
        try:
            return self.main(*args, **kwargs)

        except (BasePathError, LaTeXCompileError, SubcommandError) as err:
            err_echo(err)
            sys.exit(1)


@click.group(cls=CatchInternalExceptions)
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
@click.pass_context
def cli(ctx, proj_dir: Path, dry_run: bool, verbose: bool) -> None:
    """TexProject is a tool to help streamline the creation and distribution of files written in
    LaTeX.
    """
    ctx.obj = ProjectInfo(proj_dir, dry_run, verbose)


@cli.command()
@click.argument(
    "template", type=click.Choice(template_linker.list_names()), metavar="TEMPLATE"
)
@click.pass_obj
def init(proj_info: ProjectInfo, template: str) -> None:
    """Initialize a new project in the working directory. The project is created using the template
    with name TEMPLATE and placed in the output folder OUTPUT.

    The path working directory either must not exist or be an empty folder. Missing intermediate
    directories are automatically constructed.
    """
    proj_info.validate(exists=False)

    proj_gen = InitTemplate(template)

    proj_gen.create_output_folder(proj_info)
    proj_gen.write_tpr_files(proj_info)


def _refresh_template(proj_info: ProjectInfo):
    LoadTemplate(proj_info).write_tpr_files(proj_info)


@cli.command()
@click.option(
    "--template",
    "config_file",
    flag_value="template",
    default=True,
    help="Edit project template.",
)
@click.option(
    "--local", "config_file", flag_value="local", help="Edit local configuration."
)
@click.option(
    "--global", "config_file", flag_value="global", help="Edit global configuration."
)
@click.pass_obj
def config(proj_info: ProjectInfo, config_file: str) -> None:
    """Edit texproject configuration files. This opens the corresponding file in your $EDITOR. By
    default, edit the project template file: this requires the working directory to be texproject
    directory.

    Note that this command does not replace existing macro files. See the `tpr import` command for
    this functionality.
    """
    match config_file:
        case "template":
            proj_info.validate(exists=True)

            click.edit(filename=str(proj_info.template))
            _refresh_template(proj_info)

        case "local":
            click.edit(filename=str(proj_info.config.local_path))

        case "global":
            click.edit(filename=str(proj_info.config.global_path))

        case _:
            assert_never(config_file)


@cli.command("import")
@click.option(
    "--macro",
    "macros",
    multiple=True,
    type=click.Choice(macro_linker.list_names()),
    help="macro file",
    show_default=False,
)
@click.option(
    "--citation",
    "citations",
    multiple=True,
    type=click.Choice(citation_linker.list_names()),
    help="citation file",
    show_default=False,
)
@click.option(
    "--style",
    "style",
    default=None,
    type=click.Choice(style_linker.list_names()),
    help="style file",
    show_default=False,
)
@click.option(
    "--macro-path",
    "macro_paths",
    multiple=True,
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, writable=False, path_type=Path
    ),
    help="macro file path",
)
@click.option(
    "--citation-path",
    "citation_paths",
    multiple=True,
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, writable=False, path_type=Path
    ),
    help="citation file path",
)
@click.pass_obj
def import_(
    proj_info: ProjectInfo,
    macros: Iterable[str],
    citations: Iterable[str],
    style: Optional[str],
    macro_paths: Iterable[Path],
    citation_paths: Iterable[Path],
) -> None:
    """Import macro, citation, and format files. This command will replace existing files. Note that
    this command does not import the files into the main .tex file.

    The --macro-path and --citation-path allow macro and citation files to be specified as paths to
    existing files. For example, this enables imports which are not installed in the texproject data
    directory.
    """
    proj_info.validate(exists=True)

    linker = PackageLinker(proj_info, force=True)
    linker.link_macros(macros)
    linker.link_citations(citations)
    linker.link_style(style)
    linker.link_macro_paths(macro_paths)
    linker.link_citation_paths(citation_paths)


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
@click.pass_obj
def validate(proj_info: ProjectInfo, pdf: Path, logfile: Path) -> None:
    """Check for compilation errors. Save the resulting pdf with the '--output' argument, or the log
    file with the '--logfile' argument. These options, if specified, will overwrite existing files.

    Compilation requires the 'latexmk' program to be installed and accessible
    to this program. Compilation is done by executing the command

    $ latexmk -pdf -interaction=nonstopmode

    You can specify additional options in 'config.system.latex_compile_options'.
    """
    proj_info.validate(exists=True)
    with proj_info.temp_subpath() as build_dir:
        build_dir.mkdir()
        compile_tex(
            proj_info, outdir=build_dir, output_map={".pdf": pdf, ".log": logfile}
        )


def validate_exists(ctx, _, path) -> Path:
    """TODO: write"""
    if not ctx.obj.force and path.exists():
        raise click.BadParameter("file exists. Use -f / --force to overwrite.")
    return path


@cli.command()
@click.option("--force/--no-force", "-f/-F", default=False, help="overwrite files")
@click.option(
    "--format",
    "compression",
    type=click.Choice(SHUTIL_ARCHIVE_FORMATS, case_sensitive=False),
    help="compression mode",
)
@click.option(
    "--mode",
    "mode",
    type=click.Choice(["arxiv", "build", "source"]),
    default="source",
    show_default=True,
    help="specify what to export",
)
@click.argument(
    "output",
    type=click.Path(exists=False, writable=True, path_type=Path),
    callback=validate_exists,
)
@click.pass_obj
def archive(
    proj_info: ProjectInfo, force: bool, compression: str, mode: str, output: Path
) -> None:
    """Create a compressed export with name OUTPUT. If the 'arxiv' or 'build' options are chosen,
    'latexmk' is used to compile additional required files. Run 'tpr validate --help' for more
    information.

    The --format option specifies the format of the resulting archive. If unspecified, the format is
    inferred from the resulting filename if possible. Otherwise, the output format is 'tar'.

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

    Note that not all compression modes may be available on your system.
    """
    proj_info.force = force
    proj_info.validate(exists=True)

    if compression is None:
        try:
            compression = SHUTIL_ARCHIVE_SUFFIX_MAP[output.suffix]
            output = output.parent / output.stem
        except KeyError:
            compression = "tar"

    create_archive(proj_info, compression, output, fmt=mode)


@cli.group()
@click.pass_obj
def git(proj_info: ProjectInfo) -> None:
    """Subcommand to manage git files."""
    proj_info.validate(exists=True)


@git.command("init")
@click.option(
    "--repo-name",
    "repo_name",
    prompt="Repository name",
    help="Name of the repository",
    type=str,
)
@click.option(
    "--repo-description",
    "repo_desc",
    prompt="Repository description",
    help="Repository description",
    type=str,
)
@click.option(
    "--repo-visibility",
    "vis",
    prompt="Repository visibility",
    type=click.Choice(["public", "private"]),
    help="Specify public or private repository",
    default="private",
)
@click.option(
    "--wiki/--no-wiki",
    "wiki",
    prompt="Include wiki?",
    help="Create wiki",
    default=False,
)
@click.option(
    "--issues/--no-issues",
    "issues",
    prompt="Include issues?",
    help="Create issues page",
    default=False,
)
@click.pass_obj
def git_init(
    proj_info: ProjectInfo,
    repo_name: str,
    repo_desc: str,
    vis: str,
    wiki: bool,
    issues: bool,
) -> None:
    """Initialize git and a corresponding GitHub repository. If called with no
    options, this command will interactively prompt you in order to initialize
    the repo correctly. This command also creates a GitHub action with
    automatically compiles and releases the main .pdf file for tagged releases.

    If you have specified 'config.user.github.archive', the
    GitHub action will also automatically push the build files to the
    corresponding folder in the specified repository. In order for this to
    work, you must provide an access token must with at least repo privileges.
    This can be done (in order of priority) by

    1) setting the environment variable $API_TOKEN_GITHUB, or

    2) setting the 'github.keyring' settings in the system configuration.

    Otherwise, the token will default to the empty string. The access token is
    not required for the build action functionality.
    """
    proj_info.validate_git(exists=False)

    proj_gen = LoadTemplate(proj_info)
    proj_gen.write_git_files(proj_info)

    # initialize repo
    subproc_run(proj_info, ["git", "init"])

    # add and commit all files
    subproc_run(proj_info, ["git", "add", "-A"])
    subproc_run(
        proj_info, ["git", "commit", "-m", "Initialize new texproject repository"]
    )

    # initialize github with settings
    gh_command = [
        "gh",
        "repo",
        "create",
        "-d",
        repo_desc,
        "--source",
        str(proj_info.dir),
        "--remote",
        "origin",
        "--push",
        repo_name,
        "--" + vis,
    ]

    if not wiki:
        gh_command.append("--disable-wiki")

    if not issues:
        gh_command.append("--disable-issues")

    subproc_run(proj_info, gh_command)

    subproc_run(
        proj_info,
        [
            "gh",
            "secret",
            "set",
            "API_TOKEN_GITHUB",
            "-b",
            get_github_api_token(proj_info),
            "-r",
            repo_name,
        ],
    )


@git.command()
@click.option("--force/--no-force", "-f/-F", default=False, help="overwrite files")
@click.pass_obj
def init_files(proj_info: ProjectInfo, force: bool) -> None:
    """Initialize git files, but do not create the repository."""
    if not force:
        proj_info.validate_git(exists=False)
    proj_gen = LoadTemplate(proj_info)
    proj_gen.write_git_files(proj_info, force=force)


@git.command()
@click.option(
    "--repo-name",
    "repo_name",
    prompt="Repository name",
    help="Name of the repository",
    type=str,
)
@click.pass_obj
def set_archive(proj_info: ProjectInfo, repo_name: str) -> None:
    """Set the GitHub secret and archive repository."""
    proj_gen = LoadTemplate(proj_info)
    proj_gen.write_template_with_info(
        proj_info, JINJA_PATH.build_latex, proj_info.build_latex, force=True
    )
    subproc_run(
        proj_info,
        [
            "gh",
            "secret",
            "set",
            "API_TOKEN_GITHUB",
            "-b",
            get_github_api_token(proj_info),
            "-r",
            repo_name,
        ],
    )


@cli.command("list")
@click.argument(
    "res_class", type=click.Choice(["citation", "macro", "format", "template"])
)
def list_(res_class: str) -> None:
    """Retrieve program and template information."""

    linker_map = {
        "citation": citation_linker,
        "macro": macro_linker,
        "style": style_linker,
        "template": template_linker,
    }

    click.echo("\n".join(linker_map[res_class].list_names()))


@cli.group()
@click.pass_obj
def util(proj_info: ProjectInfo) -> None:
    """Various utilities to facilitate the upgrading of old repositories.
    Warning: these commands are destructive!
    """
    proj_info.validate(exists=True)


@util.command("upgrade")
@click.pass_obj
def upgrade(proj_info: ProjectInfo) -> None:
    """Update configuration file to .toml."""
    import yaml
    import pytomlpp

    yaml_path = proj_info.data_dir / "tpr_info.yaml"
    old_toml_path = proj_info.data_dir / "tpr_info.toml"

    if yaml_path.exists():
        proj_info.template.write_text(
            pytomlpp.dumps(yaml.safe_load(yaml_path.read_text()))
        )
        yaml_path.unlink()

    if old_toml_path.exists():
        old_toml_path.rename(proj_info.template)

    # rename all the files
    for init, trg, end in [
        ("macro", "macros", ".sty"),
        ("citation", "citations", ".bib"),
        ("format", "style", ".sty"),
    ]:
        (proj_info.data_dir / trg).mkdir(exist_ok=True)
        for path in proj_info.data_dir.glob(f"{init}-*{end}"):
            path.rename(
                proj_info.data_dir
                / trg
                / ("local-" + "".join(path.name.split("-")[1:]))
            )

    # rename format key to style key, if needed
    try:
        tpl_dict = pytomlpp.load(proj_info.template)
        tpl_dict["style"] = tpl_dict.pop("format")
        proj_info.template.write_text(pytomlpp.dumps(tpl_dict))
    except KeyError:
        pass

    # refresh the template
    _refresh_template(proj_info)


@util.command()
@click.option(
    "--remove-unneeded/--keep-unneeded",
    "rm_unneeded",
    default=False,
    help="remove packages that are not imported into the file",
)
@click.pass_obj
def clean(proj_info: ProjectInfo, rm_unneeded: bool) -> None:
    """Clean the project directory.

    Currently not fully implemented.
    """
    proj_info.validate(exists=True)
    proj_info.clear_temp()
