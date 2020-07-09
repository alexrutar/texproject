from xdg import XDG_DATA_HOME, XDG_CONFIG_HOME
from pathlib import Path
from shutil import copyfile
import os
import errno
import yaml


def constant(f):
    def fset(self, value):
        raise AttributeError("Cannot change constant values")
    def fget(self):
        return f(self)
    return property(fget, fset)

def yaml_load(path_obj):
    return yaml.safe_load(path_obj.read_text())

def yaml_dump(path_obj, dct):
    path_obj.write_text(yaml.dump(dct))

class _ConfigPath:
    @constant
    def system(self):
        return XDG_DATA_HOME / 'texproject' / 'config' / 'tpr_config.yaml'

    @constant
    def user(self):
        return XDG_CONFIG_HOME / 'texproject' / 'config.yaml'

CONFIG_PATH = _ConfigPath()
CONFIG = yaml_load(CONFIG_PATH.system)

class _Naming:
    @constant
    def template_yaml(self):
        return 'template.yaml'

    @constant
    def template_doc(self):
        return 'document.tex'

NAMES = _Naming()

class _DataPath:
    # data location constants
    @constant
    def data_dir(self):
        return XDG_DATA_HOME / 'texproject'

    @constant
    def default_template(self):
        return self.data_dir / 'config' / 'default_template.yaml'

    @constant
    def _resource_absolute(self):
        return XDG_DATA_HOME / 'texproject' / 'resources'

    @constant
    def macro_dir(self):
        return self._resource_absolute / 'packages' / 'macros'

    @constant
    def format_dir(self):
        return self._resource_absolute / 'packages' / 'format'

    @constant
    def citation_dir(self):
        return self._resource_absolute / 'citations'

    @constant
    def template_dir(self):
        return self.data_dir / 'templates'


class _JinjaTemplatePath:
    def template_doc(self, name):
        return Path('templates', name, NAMES.template_doc)

    @constant
    def _template_resource_dir(self):
        return  Path('resources', 'other')

    @constant
    def project_macro(self):
        return self._template_resource_dir / 'project_macro_file.tex'

    @constant
    def classinfo(self):
        return self._template_resource_dir / 'classinfo.tex'

    @constant
    def bibinfo(self):
        return self._template_resource_dir / 'bibinfo.tex'

    @constant
    def bibliography(self):
        return self._template_resource_dir / 'bibliography.tex'

def relative(base):
    if base == 'data':
        def decorator(func):
            def wrapper(self, rel_path):
                return rel_path / CONFIG['project_data_folder'] / func(self)
            return wrapper
        return decorator
    elif base == 'root':
        def decorator(func):
            def wrapper(self, rel_path):
                return rel_path / func(self)
            return wrapper
        return decorator

def path_relative(func):
    def wrapper(self, rel_path):
        return rel_path / CONFIG['project_data_folder'] / func(self)
    return wrapper

class _ProjectPath:
    @relative('data')
    def config(self):
        return 'tpr_info.yaml'

    @relative('data')
    def classinfo(self):
        return f"{CONFIG['classinfo_file']}.tex"

    @relative('data')
    def bibinfo(self):
        return f"{CONFIG['bibinfo_file']}.tex"

    @relative('data')
    def dir(self):
        return ''

    @relative('data')
    def temp_dir(self):
        return 'tmp'

    @relative('root')
    def main(self):
        return f"{CONFIG['default_tex_name']}.tex"

    @relative('root')
    def macro_proj(self):
        return f"{CONFIG['project_macro_file']}.sty"

JINJA_PATH = _JinjaTemplatePath()
DATA_PATH = _DataPath()
PROJ_PATH = _ProjectPath()


class BaseLinker:
    def __init__(self, dir_path, suffix, user_str):
        self.user_str = user_str
        self.dir_path = dir_path
        self.suffix = suffix
        self.frozen = False

    def valid_path(self, path):
        return path.suffix == self.suffix

    def list_names(self):
        return [path.stem for path in self.dir_path.iterdir()
                if self.valid_path(path)]

    def file_path(self, name):
        return self.dir_path / f'{name}{self.suffix}'

class FileLinker(BaseLinker):
    def __init__(self, dir_path, suffix, user_str, name_convention):
        super().__init__(dir_path, suffix, user_str)
        self.name_convention = name_convention

    def safe_name(self, name):
        return f"{self.name_convention}{CONFIG['prefix_separator']}{name}"

    def link_name(self, name, rel_path, frozen=False,force=False,silent_fail=True):
        source_path = self.file_path(name).resolve()
        target_path = rel_path / (self.safe_name(name) + self.suffix)
        if not source_path.exists():
            raise FileNotFoundError(
                    errno.ENOENT,
                    f"The {self.user_str} '{name}' does not exist at source",
                    str(source_path.resolve()))

        if target_path.is_symlink():
            target_path.unlink()

        elif target_path.exists():
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

        if frozen:
            copyfile(
                    str(source_path),
                    str(target_path.resolve()))
        else:
            target_path.symlink_to(source_path)

class TemplateLinker(BaseLinker):
    def load_template(self, name):
        default_template = yaml_load(DATA_PATH.default_template)
        template = yaml_load(
                self.file_path(name) / NAMES.template_yaml)
        return {**default_template, **template}

    def valid_path(self, path):
        return (super().valid_path(path) and
                (path / NAMES.template_doc).exists() and
                (path / NAMES.template_yaml).exists())

macro_linker = FileLinker(
        DATA_PATH.macro_dir,
        '.sty',
        'macro file',
        CONFIG['macro_prefix'])

format_linker = FileLinker(
        DATA_PATH.format_dir,
        '.sty',
        'format file',
        CONFIG['format_prefix'])

citation_linker = FileLinker(
        DATA_PATH.citation_dir,
        '.bib',
        'citation file',
        CONFIG['citation_prefix'])

template_linker = TemplateLinker(
        DATA_PATH.template_dir,
        '',
        'template')
