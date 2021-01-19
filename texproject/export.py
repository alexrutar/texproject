import shutil
from .filesystem import CONFIG, ProjectPath
from .template import ProjectTemplate
import re

def create_export(proj_path, compression, arxiv=False):

    root_dir = proj_path.dir
    temp_dir = proj_path.temp_dir / 'output'
    archive_file = root_dir / proj_path.name

    shutil.copytree(root_dir,
            temp_dir,
            copy_function=shutil.copyfile,
            ignore=shutil.ignore_patterns(*CONFIG['ignore_patterns']))


    if arxiv:
        _modify_arxiv(temp_dir)

    shutil.make_archive(archive_file,
            compression,
            temp_dir)

    shutil.rmtree(temp_dir)

def _modify_arxiv(temp_dir):
    """Modify the temp_dir in place to make it arxiv-compatible!"""
    proj_path = ProjectPath(temp_dir)
    proj_info = ProjectTemplate.load_from_project(proj_path)
    old_data_folder = CONFIG['project_data_folder']
    new_data_folder = old_data_folder.lstrip('.')

    # remove hidden folders and references
    shutil.move(temp_dir / old_data_folder,
            temp_dir / new_data_folder,
            copy_function=shutil.copyfile)
        
    # substitute some macros that arxiv does not like
    macro_substitutions = {
            'typesetting': 'arxiv-typesetting'
            }
    proj_info.template_dict['macros'] = [macro_substitutions[macro] if macro in macro_substitutions.keys() else macro for macro in proj_info.template_dict['macros']]
    

    # TODO: Modifying global variable!!! yikes
    # maybe have a no-hidden option...
    # this writes all the new files after updating this
    CONFIG['project_data_folder'] = new_data_folder
    proj_info.write_tpr_files(proj_path, force=True)


    # replace \input with information pulled directly from data folder
    main_tex_path = temp_dir / (CONFIG['default_tex_name'] + '.tex')
    with open(main_tex_path, 'r') as texfile:
        new_contents = texfile.read()

        # pull in relative inputs
        for end in [CONFIG['classinfo_file'], CONFIG['bibinfo_file']]:
            with open(temp_dir / new_data_folder / (end + ".tex"), 'r') as repl:
                new_contents = new_contents.replace(
                        r"\input{" + old_data_folder + "/" + end + r"}" + "\n",
                        repl.read()
                        )

    with open(main_tex_path, 'w') as texfile:
        texfile.write(new_contents)

    # add arxiv autotex content
    proj_info.write_arxiv_autotex(proj_path)
