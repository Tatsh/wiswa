from __future__ import annotations

from typing import TYPE_CHECKING

from wiswa.main import main

if TYPE_CHECKING:
    from click.testing import CliRunner
    from pytest_mock import MockerFixture


def test_main(runner: CliRunner, mocker: MockerFixture) -> None:
    """Test main function."""
    mocker.patch('wiswa.main._jsonnet')
    result = runner.invoke(main)
    assert result.exit_code == 0
