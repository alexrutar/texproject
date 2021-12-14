from xdg import XDG_DATA_HOME, XDG_CONFIG_HOME
from pathlib import Path
import shutil
import os
import errno
import pytomlpp
import uuid
import contextlib

from .error import (BasePathError, ProjectExistsError, ProjectDataMissingError,
        ProjectMissingError, TemplateDataMissingError, SystemDataMissingError,
        GitExistsError, GitMissingError)


def _constant(f):
    def fset(self, value):
        raise AttributeError("Cannot change constant values")
    def fget(self):
        return f(self)
    return property(fget, fset)


def toml_load(path_obj):
    return pytomlpp.loads(path_obj.read_text())


def toml_dump(path_obj, dct):
    path_obj.write_text(pytomlpp.dumps(dct))


class _ConfigPath:
    @_constant
    def system(self):
        return XDG_DATA_HOME / 'texproject' / 'config' / 'tpr_config.toml'

    @_constant
    def user(self):
        return XDG_CONFIG_HOME / 'texproject' / 'config.toml'


CONFIG_PATH = _ConfigPath()
CONFIG = toml_load(CONFIG_PATH.system)


class _Naming:
    @_constant
    def template_toml(self):
        return 'template.toml'

    @_constant
    def template_doc(self):
        return 'document.tex'


NAMES = _Naming()


class _DataPath:
    # data location constants
    @_constant
    def data_dir(self):
        return XDG_DATA_HOME / 'texproject'

    @_constant
    def default_template(self):
        return self.data_dir / 'config' / 'default_template.toml'

    @_constant
    def _resource_absolute(self):
        return XDG_DATA_HOME / 'texproject' / 'resources'

    @_constant
    def macro_dir(self):
        return self._resource_absolute / 'packages' / 'macros'

    @_constant
    def format_dir(self):
        return self._resource_absolute / 'packages' / 'format'

    @_constant
    def citation_dir(self):
        return self._resource_absolute / 'citations'

    @_constant
    def template_dir(self):
        return self.data_dir / 'templates'


class _JinjaTemplatePath:
    def template_doc(self, name):
        return Path('templates', name, NAMES.template_doc)

    @_constant
    def _template_resource_dir(self):
        return  Path('resources', 'other')

    @_constant
    def project_macro(self):
        return self._template_resource_dir / 'project_macro_file.tex'

    @_constant
    def gitignore(self):
        return self._template_resource_dir / 'gitignore'

    @_constant
    def build_latex(self):
        return self._template_resource_dir / 'build_latex.yml'

    @_constant
    def classinfo(self):
        return self._template_resource_dir / 'classinfo.tex'

    @_constant
    def bibinfo(self):
        return self._template_resource_dir / 'bibinfo.tex'

    @_constant
    def bibliography(self):
        return self._template_resource_dir / 'bibliography.tex'

    @_constant
    def arxiv_autotex(self):
        return self._template_resource_dir / 'arxiv_autotex.txt'


def relative(base):
    def fset(self, value):
        raise AttributeError("Cannot change constant values")

    def decorator(func):
        def fget(self):
            if base == 'root':
                return self.working_dir / func(self)
            elif base == 'data':
                if self.nohidden:
                    data_folder = CONFIG['project_data_folder'].lstrip('.')
                else:
                    data_folder = CONFIG['project_data_folder']

                return self.working_dir / data_folder / func(self)
            elif base == 'gh_actions':
                return self.working_dir / '.github' / 'workflows' / func(self)
        return property(fget, fset)

    return decorator


