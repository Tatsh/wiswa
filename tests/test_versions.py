"""Tests for version utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
import json
import logging
import math
import stat

from wiswa.utils.versions import (
    clear_resolution_caches,
    download_yarn,
    download_yarn_plugins,
    get_github_release_latest_tag,
    get_npm_latest_package_version,
    get_pypi_latest_package_version,
    resolve_npm_minimal_age_gate_minutes,
)
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def clear_version_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clear_resolution_caches()
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'xdg-cache'))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / '.config'))


def _make_response(
    text: str = '',
    json_data: object = None,
    ok: bool = True,  # noqa: FBT001, FBT002
    content: bytes = b'',
    status_code: int | None = None,
) -> MagicMock:
    """Create a mock niquests response."""
    response = MagicMock()
    response.ok = ok
    if status_code is not None:
        response.status_code = status_code
    else:
        response.status_code = 200 if ok else 404
    response.text = text
    response.json = MagicMock(return_value=json_data)
    response.content = content
    response.raise_for_status = MagicMock(return_value=response)
    return response


async def test_download_yarn_plugins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(text='  plugin content  '))
    await download_yarn_plugins(mock_session)
    plugin_file = tmp_path / '.yarn/plugins/plugin-prettier-after-all-installed.cjs'
    assert plugin_file.exists()
    assert plugin_file.read_text(encoding='utf-8') == 'plugin content\n'


async def test_download_yarn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(text='  yarn content  '))
    await download_yarn(mock_session, '4.0.0')
    target = tmp_path / '.yarn/releases/yarn-4.0.0.cjs'
    assert target.exists()
    assert target.read_text(encoding='utf-8') == 'yarn content\n'
    assert target.stat().st_mode & stat.S_IXUSR


async def test_download_yarn_removes_old_releases(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    releases_dir = tmp_path / '.yarn/releases'
    releases_dir.mkdir(parents=True)
    (releases_dir / 'yarn-3.0.0.cjs').write_text('old')
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(text='new yarn'))
    await download_yarn(mock_session, '4.0.0')
    assert not (releases_dir / 'yarn-3.0.0.cjs').exists()
    assert (releases_dir / 'yarn-4.0.0.cjs').exists()


async def test_get_github_release_latest_tag_from_release() -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=_make_response(ok=True, json_data={'tag_name': 'v1.2.3'}))
    result = await get_github_release_latest_tag(mock_session, 'owner', 'repo')
    assert result == 'v1.2.3'


async def test_get_github_release_latest_tag_from_tags_fallback() -> None:
    release_resp = _make_response(ok=False)
    tags_resp = _make_response(ok=True, json_data=[{'name': 'v2.0.0'}, {'name': 'v1.0.0'}])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[release_resp, tags_resp])
    result = await get_github_release_latest_tag(mock_session, 'owner', 'repo2')
    assert result == 'v2.0.0'


async def test_get_github_release_latest_tag_actions_mode() -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=_make_response(ok=True, json_data=[{
            'name': 'v4.1.2'
        }, {
            'name': 'v3.0.0'
        }]))
    result = await get_github_release_latest_tag(mock_session,
                                                 'owner',
                                                 'repo3',
                                                 skip_releases=True,
                                                 allow_suffixes=False)
    assert result == 'v4.1.2'


async def test_get_github_release_latest_tag_no_tags_raises() -> None:
    release_resp = _make_response(ok=False)
    tags_resp = _make_response(ok=True, json_data=[])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[release_resp, tags_resp])
    with pytest.raises(ValueError, match='Could not get latest tag'):
        await get_github_release_latest_tag(mock_session, 'owner', 'empty_repo')


async def test_get_github_release_latest_tag_skip_releases() -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=_make_response(ok=True, json_data=[{
            'name': 'v5.0.0'
        }]))
    result = await get_github_release_latest_tag(mock_session, 'owner', 'repo4', skip_releases=True)
    assert result == 'v5.0.0'
    assert mock_session.get.call_count == 1


async def test_get_github_release_latest_tag_actions_no_suffix() -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(ok=True,
                                                             json_data=[{
                                                                 'name': 'v4.0.0-beta'
                                                             }, {
                                                                 'name': 'v3.0.1'
                                                             }]))
    result = await get_github_release_latest_tag(mock_session,
                                                 'owner',
                                                 'repo5',
                                                 skip_releases=True,
                                                 allow_suffixes=False)
    assert result == 'v3.0.1'


async def test_get_github_release_latest_tag_both_fail() -> None:
    release_resp = _make_response(ok=False)
    tags_resp = _make_response(ok=False)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[release_resp, tags_resp])
    with pytest.raises(ValueError, match='Could not get latest tag'):
        await get_github_release_latest_tag(mock_session, 'owner', 'repo6')


async def test_get_github_release_latest_tag_no_suffix_skips_non_v_prefix() -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=_make_response(ok=True, json_data=[{
            'name': '4.1.2'
        }, {
            'name': 'v3.0.0'
        }]))
    result = await get_github_release_latest_tag(mock_session,
                                                 'owner',
                                                 'repo7',
                                                 skip_releases=True,
                                                 allow_suffixes=False)
    assert result == 'v3.0.0'


async def test_get_github_release_latest_tag_no_suffix_no_matching_tag() -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(ok=True,
                                                             json_data=[{
                                                                 'name': '4.1.2'
                                                             }, {
                                                                 'name': 'release-3.0.0'
                                                             }]))
    with pytest.raises(RuntimeError, match='coroutine raised StopIteration'):
        await get_github_release_latest_tag(mock_session,
                                            'owner',
                                            'repo8',
                                            skip_releases=True,
                                            allow_suffixes=False)


async def test_get_github_release_latest_tag_google_yapf_special_case() -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(ok=True,
                                                             json_data=[{
                                                                 'name': 'release-0.40'
                                                             }, {
                                                                 'name': 'v0.40.0'
                                                             }]))
    result = await get_github_release_latest_tag(mock_session,
                                                 'google',
                                                 'yapf',
                                                 skip_releases=True,
                                                 allow_suffixes=True)
    assert result == 'v0.40.0'


async def test_get_github_release_latest_tag_no_suffix_via_fallback() -> None:
    release_resp = _make_response(ok=False)
    tags_resp = _make_response(ok=True, json_data=[{'name': 'v2.0.0-rc'}, {'name': 'v1.5.0'}])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[release_resp, tags_resp])
    result = await get_github_release_latest_tag(mock_session,
                                                 'owner',
                                                 'repo9',
                                                 allow_suffixes=False)
    assert result == 'v1.5.0'


async def test_get_github_release_latest_tag_cache_hit() -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=_make_response(ok=True, json_data={'tag_name': 'v1.0.0'}))
    result1 = await get_github_release_latest_tag(mock_session, 'owner', 'cached_repo')
    result2 = await get_github_release_latest_tag(mock_session, 'owner', 'cached_repo')
    assert result1 == result2 == 'v1.0.0'
    assert mock_session.get.call_count == 1


async def test_get_github_release_latest_tag_persists_to_disk(tmp_path: Path) -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=_make_response(ok=True, json_data={'tag_name': 'v2.2.2'}))
    await get_github_release_latest_tag(mock_session, 'owner', 'persist_repo')
    cache_file = tmp_path / 'xdg-cache' / 'wiswa' / 'github_tag_cache.json'
    assert cache_file.is_file()
    on_disk = json.loads(cache_file.read_text(encoding='utf-8'))
    assert on_disk['gh_owner/persist_repo_False_True'] == 'v2.2.2'


async def test_get_github_release_latest_tag_disk_cache_on_403(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    cache_dir = tmp_path / 'xdg-cache' / 'wiswa'
    cache_dir.mkdir(parents=True)
    key = 'gh_owner/rate_limited_False_True'
    (cache_dir / 'github_tag_cache.json').write_text(json.dumps({key: 'v1.9.0'}, indent=2) + '\n',
                                                     encoding='utf-8')
    release_resp = _make_response(ok=False, json_data={}, status_code=403)
    tags_resp = _make_response(ok=False, json_data={}, status_code=403)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[release_resp, tags_resp])
    with caplog.at_level(logging.WARNING):
        result = await get_github_release_latest_tag(mock_session, 'owner', 'rate_limited')
    assert result == 'v1.9.0'
    assert 'disk-cached' in caplog.text


async def test_get_github_release_latest_tag_corrupt_disk_store_overwritten(tmp_path: Path) -> None:
    cache_dir = tmp_path / 'xdg-cache' / 'wiswa'
    cache_dir.mkdir(parents=True)
    (cache_dir / 'github_tag_cache.json').write_text('[1, 2]', encoding='utf-8')
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=_make_response(ok=True, json_data={'tag_name': 'v8.8.8'}))
    result = await get_github_release_latest_tag(mock_session, 'owner', 'fresh_repo')
    assert result == 'v8.8.8'
    data = json.loads((cache_dir / 'github_tag_cache.json').read_text(encoding='utf-8'))
    assert data == {'gh_owner/fresh_repo_False_True': 'v8.8.8'}


async def test_get_github_release_latest_tag_disk_write_oserror_logged(
        tmp_path: Path, mocker: MockerFixture, caplog: pytest.LogCaptureFixture) -> None:
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        return_value=_make_response(ok=True, json_data={'tag_name': 'v1.0.1'}))
    real_replace = Path.replace

    def boom_replace(self: Path, target: str | Path) -> Path:
        if self.name.endswith('.tmp'):
            msg = 'simulated replace failure'
            raise OSError(msg)
        return real_replace(self, target)

    mocker.patch.object(Path, 'replace', boom_replace)
    with caplog.at_level(logging.DEBUG):
        result = await get_github_release_latest_tag(mock_session, 'owner', 'write_fail')
    assert result == 'v1.0.1'
    assert 'persist GitHub tag cache' in caplog.text


async def test_get_github_release_latest_tag_403_missing_disk_entry_raises(tmp_path: Path) -> None:
    cache_dir = tmp_path / 'xdg-cache' / 'wiswa'
    cache_dir.mkdir(parents=True)
    (cache_dir / 'github_tag_cache.json').write_text('{}\n', encoding='utf-8')
    release_resp = _make_response(ok=False, json_data={}, status_code=403)
    tags_resp = _make_response(ok=False, json_data={}, status_code=403)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[release_resp, tags_resp])
    with pytest.raises(ValueError, match='Could not get latest tag'):
        await get_github_release_latest_tag(mock_session, 'owner', 'no_disk_entry')


async def test_get_github_release_latest_tag_disk_cache_on_403_skip_releases(
        tmp_path: Path) -> None:
    cache_dir = tmp_path / 'xdg-cache' / 'wiswa'
    cache_dir.mkdir(parents=True)
    key = 'gh_owner/wf_only_True_False'
    (cache_dir / 'github_tag_cache.json').write_text(json.dumps({key: 'v3.1.0'}) + '\n',
                                                     encoding='utf-8')
    mock_session = MagicMock()
    mock_session.get = AsyncMock(
        side_effect=[_make_response(ok=False, json_data=[], status_code=403)])
    result = await get_github_release_latest_tag(mock_session,
                                                 'owner',
                                                 'wf_only',
                                                 skip_releases=True,
                                                 allow_suffixes=False)
    assert result == 'v3.1.0'


async def test_get_github_release_latest_tag_npm_age_picks_older_published_release() -> None:
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%SZ')
    new_pub = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    releases = _make_response(ok=True,
                              json_data=[
                                  {
                                      'tag_name': 'v2.0.0',
                                      'draft': False,
                                      'prerelease': False,
                                      'published_at': new_pub,
                                  },
                                  {
                                      'tag_name': 'v1.0.0',
                                      'draft': False,
                                      'prerelease': False,
                                      'published_at': old_pub,
                                  },
                              ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[releases])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080)
    assert result == 'v1.0.0'


async def test_get_github_release_latest_tag_npm_age_list_blocked_falls_back_latest() -> None:
    blocked = _make_response(ok=False, status_code=403)
    latest = _make_response(ok=True, json_data={'tag_name': 'v2.0.0'})
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[blocked, latest])
    result = await get_github_release_latest_tag(mock_session,
                                                 'x',
                                                 'y',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=60)
    assert result == 'v2.0.0'


async def test_get_github_release_latest_tag_npm_age_list_429() -> None:
    blocked = _make_response(ok=False, status_code=429)
    latest = _make_response(ok=True, json_data={'tag_name': 'v2.1.0'})
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[blocked, latest])
    result = await get_github_release_latest_tag(mock_session,
                                                 'x',
                                                 'y',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=1)
    assert result == 'v2.1.0'


async def test_get_github_release_latest_tag_npm_age_no_match_logs_and_falls_back(
        caplog: pytest.LogCaptureFixture) -> None:
    new_pub = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    releases = _make_response(ok=True,
                              json_data=[{
                                  'tag_name': 'v5.0.0',
                                  'draft': False,
                                  'prerelease': False,
                                  'published_at': new_pub,
                              }])
    latest = _make_response(ok=True, json_data={'tag_name': 'v5.0.0'})
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[releases, latest])
    with caplog.at_level(logging.DEBUG):
        result = await get_github_release_latest_tag(mock_session,
                                                     'a',
                                                     'b',
                                                     apply_npm_min_release_age=True,
                                                     npm_age_gate_minutes=10080)
    assert result == 'v5.0.0'
    assert 'falling back to latest tag logic' in caplog.text


async def test_get_github_release_latest_tag_npm_age_skips_non_qualifying_releases() -> None:
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    new_pub = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    batch = [
        'not-a-dict',
        {
            'draft': True,
            'tag_name': 'v9.0.0',
            'published_at': old_pub,
        },
        {
            'prerelease': True,
            'tag_name': 'v8.0.0',
            'published_at': old_pub,
        },
        {
            'tag_name': '',
            'published_at': old_pub,
        },
        {
            'tag_name': 'v7.0.0',
            'published_at': 7,
        },
        {
            'tag_name': 'v6.0.0',
            'published_at': 'not-a-date',
        },
        {
            'tag_name': 'v5.0.0',
            'published_at': new_pub,
        },
        {
            'tag_name': 'vvvv',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
        {
            'tag_name': 'v2.0.0',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
    ]
    releases = _make_response(ok=True, json_data=batch)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[releases])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080,
                                                 allow_suffixes=False)
    assert result == 'v2.0.0'


async def test_get_github_release_latest_tag_npm_age_non_list_batch_falls_back() -> None:
    weird = _make_response(ok=True, json_data={'items': []})
    latest = _make_response(ok=True, json_data={'tag_name': 'v1.2.3'})
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[weird, latest])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=1)
    assert result == 'v1.2.3'


async def test_get_github_release_latest_tag_npm_age_http_not_ok_falls_back() -> None:
    nok = _make_response(ok=False, status_code=404)
    latest = _make_response(ok=True, json_data={'tag_name': 'v4.0.0'})
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[nok, latest])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=5)
    assert result == 'v4.0.0'


async def test_get_github_release_latest_tag_npm_age_empty_batch_falls_back() -> None:
    empty = _make_response(ok=True, json_data=[])
    latest = _make_response(ok=True, json_data={'tag_name': 'v0.0.1'})
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[empty, latest])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=9)
    assert result == 'v0.0.1'


async def test_get_github_release_latest_tag_npm_age_second_release_page() -> None:
    new_pub = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=60)).strftime('%Y-%m-%dT%H:%M:%SZ')
    page1 = [{
        'tag_name': f'v0.{i}.0',
        'draft': False,
        'prerelease': False,
        'published_at': new_pub,
    } for i in range(100)]
    page2 = [{
        'tag_name': 'v10.0.0',
        'draft': False,
        'prerelease': False,
        'published_at': old_pub,
    }]
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[
        _make_response(ok=True, json_data=page1),
        _make_response(ok=True, json_data=page2),
    ])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080)
    assert result == 'v10.0.0'


async def test_get_github_release_latest_tag_npm_age_omits_minutes_uses_yarnrc(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.yarnrc.yml').write_text('npmMinimalAgeGate: 10080\n', encoding='utf-8')
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%SZ')
    releases = _make_response(ok=True,
                              json_data=[{
                                  'tag_name': 'v1.0.0',
                                  'draft': False,
                                  'prerelease': False,
                                  'published_at': old_pub,
                              }])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[releases])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True)
    assert result == 'v1.0.0'


async def test_get_github_release_latest_tag_npm_age_google_yapf_old_release() -> None:
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%SZ')
    batch = [{
        'tag_name': 'v0.41.0',
        'draft': False,
        'prerelease': False,
        'published_at': old_pub,
    }]
    releases = _make_response(ok=True, json_data=batch)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[releases])
    result = await get_github_release_latest_tag(mock_session,
                                                 'google',
                                                 'yapf',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080,
                                                 allow_suffixes=True)
    assert result == 'v0.41.0'


async def test_get_github_release_latest_tag_npm_age_google_yapf_no_digit_suffix() -> None:
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%SZ')
    batch = [
        {
            'tag_name': 'v0.40.0-beta',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
        {
            'tag_name': 'v0.40.0',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
    ]
    releases = _make_response(ok=True, json_data=batch)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[releases])
    result = await get_github_release_latest_tag(mock_session,
                                                 'google',
                                                 'yapf',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080,
                                                 allow_suffixes=False)
    assert result == 'v0.40.0'


async def test_get_github_release_latest_tag_npm_age_prefers_highest_eligible_version() -> None:
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
    batch = [
        {
            'tag_name': 'v1.0.0',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
        {
            'tag_name': 'v2.0.0',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
    ]
    releases = _make_response(ok=True, json_data=batch)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[releases])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080,
                                                 allow_suffixes=False)
    assert result == 'v2.0.0'


async def test_get_github_release_latest_tag_npm_age_skips_invalid_and_prerelease_tags() -> None:
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
    batch = [
        {
            'tag_name': 'v!!!!',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
        {
            'tag_name': 'v3.0.0rc1',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
        {
            'tag_name': 'v3.0.0',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
    ]
    releases = _make_response(ok=True, json_data=batch)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[releases])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080,
                                                 allow_suffixes=False)
    assert result == 'v3.0.0'


async def test_get_github_release_latest_tag_npm_age_partial_release_page() -> None:
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
    page_short = [{
        'tag_name': 'v1.1.0',
        'draft': False,
        'prerelease': False,
        'published_at': old_pub,
    }]
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[_make_response(ok=True, json_data=page_short)])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080)
    assert result == 'v1.1.0'


async def test_get_github_release_latest_tag_npm_age_full_page_exhausts_without_short_read(
        mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.versions._GITHUB_RELEASES_PAGE_CAP', 1)
    new_pub = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    page1 = [{
        'tag_name': f'v50.{i}.0',
        'draft': False,
        'prerelease': False,
        'published_at': new_pub,
    } for i in range(100)]
    latest = _make_response(ok=True, json_data={'tag_name': 'v50.0.0'})
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[
        _make_response(ok=True, json_data=page1),
        latest,
    ])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080)
    assert result == 'v50.0.0'


async def test_get_github_release_latest_tag_npm_age_invalid_semver_suffixes_allowed() -> None:
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
    batch = [
        {
            'tag_name': 'v!!!!',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
        {
            'tag_name': 'v2.0.0',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
    ]
    releases = _make_response(ok=True, json_data=batch)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[releases])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080,
                                                 allow_suffixes=True)
    assert result == 'v2.0.0'


async def test_get_github_release_latest_tag_npm_age_google_yapf_rejects_non_v_tag() -> None:
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
    batch = [
        {
            'tag_name': 'release-0.40',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
        {
            'tag_name': 'v0.40.0',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
    ]
    releases = _make_response(ok=True, json_data=batch)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[releases])
    result = await get_github_release_latest_tag(mock_session,
                                                 'google',
                                                 'yapf',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080,
                                                 allow_suffixes=True)
    assert result == 'v0.40.0'


async def test_get_github_release_latest_tag_npm_age_skips_older_version_when_max_seen() -> None:
    old_pub = (datetime.now(tz=timezone.utc) - timedelta(days=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
    batch = [
        {
            'tag_name': 'v3.0.0',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
        {
            'tag_name': 'v2.0.0',
            'draft': False,
            'prerelease': False,
            'published_at': old_pub,
        },
    ]
    releases = _make_response(ok=True, json_data=batch)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[releases])
    result = await get_github_release_latest_tag(mock_session,
                                                 'o',
                                                 'r',
                                                 apply_npm_min_release_age=True,
                                                 npm_age_gate_minutes=10080,
                                                 allow_suffixes=False)
    assert result == 'v3.0.0'


async def test_get_github_release_disk_store_memo_avoids_second_file_read(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_dir = tmp_path / 'xdg-cache' / 'wiswa'
    cache_dir.mkdir(parents=True)
    store = {
        'gh_aa/bb_False_True': 'v1.0.0',
        'gh_cc/dd_False_True': 'v2.0.0',
    }
    (cache_dir / 'github_tag_cache.json').write_text(json.dumps(store) + '\n', encoding='utf-8')
    reads: list[Path] = []
    real_read = Path.read_text

    def counting(self: Path, *a: Any, **kw: Any) -> str:
        if self.name == 'github_tag_cache.json':
            reads.append(self)
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, 'read_text', counting)
    blocked = _make_response(ok=False, status_code=403)
    mock_session = MagicMock()
    mock_session.get = AsyncMock(side_effect=[blocked, blocked, blocked, blocked])
    one = await get_github_release_latest_tag(mock_session, 'aa', 'bb')
    assert one == 'v1.0.0'
    two = await get_github_release_latest_tag(mock_session, 'cc', 'dd')
    assert two == 'v2.0.0'
    assert len(reads) == 1


async def test_get_pypi_latest_package_version_uv_toml_global_parses_timestamp(
        tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2025-01-15T12:00:00Z"\n', encoding='utf-8')
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Jun 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'toml-parse-pkg')
    assert result == '1.0.0'


@pytest.mark.parametrize(
    ('toml_value', 'pkg', 'use_bare_int'),
    [
        ('PT4H', 'dur-pt4h', False),
        ('P10D', 'dur-p10d', False),
        ('P2W', 'dur-p2w', False),
        ('P1DT2H', 'dur-p1dt2h', False),
        ('9 hours', 'dur-9h', False),
        ('8 days', 'dur-8d', False),
        ('2 weeks', 'dur-2w', False),
        ('30', 'dur-intdays', True),
    ],
)
async def test_get_pypi_exclude_newer_duration_forms(
        tmp_path: Path,
        mocker: MockerFixture,
        toml_value: str,
        pkg: str,
        use_bare_int: bool,  # noqa: FBT001
) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    line = (f'exclude-newer = {toml_value}\n'
            if use_bare_int else f'exclude-newer = "{toml_value}"\n')
    (uv_dir / 'uv.toml').write_text(line, encoding='utf-8')
    fixed_now = datetime(2025, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
    mocker.patch('wiswa.utils.versions.datetime', wraps=datetime)
    mocker.patch('wiswa.utils.versions.datetime.now', return_value=fixed_now)
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Aug 2025 10:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, pkg)
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_uv_toml_duration_exclude_newer(
        tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "P7D"\n', encoding='utf-8')
    fixed_now = datetime(2025, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    mocker.patch('wiswa.utils.versions.datetime', wraps=datetime)
    mocker.patch('wiswa.utils.versions.datetime.now', return_value=fixed_now)
    xml = _make_pypi_xml([('1.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'duration-cutoff-pkg')
    assert result == '1.0.0'


async def test_get_pypi_per_package_uv_toml_skips_invalid_timestamp(tmp_path: Path,
                                                                    mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text(
        '[exclude-newer-package]\nkeep = "2025-02-01T00:00:00Z"\ndrop = "not-a-timestamp"\n',
        encoding='utf-8',
    )
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Mar 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'keep')
    assert result == '1.0.0'


async def test_get_pypi_uv_toml_empty_behaves_like_no_config(tmp_path: Path,
                                                             mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('', encoding='utf-8')
    xml = _make_pypi_xml([('1.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'empty-uv-pkg')
    assert result == '1.0.0'


async def test_get_pypi_uv_toml_read_os_error_falls_back_to_no_cutoff(
        tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('valid = true', encoding='utf-8')
    mocker.patch('pathlib.Path.read_text', side_effect=OSError('Permission denied'))
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'read-error-pkg')
    assert result == '2.0.0'


def test_resolve_npm_minimal_age_gate_minutes_prefers_merged_settings() -> None:
    assert resolve_npm_minimal_age_gate_minutes(settings={'yarnrc': {
        'npmMinimalAgeGate': 42,
    }}) == 42


def test_resolve_npm_minimal_age_gate_minutes_settings_over_snippet() -> None:
    assert resolve_npm_minimal_age_gate_minutes(settings={'yarnrc': {
        'npmMinimalAgeGate': 55,
    }},
                                                project_snippet='npmMinimalAgeGate: 99\n') == 55


def test_resolve_npm_minimal_age_gate_minutes_snippet_over_yarnrc_files(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 100\n', encoding='utf-8')
    snippet = 'npmMinimalAgeGate: 200\n'
    assert resolve_npm_minimal_age_gate_minutes(settings=None, project_snippet=snippet) == 200


def test_resolve_npm_minimal_age_gate_minutes_project_yarnrc_before_home(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.yarnrc.yml').write_text('npmMinimalAgeGate: 11\n', encoding='utf-8')
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 22\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 22


def test_resolve_npm_minimal_age_gate_minutes_npmrc_when_no_yarnrc(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.npmrc').write_text('min-release-age=2\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 2 * 24 * 60


def test_resolve_npm_minimal_age_gate_minutes_default_when_missing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    assert resolve_npm_minimal_age_gate_minutes() == 10080


def test_resolve_npm_minimal_age_gate_minutes_settings_yarnrc_list_type(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 88\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes(settings={'yarnrc': []}) == 88


def test_resolve_npm_minimal_age_gate_minutes_settings_gate_string() -> None:
    assert resolve_npm_minimal_age_gate_minutes(settings={'yarnrc': {
        'npmMinimalAgeGate': '321',
    }}) == 321


def test_resolve_npm_minimal_age_gate_minutes_settings_non_numeric_skips_to_yarnrc(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 15\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes(
        settings={'yarnrc': {
            'npmMinimalAgeGate': math.pi,
        }}) == 15


def test_resolve_npm_minimal_age_gate_minutes_snippet_without_key_reads_yarnrc(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 77\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes(project_snippet='foo: 1\n') == 77


def test_resolve_npm_minimal_age_gate_minutes_project_yarnrc_missing_gate_then_home(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('# no gate\nplugins: []\n', encoding='utf-8')
    (fake_home / '.yarnrc.yml').write_text('npmMinimalAgeGate: 9\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 9


def test_resolve_npm_minimal_age_gate_minutes_malformed_cwd_yarnrc_then_home(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: notint\n', encoding='utf-8')
    (fake_home / '.yarnrc.yml').write_text('npmMinimalAgeGate: 33\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 33


def test_resolve_npm_minimal_age_gate_minutes_cwd_yarnrc_oserror_then_home(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    cwd_rc = tmp_path / '.yarnrc.yml'
    cwd_rc.write_text('npmMinimalAgeGate: 1\n', encoding='utf-8')
    (fake_home / '.yarnrc.yml').write_text('npmMinimalAgeGate: 44\n', encoding='utf-8')
    real_read = Path.read_text

    def patched(self: Path, *a: Any, **kw: Any) -> str:
        if self.resolve() == cwd_rc.resolve():
            msg = 'simulated read failure'
            raise OSError(msg)
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, 'read_text', patched)
    assert resolve_npm_minimal_age_gate_minutes() == 44


def test_resolve_npm_minimal_age_gate_minutes_npmrc_min_release_age_snake_key(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.npmrc').write_text('# c\nmin_release_age=4\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 4 * 24 * 60


def test_resolve_npm_minimal_age_gate_minutes_npmrc_skips_line_without_equals(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.npmrc').write_text('foo\nmin-release-age=2\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 2 * 24 * 60


def test_resolve_npm_minimal_age_gate_minutes_npmrc_invalid_days_then_default(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.npmrc').write_text('min-release-age=notint\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 10080


def test_resolve_npm_minimal_age_gate_minutes_npmrc_oserror_then_yarnrc(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    npmrc = fake_home / '.npmrc'
    npmrc.write_text('min-release-age=1\n', encoding='utf-8')
    (tmp_path / '.yarnrc.yml').write_text('npmMinimalAgeGate: 12\n', encoding='utf-8')
    real_read = Path.read_text

    def patched(self: Path, *a: Any, **kw: Any) -> str:
        if self.resolve() == npmrc.resolve():
            msg = 'npmrc read failure'
            raise OSError(msg)
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, 'read_text', patched)
    assert resolve_npm_minimal_age_gate_minutes() == 12


def test_resolve_npm_minimal_age_gate_minutes_npmrc_without_min_release_reads_default(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    (fake_home / '.npmrc').write_text('registry=https://registry.npmjs.org/\n', encoding='utf-8')
    assert resolve_npm_minimal_age_gate_minutes() == 10080


def test_resolve_npm_minimal_age_gate_minutes_npmrc_read_oserror_only(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_home = tmp_path / 'home'
    fake_home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: fake_home)
    monkeypatch.chdir(tmp_path)
    npmrc = fake_home / '.npmrc'
    npmrc.write_text('min-release-age=1\n', encoding='utf-8')
    real_read = Path.read_text

    def patched(self: Path, *a: Any, **kw: Any) -> str:
        if self.resolve() == npmrc.resolve():
            msg = 'npmrc read failure'
            raise OSError(msg)
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, 'read_text', patched)
    assert resolve_npm_minimal_age_gate_minutes() == 10080


# get_npm_latest_package_version tests


async def test_get_npm_latest_package_version_picks_oldest_stable() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    new_date = (datetime.now(tz=timezone.utc) - timedelta(minutes=5)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '2.0.0'
            },
            'versions': {
                '1.0.0': {},
                '2.0.0': {},
            },
            'time': {
                'created': '2020-01-01T00:00:00Z',
                'modified': '2025-01-01T00:00:00Z',
                '1.0.0': old_date,
                '2.0.0': new_date,
            },
        }))
    result = await get_npm_latest_package_version(mock_session, 'test-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_all_too_new_falls_back_to_latest() -> None:
    new_date = (datetime.now(tz=timezone.utc) - timedelta(minutes=5)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '3.0.0'
            },
            'versions': {
                '3.0.0': {},
            },
            'time': {
                '3.0.0': new_date,
            },
        }))
    result = await get_npm_latest_package_version(mock_session, 'new-only-pkg')
    assert result == '3.0.0'


async def test_get_npm_latest_package_version_skips_prerelease() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '2.0.0-beta.1'
            },
            'versions': {
                '1.0.0': {},
                '2.0.0-beta.1': {},
            },
            'time': {
                '1.0.0': old_date,
                '2.0.0-beta.1': old_date,
            },
        }))
    result = await get_npm_latest_package_version(mock_session, 'pre-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_skips_invalid_versions() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '1.0.0'
            },
            'versions': {
                'not-a-version': {},
                '1.0.0': {},
            },
            'time': {
                'not-a-version': old_date,
                '1.0.0': old_date,
            },
        }))
    result = await get_npm_latest_package_version(mock_session, 'invalid-ver-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_skips_invalid_dates() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '2.0.0'
            },
            'versions': {
                '1.0.0': {},
                '2.0.0': {},
            },
            'time': {
                '1.0.0': old_date,
                '2.0.0': 'not-a-date',
            },
        }))
    result = await get_npm_latest_package_version(mock_session, 'bad-date-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_cache_hit() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '1.0.0'
            },
            'versions': {
                '1.0.0': {},
            },
            'time': {
                '1.0.0': old_date
            },
        }))
    result1 = await get_npm_latest_package_version(mock_session, 'cached-npm')
    result2 = await get_npm_latest_package_version(mock_session, 'cached-npm')
    assert result1 == result2 == '1.0.0'
    assert mock_session.get.call_count == 1


async def test_get_npm_latest_package_version_picks_highest_version() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '3.0.0'
            },
            'versions': {
                '1.0.0': {},
                '2.0.0': {},
                '3.0.0': {},
            },
            'time': {
                '1.0.0': old_date,
                '2.0.0': old_date,
                '3.0.0': old_date,
            },
        }))
    result = await get_npm_latest_package_version(mock_session, 'multi-ver-pkg')
    assert result == '3.0.0'


async def test_get_npm_latest_package_version_skips_unpublished_versions() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '2.0.0'
            },
            'versions': {
                '1.0.0': {},
            },
            'time': {
                '1.0.0': old_date,
                '2.0.0': old_date,
            },
        }))
    result = await get_npm_latest_package_version(mock_session, 'unpublished-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_all_unpublished_falls_back_to_latest() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '3.0.0'
            },
            'versions': {},
            'time': {
                '1.0.0': old_date,
                '2.0.0': old_date,
                '3.0.0': old_date,
            },
        }))
    result = await get_npm_latest_package_version(mock_session, 'all-unpublished-pkg')
    assert result == '3.0.0'


async def test_get_npm_latest_package_version_no_versions_key_falls_back_to_latest() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(json_data={
        'dist-tags': {
            'latest': '1.0.0'
        },
        'time': {
            '1.0.0': old_date,
        },
    }))
    result = await get_npm_latest_package_version(mock_session, 'no-versions-key-pkg')
    assert result == '1.0.0'


async def test_get_npm_latest_package_version_mixed_published_unpublished() -> None:
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(
        json_data={
            'dist-tags': {
                'latest': '4.0.0'
            },
            'versions': {
                '1.0.0': {},
                '3.0.0': {},
            },
            'time': {
                'created': '2020-01-01T00:00:00Z',
                'modified': '2025-01-01T00:00:00Z',
                '1.0.0': old_date,
                '2.0.0': old_date,
                '3.0.0': old_date,
                '4.0.0': old_date,
            },
        }))
    result = await get_npm_latest_package_version(mock_session, 'mixed-pub-pkg')
    assert result == '3.0.0'


# get_pypi_latest_package_version tests


def _make_pypi_xml(versions: list[tuple[str, str]]) -> bytes:
    items = ''
    for ver, pub_date in versions:
        items += f'<item><title>{ver}</title><pubDate>{pub_date}</pubDate></item>\n'
    return f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'.encode()


async def test_get_pypi_latest_package_version_no_cutoff(tmp_path: Path,
                                                         mocker: MockerFixture) -> None:
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'no-cutoff-pkg')
    assert result == '2.0.0'


async def test_get_pypi_latest_package_version_global_cutoff(tmp_path: Path,
                                                             mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2024-06-01T00:00:00Z"\n', encoding='utf-8')
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'global-cutoff-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_per_package_cutoff(tmp_path: Path,
                                                                  mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text(
        'exclude-newer = "2020-01-01T00:00:00Z"\n\n'
        '[exclude-newer-package]\nmy-pkg = "2024-06-01T00:00:00Z"\n',
        encoding='utf-8',
    )
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'my-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_all_filtered_fallback(tmp_path: Path,
                                                                     mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2020-01-01T00:00:00Z"\n', encoding='utf-8')
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'all-filtered-pkg')
    assert result == '2.0.0'


async def test_get_pypi_latest_package_version_no_items_raises(tmp_path: Path,
                                                               mocker: MockerFixture) -> None:
    xml = b'<?xml version="1.0"?><rss><channel></channel></rss>'
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    with pytest.raises(ValueError, match='No versions found'):
        await get_pypi_latest_package_version(mock_session, 'empty-pkg')


async def test_get_pypi_latest_package_version_skips_prerelease(tmp_path: Path,
                                                                mocker: MockerFixture) -> None:
    xml = _make_pypi_xml([
        ('2.0.0a1', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'prerelease-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_skips_yanked(tmp_path: Path,
                                                            mocker: MockerFixture) -> None:
    xml = _make_pypi_xml([
        ('8.3.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('8.2.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'sphinx')
    assert result == '8.2.0'


async def test_get_pypi_latest_package_version_cache_hit(tmp_path: Path,
                                                         mocker: MockerFixture) -> None:
    xml = _make_pypi_xml([('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result1 = await get_pypi_latest_package_version(mock_session, 'cached-pypi')
    result2 = await get_pypi_latest_package_version(mock_session, 'cached-pypi')
    assert result1 == result2 == '1.0.0'
    assert mock_session.get.call_count == 1


async def test_get_pypi_latest_package_version_only_prerelease_raises(
        tmp_path: Path, mocker: MockerFixture) -> None:
    xml = _make_pypi_xml([
        ('2.0.0a1', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0rc1', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    with pytest.raises(ValueError, match='No versions found'):
        await get_pypi_latest_package_version(mock_session, 'only-pre-pkg')
