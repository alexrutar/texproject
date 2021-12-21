from click.testing import CliRunner
from pathlib import Path
from texproject.command import cli
from texproject.filesystem import template_linker
import pytest

def _verbose_invoke(runner, args):
    print(f"Calling with {args}")
    return runner.invoke(cli, args)

def _run_cmd_seq(runner, *args_list):
    results = (_verbose_invoke(runner, args) for args in args_list)
    assert all(res.exit_code == 0 for res in results)

@pytest.fixture
def fs_runner():
    print(f"Set up new environment.")
    runner = CliRunner()
    with runner.isolated_filesystem():
        yield runner

@pytest.mark.slow
@pytest.mark.parametrize("tname", template_linker.list_names())
def test_all_templates(fs_runner, tname):
    _run_cmd_seq(fs_runner,
        ['init', tname],
        ['validate'])

def test_archive(fs_runner):
    _run_cmd_seq(fs_runner,
            ['init', 'preprint'],
            ['archive', '--mode', 'arxiv', 'out.tar'])

def test_import(fs_runner):
    _run_cmd_seq(fs_runner,
            ['init', 'preprint'],
            ['import', '--macro', 'tikz'])
    cit_path = Path('test.bib')
    bibtext = 'example text'
    cit_path.write_text(bibtext)
    _run_cmd_seq(fs_runner,
            ['import', '--citation-path', str(cit_path)])
    assert Path('.texproject/citation-test.bib').read_text() == bibtext

def test_git(fs_runner):
    _run_cmd_seq(fs_runner,
            ['init', 'plain'],
            ['-n', 'git', 'init',
                '--repo-name', 'test_repo',
                '--repo-description', 'some description',
                '--no-wiki',
                '--issues',
                '--repo-visibility', 'private'])
