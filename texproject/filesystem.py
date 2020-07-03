from xdg import XDG_DATA_HOME, XDG_CONFIG_HOME
from pathlib import Path
import yaml

DATA_DIR = XDG_DATA_HOME / "texproject"
TEMPLATE_DIR = DATA_DIR / "templates"
RESOURCES_DIR = DATA_DIR / "resources"
CONFIG_DIR = XDG_CONFIG_HOME / "texproject"
TPR_INFO_FILENAME = '.tpr_link_info'

# TODO: do some error catching if paths are missing
def yaml_load_from_path(path_obj):
    return yaml.safe_load(path_obj.read_text())

def load_config_dict():
    return yaml_load_from_path(CONFIG_DIR / '.tpr_config.yaml')

def load_user_dict():
    return yaml_load_from_path(CONFIG_DIR / 'user_info.yaml')

def load_template_dict(template_name):
    default_template = yaml_load_from_path(CONFIG_DIR / '.default_template.yaml')
    template = yaml_load_from_path(TEMPLATE_DIR / template_name / 'template.yaml')
    return {**default_template, **template}

def load_proj_dict(proj_path):
    return yaml_load_from_path(proj_path / TPR_INFO_FILENAME)

def formatting_path(form):
    return RESOURCES_DIR / 'packages' / 'formatting' / f"{form}.sty"

def macro_path(macro):
    return RESOURCES_DIR / 'packages' / 'macros' / f"{macro}.sty"

def citation_path(citation):
    return RESOURCES_DIR / 'citations' / f'{citation}.bib'
