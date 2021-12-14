import click
import shutil
import sys
from pathlib import Path

from . import __version__, __repo__
from .template import ProjectTemplate, PackageLinker
from .filesystem import (CONFIG, ProjectPath, CONFIG_PATH,
        format_linker, macro_linker, citation_linker, template_linker)
from .export import create_export
from .error import BasePathError, BuildError
from .term import REPO_FORMATTED, err_echo, subproc_run, get_github_api_token
from .latex import compile_tex


class CatchInternalExceptions(click.Group):
    def __call__(self, *args, **kwargs):
        try:
            return self.main(*args, **kwargs)

        except BasePathError as err:
            err_echo(err.message)
            sys.exit(1)

        except BuildError as err:
            err_echo(err.message + " Here is the build error output:\n")
            click.echo(err.stderr, err=True)
            sys.exit(1)

class CtxObjectWrapper:
    def __init__(self, proj_dir, verbose):
        self.proj_path = ProjectPath(proj_dir)
        self.working_directory = self.proj_path.dir
        self.verbose = verbose

@click.group(cls=CatchInternalExceptions)
@click.version_option(prog_name="tpr (texproject)")
@click.option(
        '-C', 'proj_dir',
        default='.',
        show_default=True,
        help='working directory',
        type=click.Path(
            exists=True, file_okay=False, dir_okay=True, writable=True, path_type=Path))
@click.option('--verbose/--silent', '-v/-V', 'verbose',
        default=True,
        help='Be verbose')
@click.pass_context
def cli(ctx, proj_dir, verbose):
    ctx.obj = CtxObjectWrapper(proj_dir, verbose)


@cli.command()
@click.argument('template')
@click.option('--citation','-c',
        multiple=True,
        help="include citation file")
@click.pass_obj
def init(ctxo, template, citation):
    """Initialize a new project in the current directory. The project is
    created using the template with name TEMPLATE and placed in the output
    folder OUTPUT.

    The path OUTPUT either must not exist or be an empty folder. Missing
    intermediate directories are automatically constructed."""
    ctxo.proj_path.validate(exists=False)

    proj_gen = ProjectTemplate.load_from_template(
            template,
            citation)

    proj_gen.create_output_folder(ctxo.proj_path)
    proj_gen.write_tpr_files(ctxo.proj_path, write_template=True)


@cli.command()
@click.option('--local', 'config_file', flag_value='local', default=True,
        help="Edit local project configuration.")
@click.option('--user', 'config_file', flag_value='user',
        help="Edit user information.")
@click.option('--system', 'config_file', flag_value='system',
        help="Edit global system configuration.")
@click.pass_obj
def config(ctxo, config_file):
    """Edit texproject configuration files. This opens the corresponding file
    in your $EDITOR. By default, edit the project configuration file; this
    requires the current directory (or the directory specified by -C) to be
    a texproject directory.

    Note that this command does not replace existing macro files. See the
    `tpr import` command for this functionality.
    """
    match config_file:
        case 'local':
            ctxo.proj_path.validate(exists=True)

            click.edit(filename=str(ctxo.proj_path.config))

            proj_info = ProjectTemplate.load_from_project(ctxo.proj_path)
            proj_info.write_tpr_files(ctxo.proj_path)

        case 'user':
            click.edit(filename=str(CONFIG_PATH.user))

        case 'system':
            click.edit(filename=str(CONFIG_PATH.system))


@cli.command('import')
@click.option('--macro', multiple=True,
        help="macro file")
@click.option('--citation', multiple=True,
        help="citation file")
@click.option('--format', default=None,
        help="format file")
@click.option('--path/--no-path', default=False,
        help="files given as absolute paths")
@click.pass_obj
def import_(ctxo, macro, citation, format, path):
    """Import macro, citation, and format files. This command will replace existing
    files. When called with the --path option, the arguments are interpreted as paths.
    This is convenient when importing packages which are not installed in the texproject
    directories.
    """
    ctxo.proj_path.validate(exists=True)

    linker = PackageLinker(ctxo.proj_path, force=True, is_path=path)
    linker.link_macros(macro)
    linker.link_citations(citation)
    linker.link_format(format)


