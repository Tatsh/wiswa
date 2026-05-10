"""Tests for Jsonnet evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
import json
import subprocess as sp

from wiswa.utils.jsonnet import (
    FlatpakConfigurationError,
    RemoteHostConflictError,
    evaluate_jsonnet_file,
    evaluate_jsonnet_project,
    evaluate_merged_settings,
    resolve_defaults_only,
    validate_flatpak_app_id,
    validate_remote_host_flags,
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


async def test_evaluate_jsonnet_file_session_exposes_ref_commit_sha_callback(
        mocker: MockerFixture) -> None:
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}', session=MagicMock())
    native_callbacks = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']
    assert 'githubRefCommitSha' in native_callbacks
    arg_names, _fn = native_callbacks['githubRefCommitSha']
    assert arg_names == ('o', 'r', 'f')


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
    mocker.patch('wiswa.utils.jsonnet.evaluate_jsonnet_file',
                 return_value='{"sub/file.txt": "hello content"}')
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


@pytest.mark.parametrize('filename', ['vcpkg.json', 'vcpkg-configuration.json'])
async def test_evaluate_jsonnet_project_vcpkg_no_trailing_newline(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch,
                                                                  mocker: MockerFixture,
                                                                  filename: str) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    payload = json.dumps({filename: '{\n  "name": "x"\n}'})
    mocker.patch('wiswa.utils.jsonnet.evaluate_jsonnet_file', return_value=payload)
    await evaluate_jsonnet_project(lib_path, [str(lib_path)], '{}')
    written = (tmp_path / filename).read_text()
    assert not written.endswith('\n')


async def test_evaluate_jsonnet_project_other_json_keeps_trailing_newline(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    payload = json.dumps({'package.json': '{\n  "name": "x"\n}'})
    mocker.patch('wiswa.utils.jsonnet.evaluate_jsonnet_file', return_value=payload)
    await evaluate_jsonnet_project(lib_path, [str(lib_path)], '{}')
    written = (tmp_path / 'package.json').read_text()
    assert written.endswith('\n')


async def test_evaluate_jsonnet_project_vcpkg_in_subdir_no_trailing_newline(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    payload = json.dumps({'nested/dir/vcpkg.json': '{\n  "name": "x"\n}'})
    mocker.patch('wiswa.utils.jsonnet.evaluate_jsonnet_file', return_value=payload)
    await evaluate_jsonnet_project(lib_path, [str(lib_path)], '{}')
    written = (tmp_path / 'nested' / 'dir' / 'vcpkg.json').read_text()
    assert not written.endswith('\n')


def test_validate_flatpak_app_id_skips_when_disabled() -> None:
    validate_flatpak_app_id({'want_flatpak': False})


def test_validate_flatpak_app_id_accepts_flathub() -> None:
    validate_flatpak_app_id({'want_flatpak': True, 'publishing': {'flathub': 'org.example.App'}})


def test_validate_flatpak_app_id_empty_flathub_raises() -> None:
    with pytest.raises(FlatpakConfigurationError, match=r'publishing\.flathub'):
        validate_flatpak_app_id({'want_flatpak': True, 'publishing': {'flathub': ''}})


def test_validate_flatpak_app_id_publishing_not_dict_raises() -> None:
    with pytest.raises(FlatpakConfigurationError, match=r'publishing\.flathub'):
        validate_flatpak_app_id({'want_flatpak': True, 'publishing': None})


def test_validate_remote_host_flags_accepts_mutually_exclusive() -> None:
    validate_remote_host_flags({'using_github': True})
    validate_remote_host_flags({'using_gitlab': True})
    validate_remote_host_flags({})


def test_validate_remote_host_flags_raises_when_both_hosts() -> None:
    with pytest.raises(RemoteHostConflictError, match='using_github and using_gitlab'):
        validate_remote_host_flags({'using_github': True, 'using_gitlab': True})


def _patch_evaluate_merged_settings_mocks(
        mocker: MockerFixture,
        *,
        user_defaults_exists: bool = False,
        user_defaults_text: str = '{}',
        readme_exists: bool = False,
        established_pytest: bool = False,
        evaluate_snippet_return: str = '{"project_type": "python"}') -> MagicMock:
    mocker.patch('wiswa.utils.jsonnet.run_sync',
                 new_callable=AsyncMock,
                 side_effect=lambda func, *_a, **_kw: func())
    mocker.patch('wiswa.utils.jsonnet.json.loads', wraps=json.loads)

    def make_path(*args: object, **_kwargs: object) -> MagicMock:
        raw = args[0] if args else ''
        ps = raw if isinstance(raw, str) else str(raw)
        inst = MagicMock()
        inst.read_text = AsyncMock(return_value='{}')
        inst.exists = AsyncMock(return_value=False)
        if 'defaults.libsonnet' in ps:
            inst.read_text = AsyncMock(return_value='{ project_type: "python" }')
        elif ps.endswith('defaults.jsonnet'):
            inst.exists = AsyncMock(return_value=user_defaults_exists)
            inst.read_text = AsyncMock(return_value=user_defaults_text)
        elif ps.endswith('README.md'):
            inst.exists = AsyncMock(return_value=readme_exists)
        return inst

    mocker.patch('wiswa.utils.jsonnet.anyio.Path', side_effect=make_path)
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_snippet.return_value = evaluate_snippet_return
    mocker.patch('wiswa.utils.jsonnet.tests_dir_has_pytest_modules_excluding_starter_main',
                 new_callable=AsyncMock,
                 return_value=established_pytest)
    return mock_jsonnet


async def test_evaluate_merged_settings_mocks_jsonnet_anyio_and_pytest_scan(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path', return_value=tmp_path / 'cfg')
    mock_jsonnet = _patch_evaluate_merged_settings_mocks(mocker)
    merged_json, merged = await evaluate_merged_settings([str(lib_path)], lib_path, '{}')
    assert merged_json == '{"project_type": "python"}'
    assert merged['project_type'] == 'python'
    assert merged['_readme_existed'] is False
    assert merged['_has_established_pytest_modules'] is False
    mock_jsonnet.evaluate_snippet.assert_called_once()
    tla = mock_jsonnet.evaluate_snippet.call_args.kwargs['tla_codes']
    assert tla['user_defaults'] == '{}'


async def test_evaluate_merged_settings_mocks_user_defaults_file_missing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path', return_value=tmp_path / 'cfg')
    mock_jsonnet = _patch_evaluate_merged_settings_mocks(mocker, user_defaults_exists=False)
    settings = '{ uses_user_defaults: true }\n'
    _merged_json, _merged = await evaluate_merged_settings([str(lib_path)], lib_path, settings)
    tla = mock_jsonnet.evaluate_snippet.call_args.kwargs['tla_codes']
    assert tla['user_defaults'] == '{}'


async def test_evaluate_merged_settings_mocks_user_defaults_readme_pytest(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    lib_path = tmp_path / 'lib'
    lib_path.mkdir()
    mocker.patch('wiswa.utils.jsonnet.platformdirs.user_config_path', return_value=tmp_path / 'cfg')
    mock_jsonnet = _patch_evaluate_merged_settings_mocks(mocker,
                                                         user_defaults_exists=True,
                                                         user_defaults_text='{ extra: true }',
                                                         readme_exists=True,
                                                         established_pytest=True)
    settings = '{ uses_user_defaults: true }\n'
    merged_json, merged = await evaluate_merged_settings([str(lib_path)], lib_path, settings)
    assert merged_json == '{"project_type": "python"}'
    assert merged['_readme_existed'] is True
    assert merged['_has_established_pytest_modules'] is True
    tla = mock_jsonnet.evaluate_snippet.call_args.kwargs['tla_codes']
    assert tla['user_defaults'] == '{ extra: true }'
    assert tla['settings'] == settings


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
    assert native_callbacks['latestPypiPackageVersion'][0] == ('p', 'h', 'py')
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


@pytest.mark.parametrize(('origin_url', 'expected_owner'),
                         [('git@github.com:some_owner/some_repo.git', 'some_owner'),
                          ('https://github.com/other_owner/x.git', 'other_owner')])
async def test_github_username_native_falls_back_to_git_origin(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch,
                                                               mocker: MockerFixture,
                                                               origin_url: str,
                                                               expected_owner: str) -> None:
    monkeypatch.chdir(tmp_path)
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value='/usr/bin/gh')
    mock_run = mocker.patch('wiswa.utils.jsonnet.sp.run')
    mock_run.side_effect = sp.CalledProcessError(1, 'gh')
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text(f'[remote "origin"]\n\turl = {origin_url}\n', encoding='utf-8')
    mock_jsonnet = mocker.patch('wiswa.utils.jsonnet._jsonnet')
    mock_jsonnet.evaluate_file.return_value = '{}'
    await evaluate_jsonnet_file(['/lib'], MagicMock(), '{}')
    callback = mock_jsonnet.evaluate_file.call_args[1]['native_callbacks']['githubCliUsername'][1]
    assert callback() == expected_owner


@pytest.mark.parametrize(('origin_url', 'expected_owner'),
                         [('git://github.com/proto_owner/proto_repo.git', 'proto_owner'),
                          ('ssh://git@github.com/ssh_owner/ssh_repo.git', 'ssh_owner'),
                          ('https://www.github.com/www_owner/repo', 'www_owner')])
async def test_github_username_native_git_remote_url_schemes(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch,
                                                             mocker: MockerFixture, origin_url: str,
                                                             expected_owner: str) -> None:
    monkeypatch.chdir(tmp_path)
    mocker.patch('wiswa.utils.jsonnet.shutil.which', return_value='/usr/bin/gh')
    mock_run = mocker.patch('wiswa.utils.jsonnet.sp.run')
    mock_run.side_effect = sp.CalledProcessError(1, 'gh')
    git_dir = tmp_path / '.git'
    git_dir.mkdir()
    (git_dir / 'config').write_text(f'[remote "origin"]\n\turl = {origin_url}\n', encoding='utf-8')
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
        '[remote "origin"]\n\turl = git@github.com:unused_main/x.git\n', encoding='utf-8')
    wt_marker = git_main / 'worktrees' / 'wt'
    wt_marker.mkdir(parents=True)
    (wt_marker / 'config').write_text(
        '[remote "origin"]\n\turl = https://gitlab.com/wt/no_commondir.git\n', encoding='utf-8')
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
    """``commondir`` ``.`` makes common Git match the worktree directory.

    The same ``config`` path is then yielded twice and the second is skipped.
    """
    repo = tmp_path / 'repo'
    git_main = repo / '.git'
    git_main.mkdir(parents=True)
    (git_main / 'config').write_text(
        '[remote "origin"]\n\turl = git@github.com:unused_main/x.git\n', encoding='utf-8')
    wt_marker = git_main / 'worktrees' / 'wt'
    wt_marker.mkdir(parents=True)
    (wt_marker / 'commondir').write_text('.\n')
    (wt_marker / 'config').write_text(
        '[remote "origin"]\n\turl = https://gitlab.com/group/proj.git\n', encoding='utf-8')
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
        '[remote "origin"]\n\turl = git@github.com:good_owner/good_repo.git\n', encoding='utf-8')
    wt_marker = git_main / 'worktrees' / 'wt'
    wt_marker.mkdir(parents=True)
    (wt_marker / 'commondir').write_text('../../')
    (wt_marker / 'config').write_text(
        '[remote "origin"]\n\turl = https://gitlab.com/group/proj.git\n', encoding='utf-8')
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
        '[remote "origin"]\n\turl = https://gitlab.com/acme/warehouse.git\n', encoding='utf-8')
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
        '[remote "origin"]\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n', encoding='utf-8')
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
    (git_dir / 'config').write_text('[remote "origin"]\n\turl = https://github.com/\n',
                                    encoding='utf-8')
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
    (git_dir / 'config').write_text('[remote "origin"]\n\turl = git@github.com:fall_owner/x.git\n',
                                    encoding='utf-8')
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
        '[remote "origin"]\n\turl = git@github.com:skipped_common/x.git\n', encoding='utf-8')
    wt_marker = git_main / 'worktrees' / 'wt'
    wt_marker.mkdir(parents=True)
    (wt_marker / 'commondir').write_text('../../')
    (wt_marker / 'config').write_text(
        '[remote "origin"]\n\turl = https://gitlab.com/group/proj.git\n', encoding='utf-8')
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
