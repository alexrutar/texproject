from xdg import XDG_DATA_HOME, XDG_CONFIG_HOME
from pathlib import Path
from shutil import copyfile
import os
import errno
import yaml

DATA_DIR = XDG_DATA_HOME / 'texproject'
RESOURCES_DIR = DATA_DIR / 'resources'

_CONFIG_DIR = DATA_DIR / 'config' / 'tpr_config.yaml'
_USER_CONFIG_DIR = XDG_CONFIG_HOME / 'texproject' / 'config.yaml'

_DEFAULT_TEMPLATE = DATA_DIR / 'config' / 'default_template.yaml'
_TEMPLATE_YAML_NAME = 'template.yaml'
_TEMPLATE_DOC_NAME = 'document.tex'

TEMPLATE_RESOURCE_DIR = Path('resources', 'other')
_PROJECT_MACRO_TEMPLATE = TEMPLATE_RESOURCE_DIR / 'project_macro_file.tex'
_CLASSINFO_TEMPLATE = TEMPLATE_RESOURCE_DIR / 'classinfo.tex'
_BIBINFO_TEMPLATE = TEMPLATE_RESOURCE_DIR / 'bibinfo.tex'
_BIBLIOGRAPHY_TEMPLATE = TEMPLATE_RESOURCE_DIR / 'bibliography.tex'

_MACRO_DIR = RESOURCES_DIR / 'packages' / 'macros'
_FORMAT_DIR = RESOURCES_DIR / 'packages' / 'format'
_CITATION_DIR = RESOURCES_DIR / 'citations'
_TEMPLATE_DIR = DATA_DIR / 'templates'

def yaml_load_from_path(path_obj):
    return yaml.safe_load(path_obj.read_text())


CONFIG = yaml_load_from_path(_CONFIG_DIR)
TPR_INFO_FILENAME = Path(CONFIG['project_folder'], 'tpr_info.yaml')

def load_user_dict():
    return yaml_load_from_path(_USER_CONFIG_DIR)

def load_proj_dict(out_folder):
    proj_template = out_folder / TPR_INFO_FILENAME
    try:
        return yaml_load_from_path(proj_template)
    except FileNotFoundError:
        raise FileNotFoundError(
                errno.ENOENT,
                "Project file does not exist",
                str(proj_template.resolve()))

def yaml_dump_proj_info(out_folder, template_dict):
    (out_folder / TPR_INFO_FILENAME).write_text(yaml.dump(template_dict))


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

    def link_name(self, name, rel_path,frozen=False,force=False,silent_fail=True):
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
        default_template = yaml_load_from_path(_DEFAULT_TEMPLATE)
        template = yaml_load_from_path(
                self.file_path(name) / _TEMPLATE_YAML_NAME)
        return {**default_template, **template}

    def valid_path(self, path):
        return (super().valid_path(path) and
                (path / _TEMPLATE_DOC_NAME).exists() and
                (path / _TEMPLATE_YAML_NAME).exists())

macro_linker = FileLinker(
        _MACRO_DIR,
        '.sty',
        'macro file',
        CONFIG['macro_prefix'])

format_linker = FileLinker(
        _FORMAT_DIR,
        '.sty',
        'format file',
        CONFIG['format_prefix'])

citation_linker = FileLinker(
        _CITATION_DIR,
        '.bib',
        'citation file',
        CONFIG['citation_prefix'])

template_linker = TemplateLinker(
        _TEMPLATE_DIR,
        '',
        'template')
