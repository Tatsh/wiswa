"""Tests for Jsonnet evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock
import subprocess as sp

from wiswa.utils.jsonnet import (
    evaluate_jsonnet_file,
    evaluate_jsonnet_project,
    evaluate_merged_settings,
    resolve_defaults_only,
)
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


async def test_evaluate_jsonnet_file(mocker: MockerFixture) -> None:
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{"key": "value"}'
    result = await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    assert result == '{"key": "value"}'
    mock_jsonnet.evaluate_file.assert_called_once()
    native_callbacks = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']
    assert 'githubCliUsername' in native_callbacks


async def test_evaluate_jsonnet_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                        mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'project.jsonnet').write_text('{}')
    mocker.patch('wiswa.utils.jsonnet.evaluate_jsonnet_file',
                 return_value='{"file.txt": "content"}')
    await evaluate_jsonnet_project(lib_path, [str(lib_path)], '{}')
    assert (tmp_path / 'file.txt').exists()


async def test_evaluate_jsonnet_project_with_output_dir(tmp_path: Path,
                                                        mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    output_dir = tmp_path / 'output'
    mocker.patch(
        'wiswa.utils.jsonnet.evaluate_jsonnet_file',
        return_value='{"sub/file.txt": "hello content"}',
    )
    await evaluate_jsonnet_project(lib_path, [str(lib_path)], '{}', output_dir=output_dir)
    assert output_dir.exists()
    assert (output_dir / 'sub/file.txt').exists()
    assert (output_dir / 'sub/file.txt').read_text().strip() == 'hello content'


async def test_evaluate_jsonnet_project_with_custom_file(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch,
                                                         mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    custom_file = tmp_path / 'custom.jsonnet'
    custom_file.write_text('{}')
    mocker.patch('wiswa.utils.jsonnet.evaluate_jsonnet_file', return_value='{"out.txt": "custom"}')
    await evaluate_jsonnet_project(lib_path, [str(lib_path)], '{}', file=custom_file)
    assert (tmp_path / 'out.txt').exists()


async def test_evaluate_jsonnet_project_default_output_dir(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch,
                                                           mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    mocker.patch('wiswa.utils.jsonnet.evaluate_jsonnet_file',
                 return_value='{"generated.txt": "gen content"}')
    await evaluate_jsonnet_project(lib_path, [str(lib_path)], '{}')
    assert (tmp_path / 'generated.txt').exists()
    assert (tmp_path / 'generated.txt').read_text().strip() == 'gen content'


async def test_evaluate_merged_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                        mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libsonnet').write_text('{ project_type: "python" }')
    mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
                 return_value='{"project_type": "python"}')
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path',
                 return_value=tmp_path / 'config')
    result_str, result_dict = await evaluate_merged_settings([str(lib_path)], lib_path, '{}')
    assert result_str == '{"project_type": "python"}'
    assert result_dict['project_type'] == 'python'
    assert '_readme_existed' in result_dict
    assert result_dict['_readme_existed'] is False
    assert result_dict['_has_established_pytest_modules'] is False


async def test_evaluate_merged_settings_user_defaults(tmp_path: Path,
                                                      mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libsonnet').write_text('{ project_type: "python" }')
    config_path = tmp_path / 'config'
    config_path.mkdir()
    (config_path / 'defaults.jsonnet').write_text('{ extra: true }')
    settings = '{ uses_user_defaults: true }\n'
    mock_eval = mocker.patch(
        'wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
        return_value='{"project_type": "python", "extra": true, "uses_user_defaults": true}',
    )
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path', return_value=config_path)
    _result_str, result_dict = await evaluate_merged_settings([str(lib_path)], lib_path, settings)
    assert 'project_type' in result_dict
    mock_eval.assert_called_once()
    assert mock_eval.call_args[1]['tla_codes']['user_defaults'] == '{ extra: true }'
    assert mock_eval.call_args[1]['tla_codes']['settings'] == settings


async def test_evaluate_merged_settings_user_defaults_missing_raises(tmp_path: Path,
                                                                     mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libsonnet').write_text('{}')
    config_path = tmp_path / 'config'
    config_path.mkdir()
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path', return_value=config_path)
    mock_eval = mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet', return_value='{}')
    with pytest.raises(FileNotFoundError):
        await evaluate_merged_settings([str(lib_path)], lib_path, '{ uses_user_defaults: true }\n')
    mock_eval.assert_not_called()


async def test_evaluate_merged_settings_single_pass_when_user_defaults_disabled(
        tmp_path: Path, mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libsonnet').write_text('{}')
    mock_eval = mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
                             return_value='{"uses_user_defaults": false}')
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path',
                 return_value=tmp_path / 'config')
    await evaluate_merged_settings([str(lib_path)], lib_path, '{}')
    mock_eval.assert_called_once()


async def test_evaluate_merged_settings_skips_user_file_without_literal(
        tmp_path: Path, mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libsonnet').write_text('{ project_type: "python" }')
    config_path = tmp_path / 'config'
    config_path.mkdir()
    (config_path / 'defaults.jsonnet').write_text('{ extra: true }')
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path', return_value=config_path)
    mock_eval = mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
                             return_value='{"project_type": "python"}')
    await evaluate_merged_settings([str(lib_path)], lib_path, '{}')
    mock_eval.assert_called_once()
    assert mock_eval.call_args[1]['tla_codes']['user_defaults'] == '{}'


async def test_resolve_defaults_only(tmp_path: Path, mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libsonnet').write_text('{ project_type: "python" }')
    mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
                 return_value='{"project_type": "python"}')
    result = await resolve_defaults_only([str(lib_path)], lib_path)
    assert result == {'project_type': 'python'}


async def test_evaluate_jsonnet_file_with_session(mocker: MockerFixture) -> None:
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{"key": "value"}'
    mock_session = MagicMock()
    result = await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}', session=mock_session)
    assert result == '{"key": "value"}'
    call_kwargs = mock_jsonnet.evaluate_file.call_args[1]
    native_callbacks = call_kwargs['native_callbacks']
    assert 'githubLatestActionTag' in native_callbacks
    assert 'githubLatestReleaseTag' in native_callbacks
    assert 'githubLatestTag' in native_callbacks
    assert 'latestNpmPackageVersion' in native_callbacks
    assert 'latestPypiPackageVersion' in native_callbacks
    assert 'latestYarnVersion' in native_callbacks
    assert 'githubCliUsername' in native_callbacks
    assert 'isodate' in native_callbacks
    assert 'year' in native_callbacks


async def test_resolve_defaults_only_passes_empty_overrides(tmp_path: Path,
                                                            mocker: MockerFixture) -> None:
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libsonnet').write_text('{ a: 1 }')
    mock_eval = mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
                             return_value='{"a": 1}')
    await resolve_defaults_only([str(lib_path)], lib_path)
    call_kwargs = mock_eval.call_args[1]
    assert call_kwargs['tla_codes']['settings'] == '{}'
    assert call_kwargs['tla_codes']['user_defaults'] == '{}'


async def test_native_callback_params_use_short_names(mocker: MockerFixture) -> None:
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    mock_session = MagicMock()
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}', session=mock_session)
    native_callbacks = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']
    assert native_callbacks['githubLatestActionTag'][0] == ('o', 'r')
    assert native_callbacks['githubLatestReleaseTag'][0] == ('o', 'r')
    assert native_callbacks['githubLatestTag'][0] == ('o', 'r')
    assert native_callbacks['latestNpmPackageVersion'][0] == ('p',)
    assert native_callbacks['latestPypiPackageVersion'][0] == ('p',)
    assert native_callbacks['githubCliUsername'][0] == ()
    assert native_callbacks['isodate'][0] == ()
    assert native_callbacks['latestYarnVersion'][0] == ()
    assert native_callbacks['year'][0] == ()


async def test_github_cli_username_native_returns_login(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value='/usr/bin/gh')
    mock_run = mocker.patch('wiswa.utils.jsonnet.sp.run')
    mock_run.return_value = mocker.MagicMock(stdout='gh_user_out\n')
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'gh_user_out'
    args, _kwargs = mock_run.call_args
    assert list(args[0]) == ['/usr/bin/gh', 'api', 'user', '--jq', '.login']


async def test_github_cli_username_native_returns_unknown_when_gh_missing(
        mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_run = mocker.patch('wiswa.utils.jsonnet.sp.run')
    mock_run.side_effect = AssertionError('gh should not run when not on PATH')
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


@pytest.mark.parametrize(
    ('origin_url', 'expected_owner'),
    [
        ('git@github.com:some_owner/some_repo.git', 'some_owner'),
        ('https://github.com/other_owner/x.git', 'other_owner'),
    ],
)
async def test_github_username_native_falls_back_to_git_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    origin_url: str,
    expected_owner: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value='/usr/bin/gh')
    mock_run = mocker.patch('wiswa.utils.jsonnet.sp.run')
    mock_run.side_effect = sp.CalledProcessError(1, 'gh')
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text(
        f'[remote "origin"]\n\turl = {origin_url}\n',
        encoding='utf-8',
    )
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == expected_owner


async def test_evaluate_merged_settings_established_pytest_modules(tmp_path: Path,
                                                                   monkeypatch: pytest.MonkeyPatch,
                                                                   mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libsonnet').write_text('{ project_type: "python" }')
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests' / 'test_foo.py').write_text('# x\n')
    mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
                 return_value='{"project_type": "python"}')
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path',
                 return_value=tmp_path / 'config')
    _result_str, result_dict = await evaluate_merged_settings([str(lib_path)], lib_path, '{}')
    assert result_dict['_has_established_pytest_modules'] is True


async def test_evaluate_merged_settings_only_test_main_not_established(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libsonnet').write_text('{ project_type: "python" }')
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests' / 'test_main.py').write_text('# x\n')
    mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
                 return_value='{"project_type": "python"}')
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path',
                 return_value=tmp_path / 'config')
    _result_str, result_dict = await evaluate_merged_settings([str(lib_path)], lib_path, '{}')
    assert result_dict['_has_established_pytest_modules'] is False


async def test_evaluate_merged_settings_conftest_only_not_established(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    (lib_path / 'defaults.libsonnet').write_text('{ project_type: "python" }')
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests' / 'conftest.py').write_text('# x\n')
    mocker.patch('wiswa.utils.jsonnet._jsonnet.evaluate_snippet',
                 return_value='{"project_type": "python"}')
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path',
                 return_value=tmp_path / 'config')
    _result_str, result_dict = await evaluate_merged_settings([str(lib_path)], lib_path, '{}')
    assert result_dict['_has_established_pytest_modules'] is False
