import shutil
from .filesystem import CONFIG, ProjectPath
from .template import ProjectTemplate
from .latex import compile_tex

# TODO: should compile first
# check that .zip etc. are automatically appended
def create_export(proj_path, compression, archive_file, arxiv=False):

    with proj_path.temp_subpath() as archive_dir, proj_path.temp_subpath() as build_dir:
        shutil.copytree(proj_path.dir,
                archive_dir,
                copy_function=shutil.copy,
                ignore=shutil.ignore_patterns(*CONFIG['ignore_patterns']))

        if arxiv:
            output_map = {'.bbl': archive_dir / (CONFIG['default_tex_name'] + '.bbl')}
        else:
            output_map = {'.pdf': archive_dir / (CONFIG['default_tex_name'] + '.pdf')}

        # build in the files automatically
        build_dir.mkdir()
        compile_tex(proj_path.dir, outdir=build_dir, output_map=output_map)

        if arxiv:
            _modify_arxiv(archive_dir)

        shutil.make_archive(archive_file,
                compression,
                archive_dir)

def _modify_arxiv(archive_dir):
    """Modify the archive_dir in place to make it arxiv-compatible!"""
    old_proj_path = ProjectPath(archive_dir)
    old_proj_info = ProjectTemplate.load_from_project(old_proj_path)

    new_proj_path = ProjectPath(archive_dir, nohidden=True)
    new_proj_info = ProjectTemplate.from_dict(old_proj_info.template_dict)

    # remove hidden folders
    (archive_dir / old_proj_path.data_dir).rename(archive_dir / new_proj_path.data_dir)

    # substitute some macros that arxiv does not like
    macro_substitutions = {
            'typesetting': 'arxiv-typesetting'
            }
    new_proj_info.template_dict['macros'] = [macro_substitutions[macro]
            if macro in macro_substitutions.keys()
            else macro
            for macro in old_proj_info.template_dict['macros']]
    
    # write the files to the new location
    new_proj_info.write_tpr_files(new_proj_path)

    # replace \input with information pulled directly from data folder
    main_tex_path = archive_dir / (CONFIG['default_tex_name'] + '.tex')
    with open(main_tex_path, 'r') as texfile:
        new_contents = texfile.read()

        # pull in relative inputs
        for end in [CONFIG['classinfo_file'], CONFIG['bibinfo_file']]:
            with open(archive_dir / new_proj_path.data_dir / (end + ".tex"), 'r') as repl:
                new_contents = new_contents.replace(
                        r"\input{" + old_proj_path.data_dir.name + "/" + end + r"}" + "\n",
                        repl.read()
                        )

    with open(main_tex_path, 'w') as texfile:
        texfile.write(new_contents)

    # add arxiv autotex content
    new_proj_info.write_arxiv_autotex(new_proj_path)
