"""Tests for version utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
import stat

from wiswa.utils.versions import (
    download_yarn,
    download_yarn_plugins,
    get_github_release_latest_tag,
    get_npm_latest_package_version,
    get_pypi_latest_package_version,
)
import pytest
import wiswa.utils.versions

_get_uv_config = wiswa.utils.versions._get_uv_config  # noqa: SLF001
_parse_duration = wiswa.utils.versions._parse_duration  # noqa: SLF001
_parse_exclude_newer = wiswa.utils.versions._parse_exclude_newer  # noqa: SLF001

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def _clear_version_cache() -> None:
    wiswa.utils.versions._cache.clear()  # noqa: SLF001
    _get_uv_config.cache_clear()


def _make_response(
        text: str = '',
        json_data: object = None,
        ok: bool = True,  # noqa: FBT001, FBT002
        content: bytes = b'') -> MagicMock:
    """Create a mock niquests response."""
    resp = MagicMock()
    resp.ok = ok
    resp.text = text
    resp.json = MagicMock(return_value=json_data)
    resp.content = content
    resp.raise_for_status = MagicMock(return_value=resp)
    return resp


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


# _parse_duration tests


@pytest.mark.parametrize(('value', 'expected'), [
    ('PT24H', timedelta(hours=24)),
    ('pt12h', timedelta(hours=12)),
    ('P7D', timedelta(days=7)),
    ('p3d', timedelta(days=3)),
    ('P2W', timedelta(weeks=2)),
    ('p1w', timedelta(weeks=1)),
    ('P1DT12H', timedelta(days=1, hours=12)),
    ('P3DT6H', timedelta(days=3, hours=6)),
    ('7 days', timedelta(days=7)),
    ('1 day', timedelta(days=1)),
    ('24 hours', timedelta(hours=24)),
    ('1 hour', timedelta(hours=1)),
    ('2 weeks', timedelta(weeks=2)),
    ('1 week', timedelta(weeks=1)),
    ('10', timedelta(days=10)),
    ('0', timedelta(days=0)),
])
def test_parse_duration_valid(value: str, expected: timedelta) -> None:
    assert _parse_duration(value) == expected


@pytest.mark.parametrize('value', ['', 'abc', 'P1M', 'P1Y', 'not-a-duration', '1.5'])
def test_parse_duration_invalid(value: str) -> None:
    assert _parse_duration(value) is None


def test_parse_duration_strips_whitespace() -> None:
    assert _parse_duration('  P7D  ') == timedelta(days=7)


# _parse_exclude_newer tests


def test_parse_exclude_newer_iso_timestamp() -> None:
    result = _parse_exclude_newer('2025-01-15T10:30:00+00:00')
    assert result == datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


def test_parse_exclude_newer_iso_timestamp_with_z() -> None:
    result = _parse_exclude_newer('2025-01-15T10:30:00Z')
    assert result == datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


def test_parse_exclude_newer_naive_timestamp() -> None:
    result = _parse_exclude_newer('2025-06-01T00:00:00')
    assert result is not None
    assert result.year == 2025
    assert result.month == 6
    assert result.day == 1
    assert result.tzinfo is None


def test_parse_exclude_newer_duration(mocker: MockerFixture) -> None:
    fixed_now = datetime(2025, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    mocker.patch('wiswa.utils.versions.datetime', wraps=datetime)
    mocker.patch('wiswa.utils.versions.datetime.now', return_value=fixed_now)
    result = _parse_exclude_newer('P7D')
    assert result == fixed_now - timedelta(days=7)


def test_parse_exclude_newer_invalid() -> None:
    assert _parse_exclude_newer('not-valid-at-all') is None


def test_parse_exclude_newer_strips_whitespace() -> None:
    result = _parse_exclude_newer('  2025-01-15T10:30:00+00:00  ')
    assert result == datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


# _get_uv_config tests


def test_get_uv_config_no_file(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
    result = _get_uv_config()
    assert result == (None, {})


def test_get_uv_config_with_global_exclude_newer(tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    uv_toml = uv_dir / 'uv.toml'
    uv_toml.write_text('exclude-newer = "2025-01-15T00:00:00Z"\n', encoding='utf-8')
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
    global_cutoff, per_package = _get_uv_config()
    assert global_cutoff == datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    assert per_package == {}


def test_get_uv_config_with_per_package(tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    uv_toml = uv_dir / 'uv.toml'
    uv_toml.write_text(
        '[exclude-newer-package]\n'
        'requests = "2025-02-01T00:00:00Z"\n'
        'flask = "2025-03-01T00:00:00Z"\n',
        encoding='utf-8')
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
    global_cutoff, per_package = _get_uv_config()
    assert global_cutoff is None
    assert per_package == {
        'flask': datetime(2025, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
        'requests': datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
    }


def test_get_uv_config_with_both(tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    uv_toml = uv_dir / 'uv.toml'
    uv_toml.write_text(
        'exclude-newer = "2025-01-01T00:00:00Z"\n\n'
        '[exclude-newer-package]\nrequests = "2025-06-01T00:00:00Z"\n',
        encoding='utf-8')
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
    global_cutoff, per_package = _get_uv_config()
    assert global_cutoff == datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert per_package == {'requests': datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)}


def test_get_uv_config_empty_file(tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('', encoding='utf-8')
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
    assert _get_uv_config() == (None, {})


def test_get_uv_config_os_error(tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    uv_toml = uv_dir / 'uv.toml'
    uv_toml.write_text('valid = true', encoding='utf-8')
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
    mocker.patch('pathlib.Path.read_text', side_effect=OSError('Permission denied'))
    assert _get_uv_config() == (None, {})


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
    mock_session.get = AsyncMock(return_value=_make_response(json_data={
        'dist-tags': {
            'latest': '3.0.0'
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
    mock_session.get = AsyncMock(return_value=_make_response(json_data={
        'dist-tags': {
            'latest': '1.0.0'
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
            'time': {
                '1.0.0': old_date,
                '2.0.0': old_date,
                '3.0.0': old_date,
            },
        }))
    result = await get_npm_latest_package_version(mock_session, 'multi-ver-pkg')
    assert result == '3.0.0'


# get_pypi_latest_package_version tests


def _make_pypi_xml(versions: list[tuple[str, str]]) -> bytes:
    items = ''
    for ver, pub_date in versions:
        items += f'<item><title>{ver}</title><pubDate>{pub_date}</pubDate></item>\n'
    return f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'.encode()


async def test_get_pypi_latest_package_version_no_cutoff(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.versions._get_uv_config', return_value=(None, {}))
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'no-cutoff-pkg')
    assert result == '2.0.0'


async def test_get_pypi_latest_package_version_global_cutoff(mocker: MockerFixture) -> None:
    cutoff = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    mocker.patch('wiswa.utils.versions._get_uv_config', return_value=(cutoff, {}))
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'global-cutoff-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_per_package_cutoff(mocker: MockerFixture) -> None:
    global_cutoff = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    per_package = {'my-pkg': datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)}
    mocker.patch('wiswa.utils.versions._get_uv_config', return_value=(global_cutoff, per_package))
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'my-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_all_filtered_fallback(mocker: MockerFixture) -> None:
    cutoff = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    mocker.patch('wiswa.utils.versions._get_uv_config', return_value=(cutoff, {}))
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'all-filtered-pkg')
    assert result == '2.0.0'


async def test_get_pypi_latest_package_version_no_items_raises(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.versions._get_uv_config', return_value=(None, {}))
    xml = b'<?xml version="1.0"?><rss><channel></channel></rss>'
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    with pytest.raises(ValueError, match='No versions found'):
        await get_pypi_latest_package_version(mock_session, 'empty-pkg')


async def test_get_pypi_latest_package_version_skips_prerelease(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.versions._get_uv_config', return_value=(None, {}))
    xml = _make_pypi_xml([
        ('2.0.0a1', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'prerelease-pkg')
    assert result == '1.0.0'


async def test_get_pypi_latest_package_version_skips_yanked(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.versions._get_uv_config', return_value=(None, {}))
    xml = _make_pypi_xml([
        ('8.3.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('8.2.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'sphinx')
    assert result == '8.2.0'


async def test_get_pypi_latest_package_version_cache_hit(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.versions._get_uv_config', return_value=(None, {}))
    xml = _make_pypi_xml([('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result1 = await get_pypi_latest_package_version(mock_session, 'cached-pypi')
    result2 = await get_pypi_latest_package_version(mock_session, 'cached-pypi')
    assert result1 == result2 == '1.0.0'
    assert mock_session.get.call_count == 1


async def test_get_pypi_latest_package_version_only_prerelease_raises(
        mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.versions._get_uv_config', return_value=(None, {}))
    xml = _make_pypi_xml([
        ('2.0.0a1', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0rc1', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    with pytest.raises(ValueError, match='No versions found'):
        await get_pypi_latest_package_version(mock_session, 'only-pre-pkg')
