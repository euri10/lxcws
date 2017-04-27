from click.testing import CliRunner

from lxcws import create, destroy


def test_create_then_destroy():
    runner = CliRunner()
    result = runner.invoke(create, ['-n', 'test_create'])
    assert result.exit_code == 0
    result = runner.invoke(destroy, ['-n', 'test_create'])
    assert result.exit_code == 0