"""Tests for version utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
import stat

from wiswa.utils.versions import (
    clear_resolution_caches,
    download_yarn,
    download_yarn_plugins,
    get_github_release_latest_tag,
    get_npm_latest_package_version,
    get_pypi_latest_package_version,
)
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def _clear_version_cache() -> None:
    clear_resolution_caches()


def _make_response(
    text: str = '',
    json_data: object = None,
    ok: bool = True,  # noqa: FBT001, FBT002
    content: bytes = b'',
) -> MagicMock:
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


async def test_get_pypi_latest_package_version_uv_toml_global_parses_timestamp(
        tmp_path: Path, mocker: MockerFixture) -> None:
    uv_dir = tmp_path / '.config' / 'uv'
    uv_dir.mkdir(parents=True)
    (uv_dir / 'uv.toml').write_text('exclude-newer = "2025-01-15T12:00:00Z"\n', encoding='utf-8')
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
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
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
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
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
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
        '[exclude-newer-package]\n'
        'keep = "2025-02-01T00:00:00Z"\n'
        'drop = "not-a-timestamp"\n',
        encoding='utf-8',
    )
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
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
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
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
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
    mocker.patch('pathlib.Path.read_text', side_effect=OSError('Permission denied'))
    xml = _make_pypi_xml([
        ('2.0.0', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result = await get_pypi_latest_package_version(mock_session, 'read-error-pkg')
    assert result == '2.0.0'


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
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
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
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
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
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
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
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
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
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
    xml = b'<?xml version="1.0"?><rss><channel></channel></rss>'
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    with pytest.raises(ValueError, match='No versions found'):
        await get_pypi_latest_package_version(mock_session, 'empty-pkg')


async def test_get_pypi_latest_package_version_skips_prerelease(tmp_path: Path,
                                                                mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
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
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
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
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
    xml = _make_pypi_xml([('1.0.0', 'Mon, 01 Jan 2024 00:00:00 GMT')])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    result1 = await get_pypi_latest_package_version(mock_session, 'cached-pypi')
    result2 = await get_pypi_latest_package_version(mock_session, 'cached-pypi')
    assert result1 == result2 == '1.0.0'
    assert mock_session.get.call_count == 1


async def test_get_pypi_latest_package_version_only_prerelease_raises(
        tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.versions.Path.home', return_value=tmp_path)
    xml = _make_pypi_xml([
        ('2.0.0a1', 'Mon, 01 Jan 2025 00:00:00 GMT'),
        ('1.0.0rc1', 'Mon, 01 Jan 2024 00:00:00 GMT'),
    ])
    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=_make_response(content=xml))
    with pytest.raises(ValueError, match='No versions found'):
        await get_pypi_latest_package_version(mock_session, 'only-pre-pkg')
