from click.testing import CliRunner
from texproject.command import cli

def _verbose_invoke(runner, args):
    print(f"Calling with {args}")
    return runner.invoke(cli, args)

def _run_cmd_seq(*args_list):
    print(f"Set up new environment.")
    runner = CliRunner()
    with runner.isolated_filesystem():
        results = (_verbose_invoke(runner, args) for args in args_list)
        assert all(res.exit_code == 0 for res in results)


def test_all_templates():
    from texproject.filesystem import template_linker
    for tname in template_linker.list_names():
        _run_cmd_seq(
            ['init', tname],
            ['validate'])

def test_archive():
    _run_cmd_seq(
            ['init', 'preprint'],
            ['import', '--macro', 'tikz'],
            ['archive', '--mode', 'arxiv', 'out.tar'])

def test_git():
    _run_cmd_seq(
            ['init', 'plain'],
            ['-n', 'git', 'init',
                '--repo-name', 'test_repo',
                '--repo-description', 'some description',
                '--no-wiki',
                '--issues',
                '--repo-visibility', 'private'])