@cli.group()
@click.option('--force/--no-force','-f/-F', default=False,
        help="overwrite files")
@click.pass_obj
def export(ctxo, force):
    """Utilities for creating and validating export files.
    """
    ctxo.proj_path.validate(exists=True)
    ctxo.force = force


click_output_argument = click.argument(
        'output',
        type=click.Path(
            exists=False, writable=True, path_type=Path))

@export.command()
@click_output_argument
@click.pass_obj
def pdf(ctxo, output):
    """Compile the project to a pdf with name OUTPUT.
    By default, this uses the compilation command specified in 'config.user.latex_compile_command'.
    """
    if output is not None and output.exists() and not ctxo.force:
        raise BasePathError(output, "Output file already exists! Run with '-f' to overwrite")
    else:
        output_map = {'.pdf': output} if output is not None else {}
        with ctxo.proj_path.temp_subpath() as build_dir:
            build_dir.mkdir()
            compile_tex(ctxo.working_directory, outdir=build_dir, output_map=output_map)


@export.command()
@click_output_argument
@click.pass_obj
def source(ctxo, output):
    """Export the source files.
    """
    raise NotImplementedError


@export.command()
@click.option('--compression',
        type=click.Choice([ar[0] for ar in shutil.get_archive_formats()],
            case_sensitive=False),
        show_default=True,
        default=CONFIG['default_compression'],
        help="compression mode")
@click.option('--arxiv/--no-arxiv',
        default=False,
        show_default=True,
        help="format for arXiv")
@click_output_argument
@click.pass_obj
def archive(ctxo, compression, arxiv, output):
    """Create a compressed export with name OUTPUT.

    \b
    Compression modes:
     bztar: bzip2'ed tar-file
     gztar: gzip'ed tar-file
     tar: uncompressed tar-file
     xztar: xz'ed tar-file
     zip: ZIP file

    Note that not all compression modes may be available on your system.
    """
    if output.exists() and not ctxo.force:
        raise BasePathError(output,
                "Output file already exists! Run with '-f' to overwrite")
    else:
        create_export(ctxo.proj_path, compression, output, arxiv=arxiv)


@cli.group()
@click.pass_obj
def git(ctxo):
    """Subcommand to manage git files.
    """
    ctxo.proj_path.validate(exists=True)


# todo: allow specification using keyring
@git.command('init')
@click.option('--repo-name', 'repo_name',
        prompt='Repository name',
        help='Name of the repository',
        type=str)
@click.option('--repo-description', 'repo_desc',
        prompt='Repository description',
        help='Repository description',
        type=str)
@click.option('--repo-visibility', 'vis',
        prompt='Repository visibility',
        type=click.Choice(['public', 'private']),
        help='Specify public or private repository',
        default='private')
@click.option('--wiki/--no-wiki', 'wiki',
        prompt='Include wiki?',
        help='Create wiki',
        default=False)
@click.option('--issues/--no-issues', 'issues',
        prompt='Include issues?',
        help='Create issues page',
        default=False)
