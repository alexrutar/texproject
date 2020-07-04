from xdg import XDG_DATA_HOME, XDG_CONFIG_HOME
from pathlib import Path
from shutil import copy
import yaml

DATA_DIR = XDG_DATA_HOME / 'texproject'
RESOURCES_DIR = DATA_DIR / 'resources'
TPR_INFO_FILENAME = '.tpr_link_info'
TEMPLATE_RESOURCE_DIR = Path('resources', 'other')

_CONVENTIONS_DIR = DATA_DIR / 'config' / '.tpr_config.yaml'
_USER_CONFIG_DIR = XDG_CONFIG_HOME / 'texproject' / 'tpr_config.yaml'

_DEFAULT_TEMPLATE = DATA_DIR / 'config' / '.default_template.yaml'
_TEMPLATE_YAML_NAME = 'template.yaml'
_TEMPLATE_DOC_NAME = 'document.tex'

_MACRO_DIR = RESOURCES_DIR / 'packages' / 'macros'
_FORMATTING_DIR = RESOURCES_DIR / 'packages' / 'formatting'
_CITATION_DIR = RESOURCES_DIR / 'citations'
_TEMPLATE_DIR = DATA_DIR / 'templates'

def yaml_load_from_path(path_obj):
    return yaml.safe_load(path_obj.read_text())

CONVENTIONS = yaml_load_from_path(_CONVENTIONS_DIR)

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
        return f"{self.name_convention}{CONVENTIONS['prefix_separator']}{name}"

    def link_name(self, name, rel_path):
        target_path = rel_path / (self.safe_name(name) + self.suffix)
        if self.frozen:
            copy(
                    str(self.file_path(name).resolve(),
                        str(target_path.resolve())))
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
        CONVENTIONS['macro_prefix'])

formatting_loader = FileLoader(
        _FORMATTING_DIR,
        '.sty',
        'formatting file',
        CONVENTIONS['formatting_prefix'])

citation_loader = FileLoader(
        _CITATION_DIR,
        '.bib',
        'citation file',
        CONVENTIONS['citation_prefix'])

template_loader = TemplateLoader(
        _TEMPLATE_DIR,
        '',
        'template')