class ProjectPath:
    def __init__(self, working_dir, nohidden=False):
        """If exists is False, check that there are no conflicts"""
        self.working_dir = working_dir.resolve()
        self.nohidden = nohidden
        self.name = self.dir.name

    def validate(self, exists=True):
        if not exists and any(path.exists() for path in self.rootfiles):
            raise ProjectExistsError(self.working_dir)
        elif exists and any(not path.exists() for path in self.minimal_files):
            raise ProjectMissingError(self.working_dir)
        else:
            return

    def validate_git(self, exists=True):
        if not exists and any(path.exists() for path in self.gitfiles):
            raise GitExistsError(self.working_dir)
        elif exists and any(not path.exists() for path in self.minimal_gitfiles):
            raise GitMissingError(self.working_dir)

    @relative('data')
    def config(self):
        return 'tpr_info.toml'

    @relative('data')
    def classinfo(self):
        return f"{CONFIG['classinfo_file']}.tex"

    @relative('data')
    def bibinfo(self):
        return f"{CONFIG['bibinfo_file']}.tex"

    @relative('root')
    def dir(self):
        return ''

    @relative('data')
    def data_dir(self):
        return ''

    @relative('data')
    def temp_dir(self):
        return 'tmp'

    @relative('root')
    def main(self):
        return f"{CONFIG['default_tex_name']}.tex"

    @relative('root')
    def arxiv_autotex(self):
        return "000README.XXX"

    @relative('root')
    def project_macro(self):
        return f"{CONFIG['project_macro_file']}.sty"

    @relative('root')
    def gitignore(self):
        return f".gitignore"

    @relative('root')
    def git_home(self):
        return ".git"

    @relative('root')
    def github_home(self):
        return '.github'

    @relative('gh_actions')
    def build_latex(self):
        return f"build_latex.yml"

    @_constant
    def gitfiles(self):
        return (self.git_home, self.github_home)

    @_constant
    def minimal_gitfiles(self):
        return (self.git_home,)

    @_constant
    def rootfiles(self):
        return (self.main, self.project_macro, self.data_dir)

    @_constant
    def minimal_files(self):
        return (self.main, self.data_dir)

    @contextlib.contextmanager
    def temp_subpath(self):
        self.temp_dir.mkdir(exist_ok=True)
        path = self.temp_dir / uuid.uuid1().hex
        try:
            yield path
        finally:
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
            except Exception as e:
                print(f"Failed to delete '{path}'. Reason: {e}")

    def clear_temp(self):
        if self.temp_dir.exists():
            for file_path in self.temp_dir.iterdir():
                try:
                    if file_path.is_file() or file_path.is_symlink():
                        file_path.unlink()
                    elif file_path.is_dir():
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Failed to delete '{file_path}'. Reason: {e}")


JINJA_PATH = _JinjaTemplatePath()
DATA_PATH = _DataPath()


class _BaseLinker:
    def __init__(self, dir_path, suffix, user_str):
        self.user_str = user_str
        self.dir_path = dir_path
        self.suffix = suffix

    def valid_path(self, path):
        return path.suffix == self.suffix

    def list_names(self):
        return sorted([path.stem for path in self.dir_path.iterdir()
                if self.valid_path(path)])

    def file_path(self, name):
        return self.dir_path / f'{name}{self.suffix}'


class _FileLinker(_BaseLinker):
    def __init__(self, dir_path, suffix, user_str, name_convention):
        super().__init__(dir_path, suffix, user_str)
        self.name_convention = name_convention

    def safe_name(self, name):
        return f"{self.name_convention}{CONFIG['prefix_separator']}{name}"

    def link_name(
            self, name, rel_path,
            force=False, silent_fail=True, is_path=False):
        if is_path:
            source_path = Path(name).resolve()
            if source_path.suffix != self.suffix:
                raise BasePathError(
                        source_path,
                        message=f"Filetype '{source_path.suffix}' is invalid!")
            target_path = rel_path / (self.safe_name(source_path.name))
        else:
            source_path = self.file_path(name).resolve()
            target_path = rel_path / (self.safe_name(name) + self.suffix)
            if not source_path.exists():
                raise TemplateDataMissingError(
                        source_path,
                        user_str=self.user_str,
                        name=name)

        if target_path.exists():
            if force:
                os.remove(target_path)
            else:
                if silent_fail:
                    return
                else:
                    raise FileExistsError(
                            errno.EEXIST,
                            f"Link target already exists",
                            str(target_path.resolve()))

        shutil.copyfile(
                str(source_path),
                str(target_path.resolve()))


def _load_default_template():
    try:
        default_template = toml_load(DATA_PATH.default_template)
    except FileNotFoundError:
        raise SystemDataMissingError(DATA_PATH.default_template)
    return default_template

def toml_load_local_template(path):
    default_template = _load_default_template()
    try:
        template = toml_load(path)
    except FileNotFoundError:
        raise ProjectDataMissingError(path, message="The local template file is missing.")
    return {**default_template, **template}

def toml_load_system_template(path, user_str, name=None):
    default_template = _load_default_template()
    try:
        template = toml_load(path)
    except FileNotFoundError:
        raise TemplateDataMissingError(path, user_str=user_str, name=name)
    return {**default_template, **template}


class _TemplateLinker(_BaseLinker):
    def load_template(self, name):
        return toml_load_system_template(
                self.file_path(name) / NAMES.template_toml,
                self.user_str,
                name=name)

    def valid_path(self, path):
        return (super().valid_path(path) and
                (path / NAMES.template_doc).exists() and
                (path / NAMES.template_toml).exists())


macro_linker = _FileLinker(
        DATA_PATH.macro_dir,
        '.sty',
        'macro file',
        CONFIG['macro_prefix'])


format_linker = _FileLinker(
        DATA_PATH.format_dir,
        '.sty',
        'format file',
        CONFIG['format_prefix'])


citation_linker = _FileLinker(
        DATA_PATH.citation_dir,
        '.bib',
        'citation file',
        CONFIG['citation_prefix'])


template_linker = _TemplateLinker(
        DATA_PATH.template_dir,
        '',
        'template')