@click.pass_obj
def git_init(ctxo, repo_name, repo_desc, vis, wiki, issues):
    """Initialize git and a corresponding GitHub repository. If called with no options,
    this command will interactively prompt you in order to initialize the repo correctly.
    This command also creates a GitHub action with automatically compiles and releases the
    main .pdf file for tagged releases.

    If you have specified the github.archive setting in your user configuration, the
    GitHub action will also automatically push the build files to the corresponding folder
    in the specified repository. In order for this to work, you must provide an access token must
    with at least repo privileges. This can be done (in order of priority) by

    1) setting the environment variable $API_TOKEN_GITHUB, or

    2) setting the 'github.archive.github_api_token_command' in the user configuration.

    Otherwise, the token will default to the empty string. The access token is not required for
    the build functionality.
    """
    ctxo.proj_path.validate_git(exists=False)

    proj_gen = ProjectTemplate.load_from_project(ctxo.proj_path)
    # proj_gen.user_dict is the user configuration file
    proj_gen.write_git_files(ctxo.proj_path)

    # initialize repo
    subproc_run(
            ['git', 'init'],
            cwd=ctxo.working_directory,
            check=True,
            verbose=ctxo.verbose)

    # add and commit all files
    subproc_run(
            ['git', 'add', '-A'],
            cwd=ctxo.working_directory,
            check=True,
            verbose=ctxo.verbose)
    subproc_run(
            ['git', 'commit', '-m', 'Initialize new texproject repository'],
            cwd=ctxo.working_directory,
            check=True,
            verbose=ctxo.verbose)

    # initialize github with settings
    gh_command = ['gh', 'repo', 'create',
            '-d', repo_desc,
            '--source', str(ctxo.working_directory),
            '--remote', 'origin',
            '--push', repo_name,
            '--' + vis
    ]

    if not wiki:
        gh_command.append('--disable-wiki')

    if not issues:
        gh_command.append('--disable-issues')

    subproc_run(gh_command,
            cwd=ctxo.working_directory,
            check=True,
            verbose=ctxo.verbose)

    subproc_run([
        'gh', 'secret', 'set', 'API_TOKEN_GITHUB',
        '-b', get_github_api_token(proj_gen.user_dict),
        '-r', repo_name],
        cwd=ctxo.working_directory,
        check=True,
        verbose=ctxo.verbose,
        conceal=True)


@cli.command()
@click.argument('res_class',
        type=click.Choice(['citation', 'macro', 'format', 'template']))
def list(res_class):
    """Retrieve program and template information."""

    linker_map = {
            'citation': citation_linker,
            'macro':macro_linker,
            'format': format_linker,
            'template': template_linker
            }

    click.echo("\n".join(linker_map[res_class].list_names()))


# TODO: refactor this
# - have option positional argument for listing / descriptions?
# - write descriptions into packages, and write access methods
@cli.command()
@click.argument('res_class',
        type=click.Choice(['citation', 'macro', 'format', 'template', 'repo']))
def info(res_class):
    """Retrieve program and template information."""
    if res_class == 'repo':
        click.echo(f"""TPR - TexPRoject (version {__version__})
Maintained by Alex Rutar ({REPO_FORMATTED}).
MIT License.""")


@cli.group()
@click.pass_obj
def upgrade(ctxo):
    """Various utilities to facilitate the upgrading of old repositories.
    Warning: these commands are destructive!
    """
    ctxo.proj_path.validate(exists=True)


@upgrade.command()
@click.pass_obj
def yaml(ctxo):
    """Update configuration file to .toml.
    """
    import yaml
    import pytomlpp
    yaml_path = ctxo.proj_path.data_dir / 'tpr_info.yaml'
    if yaml_path.exists():
        ctxo.proj_path.config.write_text(
                pytomlpp.dumps(
                    yaml.safe_load(
                        yaml_path.read_text())))
        yaml_path.unlink()


@upgrade.command()
@click.pass_obj
def build_latex(ctxo):
    """Update the github action 'build_latex.yml' script.
    """
    from .filesystem import JINJA_PATH
    proj_gen = ProjectTemplate.load_from_project(ctxo.proj_path)
    proj_gen.write_template(
            JINJA_PATH.build_latex,
            ctxo.proj_path.build_latex,
            force=True)


@upgrade.command()
@click.pass_obj
def gitignore(ctxo):
    """Update the '.gitignore' file.
    """
    from .filesystem import JINJA_PATH
    proj_gen = ProjectTemplate.load_from_project(ctxo.proj_path)
    proj_gen.write_template(
            JINJA_PATH.gitignore,
            ctxo.proj_path.gitignore,
            force=True)


@upgrade.command()
@click.pass_obj
def clean(ctxo):
    """Cleans the project directory.

    Currently not fully implemented.
    """
    # also clean up old stuff which might not be needed? e.g. any macro files etc. that are not
    # linked, for example
    ctxo.proj_path.validate(exists=True)
    ctxo.proj_path.clear_temp()


