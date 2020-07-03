import sys
import argparse

from . import __version__, __repo__
from .scripts import create_new_project, create_export, refresh_links
from .filesystem import TPR_INFO_FILENAME

def _run_new(args):
    create_new_project(args.template[0],args.output[0],args.citations)

def _run_export(args):
    create_export()

def _run_refresh(args):
    refresh_links()

def main():
    """Main argument parser"""
    parser = argparse.ArgumentParser(prog="texproject",description='An automatic LaTeX project manager.')
    parser.add_argument('-v','--verbose',
            action='store_true',
            default=False,
            dest='verbose',
            help='run verbose mode')
    parser.add_argument('--version',
            action='version',
            version='%(prog)s {}'.format(__version__))

    subparsers = parser.add_subparsers(help="")

    parser_new = subparsers.add_parser('new', help='create a new project')
    parser_new.set_defaults(func=_run_new)

    parser_new.add_argument('template',
            type=str,
            nargs=1,
            help='the name of the template to use')

    parser_new.add_argument('output',
            type=str,
            nargs=1,
            help='the name of the project you want to create')
    parser_new.add_argument('-c','--citations',
            type=str,
            nargs='*',
            dest='citations',
            default=[],
            help='specify citation files')


    parser_export = subparsers.add_parser('export', help='generate a self-contained zip file')
    parser_export.set_defaults(func=_run_export)

    parser_refresh = subparsers.add_parser('refresh', help=f'regenerate symlinks according to {TPR_INFO_FILENAME}')
    parser_refresh.set_defaults(func=_run_refresh)
    #  parser_update = subparsers.add_parser('update', help='update an existing file')
    #  parser_update.set_defaults(func=_tn_update)
    #  parser_update.add_argument('target',
            #  type=str,
            #  nargs=1,
            #  help='the name of the file to update')
    #  parser_update.add_argument('template',
            #  type=str,
            #  nargs=1,
            #  help='the name of the template to update with')
    #  parser_update.add_argument("-f","--keep-formatting",
            #  dest="format",
            #  action="store_true",
            #  default=False,
            #  help="preserve the formatting block")
    #  parser_update.add_argument("-t","--transfer",
            #  nargs="*",
            #  default=['file-specific preamble', 'main document'],
            #  help="provide a list of blocks to transfer")

    #  parser_check = subparsers.add_parser('check', help='check templates for errors')
    #  parser_check.set_defaults(func=_tn_check)
    #  parser_check.add_argument('-p','--package',
            #  dest="package",
            #  action="store_true",
            #  default=False,
            #  help="specify a list of packages to update")
    #  parser_check.add_argument('names',
            #  nargs="*",
            #  default=False,
            #  help="check all existing templates for errors")
    #  parser_check.add_argument('-a', "--all",
            #  action="store_true",
            #  default=False,
            #  dest="all",
            #  help="check all existing templates for errors")

    #  parser_info = subparsers.add_parser('info', help='display information about texnew')
    #  parser_info.set_defaults(func=_tn_info)
    #  parser_info.add_argument('-l', "--list",
            #  action="store_true",
            #  default=False,
            #  dest="lst",
            #  help="list existing templates")
    #  parser_info.add_argument('-d', "--directory",
            #  action="store_true",
            #  default=False,
            #  dest="dir",
            #  help="display path to the root folder")
    #  parser_info.add_argument('-r', "--repository",
            #  action="store_true",
            #  default=False,
            #  dest="repo",
            #  help="display the link to the repository")

    args = parser.parse_args()
    #  _parse_errors(args)

    try:
        args.func(args)
    except AttributeError:
        parser.print_help(sys.stderr)
        sys.exit(1)
