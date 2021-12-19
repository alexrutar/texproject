import shutil
from .filesystem import ProjectInfo
from .template import ProjectTemplate
from .process import compile_tex


def create_archive(proj_info, compression, archive_file, fmt='build'):

    with proj_info.temp_subpath() as archive_dir, proj_info.temp_subpath() as build_dir:
        shutil.copytree(proj_info.dir,
                archive_dir,
                copy_function=shutil.copy,
                ignore=shutil.ignore_patterns(*proj_info.config.process['ignore_patterns']))

        # compile the tex files to get .bbl / .pdf
        if fmt in ('arxiv', 'build'):
            build_dir.mkdir()
            if fmt == 'arxiv':
                output_map = {'.bbl': archive_dir / (proj_info.config.render['default_tex_name'] + '.bbl')}
            else:
                output_map = {'.pdf': archive_dir / (proj_info.config.render['default_tex_name'] + '.pdf')}

            compile_tex(proj_info, outdir=build_dir, output_map=output_map)

            if fmt == 'arxiv':
                _modify_arxiv(proj_info, archive_dir)

        shutil.make_archive(archive_file,
                compression,
                archive_dir)

def _modify_arxiv(proj_info, archive_dir):
    """Modify the archive_dir in place to make it arxiv-compatible!"""
    # remove hidden folders
    archive_proj_info = ProjectInfo(archive_dir, False, False)
    old_data_dir = archive_proj_info.data_dir
    archive_proj_info.config.set_no_hidden()
    new_data_dir = archive_proj_info.data_dir
    (archive_dir / old_data_dir).rename(archive_dir / new_data_dir)

    archive_proj_gen = ProjectTemplate.load_from_project(archive_proj_info)


    # substitute some macros that arxiv does not like
    macro_substitutions = {
            'typesetting': 'arxiv-typesetting'
            }
    archive_proj_gen.template_dict['macros'] = [macro_substitutions[macro]
            if macro in macro_substitutions.keys()
            else macro
            for macro in archive_proj_gen.template_dict['macros']]
    
    # write the files to the new location
    archive_proj_gen.write_tpr_files(archive_proj_info)

    # replace \input with information pulled directly from data folder
    main_tex_path = archive_dir / (archive_proj_info.config.render['default_tex_name'] + '.tex')
    with open(main_tex_path, 'r') as texfile:
        new_contents = texfile.read()

        # pull in relative inputs
        for end in [archive_proj_info.config.render['classinfo_file'], archive_proj_info.config.render['bibinfo_file']]:
            with open(archive_dir / archive_proj_info.data_dir / (end + ".tex"), 'r') as repl:
                new_contents = new_contents.replace(
                        r"\input{" + archive_proj_info.data_dir.name + "/" + end + r"}" + "\n",
                        repl.read()
                        )

    with open(main_tex_path, 'w') as texfile:
        texfile.write(new_contents)

    # add arxiv autotex content
    archive_proj_gen.write_arxiv_autotex(archive_proj_info)
