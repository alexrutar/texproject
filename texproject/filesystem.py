from xdg import XDG_DATA_HOME, XDG_CONFIG_HOME
from pathlib import Path
from shutil import copyfile
from os import remove
import yaml

DATA_DIR = XDG_DATA_HOME / 'texproject'
RESOURCES_DIR = DATA_DIR / 'resources'
TPR_INFO_FILENAME = '.tpr_info'

_CONFIG_DIR = DATA_DIR / 'config' / 'tpr_config.yaml'
_USER_CONFIG_DIR = XDG_CONFIG_HOME / 'texproject' / 'config.yaml'

_DEFAULT_TEMPLATE = DATA_DIR / 'config' / 'default_template.yaml'
_TEMPLATE_YAML_NAME = 'template.yaml'
_TEMPLATE_DOC_NAME = 'document.tex'

TEMPLATE_RESOURCE_DIR = Path('resources', 'other')
_PROJECT_MACRO_TEMPLATE = TEMPLATE_RESOURCE_DIR / 'project_macro_file.tex'
_CLASSINFO_TEMPLATE = TEMPLATE_RESOURCE_DIR / 'classinfo.tex'
_BIBINFO_TEMPLATE = TEMPLATE_RESOURCE_DIR / 'bibinfo.tex'

_MACRO_DIR = RESOURCES_DIR / 'packages' / 'macros'
_FORMAT_DIR = RESOURCES_DIR / 'packages' / 'format'
_CITATION_DIR = RESOURCES_DIR / 'citations'
_TEMPLATE_DIR = DATA_DIR / 'templates'

def yaml_load_from_path(path_obj):
    return yaml.safe_load(path_obj.read_text())

def yaml_dump_proj_info(proj_path, template_dict):
    (proj_path / TPR_INFO_FILENAME).write_text(yaml.dump(template_dict))

CONFIG = yaml_load_from_path(_CONFIG_DIR)

def load_user_dict():
    return yaml_load_from_path(_USER_CONFIG_DIR)

def load_proj_dict(proj_path):
    return yaml_load_from_path(proj_path / TPR_INFO_FILENAME)


class BaseLoader:
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

class FileLoader(BaseLoader):
    def __init__(self, dir_path, suffix, user_str, name_convention):
        super().__init__(dir_path, suffix, user_str)
        self.name_convention = name_convention

    def safe_name(self, name):
        return f"{self.name_convention}{CONFIG['prefix_separator']}{name}"

    def link_name(self, name, rel_path,frozen=False,force=False):
        target_path = rel_path / (self.safe_name(name) + self.suffix)

        if target_path.is_symlink():
            target_path.unlink()
        elif target_path.exists():
            if force:
                remove(target_path)
            else:
                return

        if frozen:
            copyfile(
                    str(self.file_path(name).resolve()),
                        str(target_path.resolve()))
        else:
            target_path.symlink_to(self.file_path(name))

class TemplateLoader(BaseLoader):
    def load_template(self, name):
        default_template = yaml_load_from_path(_DEFAULT_TEMPLATE)
        template = yaml_load_from_path(
                self.file_path(name) / _TEMPLATE_YAML_NAME)
        return {**default_template, **template}

    def valid_path(self, path):
        return (super().valid_path(path) and
                (path / _TEMPLATE_DOC_NAME).exists() and
                (path / _TEMPLATE_YAML_NAME).exists())

macro_loader = FileLoader(
        _MACRO_DIR,
        '.sty',
        'macro file',
        CONFIG['macro_prefix'])

format_loader = FileLoader(
        _FORMAT_DIR,
        '.sty',
        'format file',
        CONFIG['format_prefix'])

citation_loader = FileLoader(
        _CITATION_DIR,
        '.bib',
        'citation file',
        CONFIG['citation_prefix'])

template_loader = TemplateLoader(
        _TEMPLATE_DIR,
        '',
        'template')
