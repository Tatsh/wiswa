"""Tests for Jsonnet evaluation."""

from __future__ import annotations

from pathlib import Path
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


async def test_evaluate_jsonnet_file_merged_settings_invalid_json(mocker: MockerFixture) -> None:
    mock_cb = mocker.patch('wiswa.utils.jsonnet._make_native_callbacks')
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '"ok"'
    mock_session = MagicMock()
    await evaluate_jsonnet_file(['/lib'], MagicMock(), 'not valid json{{{', session=mock_session)
    mock_cb.assert_called_once()
    assert mock_cb.call_args.kwargs['merged_settings'] is None


async def test_evaluate_jsonnet_file_merged_settings_json_not_object(mocker: MockerFixture) -> None:
    mock_cb = mocker.patch('wiswa.utils.jsonnet._make_native_callbacks')
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '"ok"'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '[1, 2]', session=MagicMock())
    mock_cb.assert_called_once()
    assert mock_cb.call_args.kwargs['merged_settings'] is None


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
    assert native_callbacks['githubLatestReleaseTag'][0] == ('o', 'r', 'g')
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
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
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


@pytest.mark.parametrize(
    ('origin_url', 'expected_owner'),
    [
        ('git://github.com/proto_owner/proto_repo.git', 'proto_owner'),
        ('ssh://git@github.com/ssh_owner/ssh_repo.git', 'ssh_owner'),
        ('https://www.github.com/www_owner/repo', 'www_owner'),
    ],
)
async def test_github_username_native_git_remote_url_schemes(
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


async def test_worktree_without_commondir_yields_only_worktree_config(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    repo = tmp_path / 'repo'
    git_main = repo / '.git'
    git_main.mkdir(parents=True)
    (git_main / 'config').write_text(
        '[remote "origin"]\n\turl = git@github.com:unused_main/x.git\n',
        encoding='utf-8',
    )
    wt_marker = git_main / 'worktrees' / 'wt'
    wt_marker.mkdir(parents=True)
    (wt_marker / 'config').write_text(
        '[remote "origin"]\n\turl = https://gitlab.com/wt/no_commondir.git\n',
        encoding='utf-8',
    )
    worktree = tmp_path / 'wt'
    worktree.mkdir()
    (worktree / '.git').write_text(f'gitdir: {wt_marker.as_posix()}\n', encoding='utf-8')
    monkeypatch.chdir(worktree)
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_github_username_native_worktree_commondir_dot_skips_duplicate_config_path(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    """``commondir`` ``.`` makes common git match the worktree directory.

    The same ``config`` path is then yielded twice and the second is skipped.
    """
    repo = tmp_path / 'repo'
    git_main = repo / '.git'
    git_main.mkdir(parents=True)
    (git_main / 'config').write_text(
        '[remote "origin"]\n\turl = git@github.com:unused_main/x.git\n',
        encoding='utf-8',
    )
    wt_marker = git_main / 'worktrees' / 'wt'
    wt_marker.mkdir(parents=True)
    (wt_marker / 'commondir').write_text('.\n')
    (wt_marker / 'config').write_text(
        '[remote "origin"]\n\turl = https://gitlab.com/group/proj.git\n',
        encoding='utf-8',
    )
    worktree = tmp_path / 'wt'
    worktree.mkdir()
    (worktree / '.git').write_text(f'gitdir: {wt_marker.as_posix()}\n', encoding='utf-8')
    monkeypatch.chdir(worktree)
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_github_username_native_gitlab_origin_then_github(tmp_path: Path,
                                                                monkeypatch: pytest.MonkeyPatch,
                                                                mocker: MockerFixture) -> None:
    repo = tmp_path / 'repo'
    git_main = repo / '.git'
    git_main.mkdir(parents=True)
    (git_main / 'config').write_text(
        '[remote "origin"]\n\turl = git@github.com:good_owner/good_repo.git\n',
        encoding='utf-8',
    )
    wt_marker = git_main / 'worktrees' / 'wt'
    wt_marker.mkdir(parents=True)
    (wt_marker / 'commondir').write_text('../../')
    (wt_marker / 'config').write_text(
        '[remote "origin"]\n\turl = https://gitlab.com/group/proj.git\n',
        encoding='utf-8',
    )
    worktree = tmp_path / 'wt'
    worktree.mkdir()
    (worktree / '.git').write_text(f'gitdir: {wt_marker.as_posix()}\n', encoding='utf-8')
    monkeypatch.chdir(worktree)
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value='/usr/bin/gh')
    mock_run = mocker.patch('wiswa.utils.jsonnet.sp.run')
    mock_run.side_effect = sp.CalledProcessError(1, 'gh')
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'good_owner'


async def test_github_username_native_config_not_a_file_skipped(tmp_path: Path,
                                                                monkeypatch: pytest.MonkeyPatch,
                                                                mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').mkdir()
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_github_username_native_dot_git_read_oserror(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch,
                                                           mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    git_file = tmp_path / '.git'
    git_file.write_text('gitdir: /unused\n', encoding='utf-8')
    real_read_text = Path.read_text

    def busted_read_text(self: Path, encoding: str = 'utf-8', errors: str | None = None) -> str:
        if self.resolve() == git_file.resolve():
            msg = 'simulated read failure'
            raise OSError(msg)
        return real_read_text(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, 'read_text', busted_read_text)
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_github_username_native_invalid_git_config_ignored(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch,
                                                                 mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text('[\n', encoding='utf-8')
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_github_username_native_no_origin_section_unknown(tmp_path: Path,
                                                                monkeypatch: pytest.MonkeyPatch,
                                                                mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text('[core]\n    bare = false\n', encoding='utf-8')
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_github_username_native_non_github_remote_unknown(tmp_path: Path,
                                                                monkeypatch: pytest.MonkeyPatch,
                                                                mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text(
        '[remote "origin"]\n\turl = https://gitlab.com/acme/warehouse.git\n',
        encoding='utf-8',
    )
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_github_username_native_blank_remote_url_unknown(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch,
                                                               mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text('[remote "origin"]\n\turl =\n', encoding='utf-8')
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_github_username_native_whitespace_only_remote_url_unknown(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text('[remote "origin"]\n\turl =    \n', encoding='utf-8')
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_github_username_native_origin_without_url_key_unknown(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text(
        '[remote "origin"]\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n',
        encoding='utf-8',
    )
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_github_username_native_github_https_root_path_unknown(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text(
        '[remote "origin"]\n\turl = https://github.com/\n',
        encoding='utf-8',
    )
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_github_username_native_empty_gh_stdout_falls_back_to_git(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text(
        '[remote "origin"]\n\turl = git@github.com:fall_owner/x.git\n',
        encoding='utf-8',
    )
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value='/usr/bin/gh')
    mock_run = mocker.patch('wiswa.utils.jsonnet.sp.run')
    mock_run.return_value = mocker.MagicMock(stdout='\n')
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'fall_owner'


async def test_github_username_native_gh_timeout_unknown_without_git(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value='/usr/bin/gh')
    mock_run = mocker.patch('wiswa.utils.jsonnet.sp.run')
    mock_run.side_effect = sp.TimeoutExpired('gh', 9)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_git_metadata_file_without_gitdir_yields_nothing(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch,
                                                               mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.git').write_text('# no gitdir here\n', encoding='utf-8')
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


async def test_worktree_commondir_read_oserror_skips_common_yield(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch,
                                                                  mocker: MockerFixture) -> None:
    repo = tmp_path / 'repo'
    git_main = repo / '.git'
    git_main.mkdir(parents=True)
    (git_main / 'config').write_text(
        '[remote "origin"]\n\turl = git@github.com:skipped_common/x.git\n',
        encoding='utf-8',
    )
    wt_marker = git_main / 'worktrees' / 'wt'
    wt_marker.mkdir(parents=True)
    (wt_marker / 'commondir').write_text('../../')
    (wt_marker / 'config').write_text(
        '[remote "origin"]\n\turl = https://gitlab.com/group/proj.git\n',
        encoding='utf-8',
    )
    worktree = tmp_path / 'wt'
    worktree.mkdir()
    (worktree / '.git').write_text(f'gitdir: {wt_marker.as_posix()}\n', encoding='utf-8')
    monkeypatch.chdir(worktree)
    real_read_text = Path.read_text
    cd_file = wt_marker / 'commondir'

    def picky_read(self: Path, encoding: str = 'utf-8', errors: str | None = None) -> str:
        if self.resolve() == cd_file.resolve():
            msg = 'commondir read failed'
            raise OSError(msg)
        return real_read_text(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, 'read_text', picky_read)
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value=None)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == 'unknown'


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
