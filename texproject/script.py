from jinja2 import Environment, FileSystemLoader
import yaml
import datetime
from pathlib import Path


class ProjectGenerator:
    def __init__(self, template_name, project_name, citation_file):
        self.data_dir = Path.home() / Path(".local/share/texproj")
        self.config_dir = Path.home() / Path(".config/texproj")
        self.template_name = template_name
        self.project_name = project_name
        self.citation_file = citation_file

        self.conventions = {
                "project_macro_file" : "project-macros",
                "project_macro_file_contents" : "% project-specific macros\n",
                "macro_prefix" : "macros",
                "formatting_prefix" : "format",
                "citation_file" : "citations",
                "makefile" : "Makefile"}

        self.user_dict = yaml.load(
                (self.config_dir / 'info.yaml').read_text())

        self.template_dict = yaml.load(
                (self.data_dir / 'templates' / template_name / 'info.yaml').read_text())

        self.env = Environment(
                # jinja2 does not support PathLib objects
                loader=FileSystemLoader(searchpath=str(self.data_dir)),
                block_start_string="<*",
                block_end_string="*>",
                variable_start_string="<+",
                variable_end_string="+>",
                comment_start_string="<#",
                comment_end_string="#>",
                trim_blocks=True
                )

        self.output_folder = Path(project_name)

    def check_errors(self):
        pass
        # TODO errors to check:
        #  - template yaml file has all required components
        #  - all the macro files exist
        #  - all the formatting files exist

        # TODO: argument parsing, script creation, and packaging on pypi
        # TODO: bibliography management
        # - argument in .yaml file specifying bibliography style
        #   - if this argument exists
        #     - generate bibliography code within the latex automatically at the end
        #     - always create a citations.bib file (see bib source below)
        #     - create Makefile citation management argument
        #   - if this argument does not exist, do not create any of the above
        # - command line argument specifying the bibliography source
        #   - if this argument exists, link the citation source
        #   - if this argument does not exist, create an empty citations.bib file
        #   - if the argument exists but does yield something correct, warn and create an empty citations.bib file

        # TODO: maybe include a python script to do project management? (instead of makefile)
        #   - this would have to be a global script that can detect local params ... or a local copy of the script
        #   - or maybe generate some .project_info.yaml file? that lets you specify the values directly
        #     - then can run some global script to rebuild the corresponding pieces
        # - see Path.unlink and shutil.make_archive

        # TODO: rename skeleton.tex -> base.tex
        #       move skeleton.tex and Makefile to an "other" subdirectory of resources (cleaner)

        # TODO: migrate other template files to new templater

        # installation script?

    def create_tex_file(self):
        template = self.env.get_template(str(Path('templates', self.template_name, 'document.tex')))

        return template.render(
            project_name = self.project_name,
            user_dict = self.user_dict,
            template_dict = self.template_dict,
            conventions = self.conventions,
            date=datetime.date.today())

    def create_makefile(self):
        template = self.env.get_template(str(Path('resources', 'Makefile')))

        return template.render(project_name = self.project_name)


        #  return f".PHONY: export\n\nexport:\n\tzip {project_name}.zip *.bib *.tex *.pdf *.sty"

    def create_output_folder(self, out_folder, texfile, makefile):
        out_folder.mkdir()

        # write local files
        (out_folder / f"{self.project_name}.tex").write_text(tex_file)
        (out_folder / f"{self.conventions['makefile']}").write_text(makefile)
        (out_folder / f"{self.conventions['project_macro_file']}.sty").write_text(
                self.conventions['project_macro_file_contents'])

        # link macro and citation files from resources
        res_dir = self.data_dir / 'resources'
        for macro in self.template_dict['macros']:
            (out_folder / f"{self.conventions['macro_prefix']}-{macro}.sty").symlink_to(
                res_dir / 'packages' / 'macros' / f"{macro}.sty")
        (out_folder / f"{self.conventions['formatting_prefix']}-{self.template_dict['formatting']}.sty").symlink_to(
                res_dir / 'packages' / 'formatting' / f"{self.template_dict['formatting']}.sty")
        (out_folder / f"{self.conventions['citation_file']}.bib").symlink_to(
                res_dir / 'citations' / f'{self.citation_file}.bib')




if __name__ == "__main__":
    template_name = "preprint"
    project_name = "almost_arith_proj"
    citation_file = 'main'

    out_folder = Path(project_name)

    proj_gen = ProjectGenerator(template_name, project_name, citation_file)

    # generate file contents and write to folder
    tex_file = proj_gen.create_tex_file()
    makefile = proj_gen.create_makefile()
    proj_gen.create_output_folder(out_folder, tex_file, makefile)

