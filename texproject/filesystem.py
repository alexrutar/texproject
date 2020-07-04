from xdg import XDG_DATA_HOME, XDG_CONFIG_HOME
from pathlib import Path
import yaml

DATA_DIR = XDG_DATA_HOME / 'texproject'
RESOURCES_DIR = DATA_DIR / 'resources'
TPR_INFO_FILENAME = '.tpr_link_info'

TEMPLATE_DIR = DATA_DIR / 'templates'
MACRO_DIR = RESOURCES_DIR / 'packages' / 'macros'
CITATION_DIR = RESOURCES_DIR / 'citations'

def yaml_load_from_path(path_obj):
    return yaml.safe_load(path_obj.read_text())

def load_config_dict():
    return yaml_load_from_path(DATA_DIR / 'config' / '.tpr_config.yaml')

def load_user_dict():
    return yaml_load_from_path(XDG_CONFIG_HOME / 'texproject' / 'tpr_config.yaml')

def load_template_dict(template_name):
    default_template = yaml_load_from_path(DATA_DIR / 'config' / '.default_template.yaml')
    template = yaml_load_from_path(TEMPLATE_DIR / template_name / 'template.yaml')
    return {**default_template, **template}

def load_proj_dict(proj_path):
    return yaml_load_from_path(proj_path / TPR_INFO_FILENAME)

def formatting_path(form):
    return RESOURCES_DIR / 'packages' / 'formatting' / f'{form}.sty'

def macro_path(macro):
    return MACRO_DIR / f'{macro}.sty'

def citation_path(citation):
    return CITATION_DIR / f'{citation}.bib'

def list_templates():
    return [path.stem for path in TEMPLATE_DIR.iterdir()
            if path.is_dir() and (path / 'document.tex').exists()]

def list_citations():
    return [path.stem for path in CITATION_DIR.iterdir()
            if path.suffix == '.bib']

def list_macros():
    return [path.stem for path in MACRO_DIR.iterdir()
            if path.suffix == '.sty']
