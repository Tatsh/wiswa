"""Tests for the main CLI entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from click.testing import CliRunner
from wiswa.main import main
import niquests
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    'args',
    [
        [],
        ['--debug'],
        ['-d'],
    ],
)
def test_main_basic_invocation(args: list[str], mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    result = runner.invoke(main, [*args, str(file_path)])
    assert result.exit_code == 0


@pytest.mark.parametrize(
    ('skip_flag', 'called'),
    [
        ('--skip-github', False),
        ('', True),
    ],
)
def test_main_skip_github(
    skip_flag: str,
    called: bool,  # noqa: FBT001
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    setup_github = mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)
    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    args = [str(file_path)]
    if skip_flag:
        args.insert(0, skip_flag)
    result = runner.invoke(main, args, catch_exceptions=False)
    assert result.exit_code == 0
    assert setup_github.called is called


@pytest.mark.parametrize(
    ('skip_flag', 'func_name'),
    [
        ('--skip-jsonnet', 'evaluate_jsonnet_project'),
        ('--skip-templates', 'write_templated_files'),
    ],
)
def test_main_skip_flags(skip_flag: str, func_name: str, mocker: MockerFixture,
                         tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
        ),
    )
    eval_jsonnet = mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    write_templates = mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    args = [skip_flag, str(file_path)]
    result = runner.invoke(main, args, catch_exceptions=False)
    assert result.exit_code == 0
    match func_name:
        case 'evaluate_jsonnet_project':
            assert not eval_jsonnet.called
        case 'write_templated_files':
            assert not write_templates.called


def test_main_stubs_only_skips_create_py_typed_files(mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            {
                'project_type': 'python',
                'stubs_only': True,
                'yarn_version': '1.0.0'
            },
            {
                'project_type': 'python',
                'stubs_only': True,
                'yarn_version': '1.0.0'
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    create_py_typed = mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    result = runner.invoke(main, [str(file_path)], catch_exceptions=False)
    assert result.exit_code == 0
    assert not create_py_typed.called


def test_main_jpath_option_passed(mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    eval_merged = mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    jpath1 = str(tmp_path / 'lib1')
    jpath2 = str(tmp_path / 'lib2')
    result = runner.invoke(
        main,
        ['--jpath', jpath1, '--jpath', jpath2, str(file_path)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    args, _kwargs = eval_merged.call_args
    assert jpath1 in args[0]
    assert jpath2 in args[0]


def _make_http_error(
    status_code: int,
    headers: dict[str, str] | None = None,
    url: str = 'https://api.github.com/repos/test',
) -> niquests.HTTPError:
    mock_request = MagicMock()
    mock_request.url = url
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.headers = headers or {}
    error = niquests.HTTPError(response=mock_response)
    error.request = mock_request
    return error


def _setup_main_mocks(mocker: MockerFixture, tmp_path: Path,
                      side_effect: Exception) -> tuple[Path, type[object]]:
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock, side_effect=side_effect)

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    return file_path, DummyContextManager


def test_main_http_403_rate_limited(mocker: MockerFixture, tmp_path: Path) -> None:
    error = _make_http_error(403, {'X-RateLimit-Remaining': '0'})
    file_path, _ = _setup_main_mocks(mocker, tmp_path, side_effect=error)
    runner = CliRunner()
    result = runner.invoke(main, [str(file_path)])
    assert result.exit_code != 0
    assert 'Rate limited by api.github.com.' in result.output
    assert 'Please wait a few minutes before trying again.' in result.output


def test_main_http_429_with_retry_after(mocker: MockerFixture, tmp_path: Path) -> None:
    error = _make_http_error(429, {'Retry-After': '60'})
    file_path, _ = _setup_main_mocks(mocker, tmp_path, side_effect=error)
    runner = CliRunner()
    result = runner.invoke(main, [str(file_path)])
    assert result.exit_code != 0
    assert 'HTTP 429 from api.github.com.' in result.output
    assert 'Retry after 60 seconds.' in result.output


def test_main_http_403_no_rate_limit_headers(mocker: MockerFixture, tmp_path: Path) -> None:
    error = _make_http_error(403)
    file_path, _ = _setup_main_mocks(mocker, tmp_path, side_effect=error)
    runner = CliRunner()
    result = runner.invoke(main, [str(file_path)])
    assert result.exit_code != 0
    assert 'HTTP 403 from api.github.com.' in result.output
    assert 'Please wait a few minutes before trying again.' in result.output


def test_main_http_429_rate_limited_with_retry_after(mocker: MockerFixture, tmp_path: Path) -> None:
    error = _make_http_error(429, {'X-RateLimit-Remaining': '0', 'Retry-After': '120'})
    file_path, _ = _setup_main_mocks(mocker, tmp_path, side_effect=error)
    runner = CliRunner()
    result = runner.invoke(main, [str(file_path)])
    assert result.exit_code != 0
    assert 'Rate limited by api.github.com.' in result.output
    assert 'Retry after 120 seconds.' in result.output


def test_main_http_error_non_rate_limit_status(mocker: MockerFixture, tmp_path: Path) -> None:
    error = _make_http_error(500)
    file_path, _ = _setup_main_mocks(mocker, tmp_path, side_effect=error)
    runner = CliRunner()
    result = runner.invoke(main, [str(file_path)])
    assert result.exit_code != 0
    assert 'Aborted!' in result.output


def test_main_http_error_no_response(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_request = MagicMock()
    mock_request.url = 'https://unknown'
    mock_response = MagicMock()
    mock_response.status_code = 0
    mock_response.headers = {}
    error = niquests.HTTPError(response=mock_response)
    error.request = mock_request
    file_path, _ = _setup_main_mocks(mocker, tmp_path, side_effect=error)
    runner = CliRunner()
    result = runner.invoke(main, [str(file_path)])
    assert result.exit_code != 0
    assert 'Aborted!' in result.output


def test_main_legacy_poetry_deps_warning(mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            '{}',
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0',
                'package_manager': 'uv',
                'python_deps': {
                    'main': {
                        'click': '>=8',
                    },
                },
                'pyproject': {
                    'project': {
                        'dependencies': ['click>=8', 'requests>=2'],
                    },
                    'dependency-groups': {},
                    'tool': {
                        'poetry': {
                            'dependencies': {
                                'requests': '^2',
                            },
                        },
                    },
                },
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)
    mock_log = mocker.patch('wiswa.main.log')

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    result = runner.invoke(main, [str(file_path)], catch_exceptions=False)
    assert result.exit_code == 0
    mock_log.warning.assert_called_once()
    assert 'deprecated' in mock_log.warning.call_args[0][0]


def test_main_legacy_poetry_group_deps_warning(mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            '{}',
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0',
                'package_manager': 'uv',
                'python_deps': {
                    'main': {},
                },
                'pyproject': {
                    'project': {
                        'dependencies': [],
                    },
                    'dependency-groups': {},
                    'tool': {
                        'poetry': {
                            'group': {
                                'dev': {
                                    'dependencies': {
                                        'pytest': '^8',
                                    },
                                },
                            },
                        },
                    },
                },
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)
    mock_log = mocker.patch('wiswa.main.log')

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    result = runner.invoke(main, [str(file_path)], catch_exceptions=False)
    assert result.exit_code == 0
    mock_log.warning.assert_called_once()
    assert 'deprecated' in mock_log.warning.call_args[0][0]


def test_main_no_legacy_deps_no_warning(mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            '{}',
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0',
                'package_manager': 'uv',
                'python_deps': {
                    'main': {
                        'click': '>=8',
                    },
                },
                'pyproject': {
                    'project': {
                        'dependencies': ['click>=8'],
                    },
                    'dependency-groups': {},
                },
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)
    mock_log = mocker.patch('wiswa.main.log')

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    result = runner.invoke(main, [str(file_path)], catch_exceptions=False)
    assert result.exit_code == 0
    mock_log.warning.assert_not_called()


def test_main_runtime_error(mocker: MockerFixture, tmp_path: Path) -> None:
    error = RuntimeError('RUNTIME ERROR: Something went wrong')
    file_path, _ = _setup_main_mocks(mocker, tmp_path, side_effect=error)
    runner = CliRunner()
    result = runner.invoke(main, [str(file_path)])
    assert result.exit_code != 0
    assert 'Something went wrong' in result.output


def test_main_runtime_error_could_not_get_latest_tag(mocker: MockerFixture, tmp_path: Path) -> None:
    error = RuntimeError('Could not get latest tag for owner/repo.')
    file_path, _ = _setup_main_mocks(mocker, tmp_path, side_effect=error)
    runner = CliRunner()
    result = runner.invoke(main, [str(file_path)])
    assert result.exit_code != 0
    assert 'rate limiting' in result.output.lower() or 'GitHub API' in result.output


def test_main_generic_exception(mocker: MockerFixture, tmp_path: Path) -> None:
    error = TypeError('unexpected error')
    file_path, _ = _setup_main_mocks(mocker, tmp_path, side_effect=error)
    runner = CliRunner()
    result = runner.invoke(main, [str(file_path)])
    assert result.exit_code != 0
    assert 'Aborted!' in result.output


@pytest.mark.parametrize(
    ('skip_flag', 'func_name'),
    [
        ('--skip-yarn', 'download_yarn'),
        ('--skip-static', 'copy_static_files'),
        ('--skip-postprocess', 'post_process_steps'),
    ],
)
def test_main_new_skip_flags(skip_flag: str, func_name: str, mocker: MockerFixture,
                             tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mock_download_yarn = mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mock_copy_static = mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mock_post_process = mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    result = runner.invoke(main, [skip_flag, str(file_path)], catch_exceptions=False)
    assert result.exit_code == 0
    mocks = {
        'download_yarn': mock_download_yarn,
        'copy_static_files': mock_copy_static,
        'post_process_steps': mock_post_process,
    }
    assert not mocks[func_name].called


def test_main_no_cache_flag(mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)
    mock_cached_session = mocker.patch('wiswa.main.cached_session')

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    result = runner.invoke(main, ['--no-cache', str(file_path)], catch_exceptions=False)
    assert result.exit_code == 0
    mock_cached_session.assert_called_once()
    call_kwargs = mock_cached_session.call_args[1]
    assert call_kwargs['no_cache'] is True


def test_main_cache_time_option(mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)
    mock_cached_session = mocker.patch('wiswa.main.cached_session')

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    result = runner.invoke(main, ['--cache-time', '120', str(file_path)], catch_exceptions=False)
    assert result.exit_code == 0
    mock_cached_session.assert_called_once()
    from datetime import timedelta
    call_kwargs = mock_cached_session.call_args[1]
    assert call_kwargs['expire_after'] == timedelta(seconds=120)


def test_main_output_dir_option(mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    output_dir = tmp_path / 'out'
    output_dir.mkdir()
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
        ),
    )
    eval_jsonnet = mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    result = runner.invoke(main, ['-o', str(output_dir), str(file_path)], catch_exceptions=False)
    assert result.exit_code == 0
    call_kwargs = eval_jsonnet.call_args[1]
    assert call_kwargs['output_dir'] == output_dir


def test_main_quiet_flag(mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0'
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    result = runner.invoke(main, ['-q', str(file_path)], catch_exceptions=False)
    assert result.exit_code == 0
    assert 'Done.' not in result.output


def test_main_has_legacy_poetry_deps_not_uv(mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch(
        'wiswa.main.evaluate_merged_settings',
        new_callable=AsyncMock,
        return_value=(
            '{}',
            {
                'project_type': 'python',
                'stubs_only': False,
                'yarn_version': '1.0.0',
                'package_manager': 'poetry',
                'python_deps': {
                    'main': {},
                },
                'pyproject': {},
            },
        ),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project', new_callable=AsyncMock)
    mocker.patch('wiswa.main.write_templated_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn', new_callable=AsyncMock)
    mocker.patch('wiswa.main.download_yarn_plugins', new_callable=AsyncMock)
    mocker.patch('wiswa.main.copy_static_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.create_py_typed_files', new_callable=AsyncMock)
    mocker.patch('wiswa.main.post_process_steps', new_callable=AsyncMock)
    mocker.patch('wiswa.main.setup_github_project', new_callable=AsyncMock)
    mock_log = mocker.patch('wiswa.main.log')

    class DummyContextManager:
        def __init__(self, value: object) -> None:
            self.value: object = value

        def __enter__(self) -> object:
            return self.value

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: object,
        ) -> None:
            return None

    mocker.patch('importlib.resources.files', side_effect=lambda _: tmp_path)
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    result = runner.invoke(main, [str(file_path)], catch_exceptions=False)
    assert result.exit_code == 0
    mock_log.warning.assert_not_called()
