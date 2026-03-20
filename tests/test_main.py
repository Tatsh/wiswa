from __future__ import annotations

from typing import TYPE_CHECKING

from click.testing import CliRunner
from wiswa.main import main
import pytest
import requests

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
    mocker.patch('wiswa.main.evaluate_merged_settings',
                 return_value=({
                     'project_type': 'python',
                     'stubs_only': False,
                     'yarn_version': '1.0.0'
                 }, {
                     'project_type': 'python',
                     'stubs_only': False,
                     'yarn_version': '1.0.0'
                 }))
    mocker.patch('wiswa.main.evaluate_jsonnet_project')
    mocker.patch('wiswa.main.write_templated_files')
    mocker.patch('wiswa.main.download_yarn')
    mocker.patch('wiswa.main.download_yarn_plugins')
    mocker.patch('wiswa.main.copy_static_files')
    mocker.patch('wiswa.main.create_py_typed_files')
    mocker.patch('wiswa.main.post_process_steps')
    mocker.patch('wiswa.main.setup_github_project')

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

    mocker.patch('importlib.resources.files', side_effect=lambda _: DummyContextManager(tmp_path))
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
        tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch('wiswa.main.evaluate_merged_settings',
                 return_value=({
                     'project_type': 'python',
                     'stubs_only': False,
                     'yarn_version': '1.0.0'
                 }, {
                     'project_type': 'python',
                     'stubs_only': False,
                     'yarn_version': '1.0.0'
                 }))
    mocker.patch('wiswa.main.evaluate_jsonnet_project')
    mocker.patch('wiswa.main.write_templated_files')
    mocker.patch('wiswa.main.download_yarn')
    mocker.patch('wiswa.main.download_yarn_plugins')
    mocker.patch('wiswa.main.copy_static_files')
    mocker.patch('wiswa.main.create_py_typed_files')
    mocker.patch('wiswa.main.post_process_steps')
    setup_github = mocker.patch('wiswa.main.setup_github_project')
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
    mocker.patch('wiswa.main.evaluate_merged_settings',
                 return_value=({
                     'project_type': 'python',
                     'stubs_only': False,
                     'yarn_version': '1.0.0'
                 }, {
                     'project_type': 'python',
                     'stubs_only': False,
                     'yarn_version': '1.0.0'
                 }))
    eval_jsonnet = mocker.patch('wiswa.main.evaluate_jsonnet_project')
    write_templates = mocker.patch('wiswa.main.write_templated_files')
    mocker.patch('wiswa.main.download_yarn')
    mocker.patch('wiswa.main.download_yarn_plugins')
    mocker.patch('wiswa.main.copy_static_files')
    mocker.patch('wiswa.main.create_py_typed_files')
    mocker.patch('wiswa.main.post_process_steps')
    mocker.patch('wiswa.main.setup_github_project')

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

    mocker.patch('importlib.resources.files', side_effect=lambda _: DummyContextManager(tmp_path))
    mocker.patch('importlib.resources.as_file', side_effect=DummyContextManager)
    args = [skip_flag, str(file_path)]
    result = runner.invoke(main, args, catch_exceptions=False)
    assert result.exit_code == 0
    if func_name == 'evaluate_jsonnet_project':
        assert not eval_jsonnet.called
    if func_name == 'write_templated_files':
        assert not write_templates.called


def test_main_stubs_only_skips_create_py_typed_files(mocker: MockerFixture, tmp_path: Path) -> None:
    runner = CliRunner()
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch('wiswa.main.evaluate_merged_settings',
                 return_value=({
                     'project_type': 'python',
                     'stubs_only': True,
                     'yarn_version': '1.0.0'
                 }, {
                     'project_type': 'python',
                     'stubs_only': True,
                     'yarn_version': '1.0.0'
                 }))
    mocker.patch('wiswa.main.evaluate_jsonnet_project')
    mocker.patch('wiswa.main.write_templated_files')
    mocker.patch('wiswa.main.download_yarn')
    mocker.patch('wiswa.main.download_yarn_plugins')
    mocker.patch('wiswa.main.copy_static_files')
    create_py_typed = mocker.patch('wiswa.main.create_py_typed_files')
    mocker.patch('wiswa.main.post_process_steps')
    mocker.patch('wiswa.main.setup_github_project')

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

    mocker.patch('importlib.resources.files', side_effect=lambda _: DummyContextManager(tmp_path))
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
        return_value=({
            'project_type': 'python',
            'stubs_only': False,
            'yarn_version': '1.0.0'
        }, {
            'project_type': 'python',
            'stubs_only': False,
            'yarn_version': '1.0.0'
        }),
    )
    mocker.patch('wiswa.main.evaluate_jsonnet_project')
    mocker.patch('wiswa.main.write_templated_files')
    mocker.patch('wiswa.main.download_yarn')
    mocker.patch('wiswa.main.download_yarn_plugins')
    mocker.patch('wiswa.main.copy_static_files')
    mocker.patch('wiswa.main.create_py_typed_files')
    mocker.patch('wiswa.main.post_process_steps')
    mocker.patch('wiswa.main.setup_github_project')

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

    mocker.patch('importlib.resources.files', side_effect=lambda _: DummyContextManager(tmp_path))
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


def _make_http_error(status_code: int,
                     headers: dict[str, str] | None = None,
                     url: str = 'https://api.github.com/repos/test') -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    response.url = url
    if headers:
        response.headers.update(headers)
    return requests.HTTPError(response=response)


def _setup_main_mocks(mocker: MockerFixture, tmp_path: Path,
                      side_effect: Exception) -> tuple[Path, type[object]]:
    file_path = tmp_path / '.wiswa.jsonnet'
    file_path.write_text('{}\n')
    mocker.patch('wiswa.main.setup_logging')
    mocker.patch('wiswa.main.evaluate_merged_settings',
                 return_value=({
                     'project_type': 'python',
                     'stubs_only': False,
                     'yarn_version': '1.0.0'
                 }, {
                     'project_type': 'python',
                     'stubs_only': False,
                     'yarn_version': '1.0.0'
                 }))
    mocker.patch('wiswa.main.evaluate_jsonnet_project')
    mocker.patch('wiswa.main.write_templated_files')
    mocker.patch('wiswa.main.download_yarn')
    mocker.patch('wiswa.main.download_yarn_plugins')
    mocker.patch('wiswa.main.copy_static_files')
    mocker.patch('wiswa.main.create_py_typed_files')
    mocker.patch('wiswa.main.post_process_steps')
    mocker.patch('wiswa.main.setup_github_project', side_effect=side_effect)

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

    mocker.patch('importlib.resources.files', side_effect=lambda _: DummyContextManager(tmp_path))
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
    error = requests.HTTPError()
    error.response = None
    file_path, _ = _setup_main_mocks(mocker, tmp_path, side_effect=error)
    runner = CliRunner()
    result = runner.invoke(main, [str(file_path)])
    assert result.exit_code != 0
    assert 'Aborted!' in result.output
