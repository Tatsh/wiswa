"""Tests for version utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
import stat

from wiswa.utils.versions import download_yarn, download_yarn_plugins, get_github_release_latest_tag
import pytest
import wiswa.utils.versions

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _clear_version_cache() -> None:
    wiswa.utils.versions._cache.clear()  # noqa: SLF001


def _make_async_response(
        text: str = '',
        json_data: object = None,
        ok: bool = True,  # noqa: FBT001, FBT002
        content: bytes = b'') -> MagicMock:
    """Create a mock response usable as ``async with session.get(...) as resp:``."""
    resp = MagicMock()
    resp.ok = ok
    resp.text = AsyncMock(return_value=text)
    resp.json = AsyncMock(return_value=json_data)
    resp.read = AsyncMock(return_value=content)
    resp.raise_for_status = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


async def test_download_yarn_plugins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    mock_session = MagicMock()
    mock_session.get.return_value = _make_async_response(text='  plugin content  ')
    await download_yarn_plugins(mock_session)
    plugin_file = tmp_path / '.yarn/plugins/plugin-prettier-after-all-installed.cjs'
    assert plugin_file.exists()
    assert plugin_file.read_text(encoding='utf-8') == 'plugin content\n'


async def test_download_yarn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    mock_session = MagicMock()
    mock_session.get.return_value = _make_async_response(text='  yarn content  ')
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
    mock_session.get.return_value = _make_async_response(text='new yarn')
    await download_yarn(mock_session, '4.0.0')
    assert not (releases_dir / 'yarn-3.0.0.cjs').exists()
    assert (releases_dir / 'yarn-4.0.0.cjs').exists()


async def test_get_github_release_latest_tag_from_release() -> None:
    mock_session = MagicMock()
    mock_session.get.return_value = _make_async_response(ok=True, json_data={'tag_name': 'v1.2.3'})
    result = await get_github_release_latest_tag(mock_session, 'owner', 'repo')
    assert result == 'v1.2.3'


async def test_get_github_release_latest_tag_from_tags_fallback() -> None:
    release_ctx = _make_async_response(ok=False)
    tags_ctx = _make_async_response(ok=True, json_data=[{'name': 'v2.0.0'}, {'name': 'v1.0.0'}])
    mock_session = MagicMock()
    mock_session.get.side_effect = [release_ctx, tags_ctx]
    result = await get_github_release_latest_tag(mock_session, 'owner', 'repo2')
    assert result == 'v2.0.0'


async def test_get_github_release_latest_tag_actions_mode() -> None:
    mock_session = MagicMock()
    mock_session.get.return_value = _make_async_response(ok=True,
                                                         json_data=[{
                                                             'name': 'v4.1.2'
                                                         }, {
                                                             'name': 'v3.0.0'
                                                         }])
    result = await get_github_release_latest_tag(mock_session,
                                                 'owner',
                                                 'repo3',
                                                 actions=True,
                                                 skip_releases=True,
                                                 allow_suffixes=False)
    assert result == 'v4'


async def test_get_github_release_latest_tag_no_tags_raises() -> None:
    release_ctx = _make_async_response(ok=False)
    tags_ctx = _make_async_response(ok=True, json_data=[])
    mock_session = MagicMock()
    mock_session.get.side_effect = [release_ctx, tags_ctx]
    with pytest.raises(ValueError, match='Could not get latest tag'):
        await get_github_release_latest_tag(mock_session, 'owner', 'empty_repo')


async def test_get_github_release_latest_tag_skip_releases() -> None:
    mock_session = MagicMock()
    mock_session.get.return_value = _make_async_response(ok=True, json_data=[{'name': 'v5.0.0'}])
    result = await get_github_release_latest_tag(mock_session, 'owner', 'repo4', skip_releases=True)
    assert result == 'v5.0.0'
    assert mock_session.get.call_count == 1


async def test_get_github_release_latest_tag_actions_no_suffix() -> None:
    mock_session = MagicMock()
    mock_session.get.return_value = _make_async_response(ok=True,
                                                         json_data=[{
                                                             'name': 'v4.0.0-beta'
                                                         }, {
                                                             'name': 'v3.0.1'
                                                         }])
    result = await get_github_release_latest_tag(mock_session,
                                                 'owner',
                                                 'repo5',
                                                 actions=True,
                                                 skip_releases=True,
                                                 allow_suffixes=False)
    assert result == 'v3'


async def test_get_github_release_latest_tag_both_fail() -> None:
    release_ctx = _make_async_response(ok=False)
    tags_ctx = _make_async_response(ok=False)
    mock_session = MagicMock()
    mock_session.get.side_effect = [release_ctx, tags_ctx]
    with pytest.raises(ValueError, match='Could not get latest tag'):
        await get_github_release_latest_tag(mock_session, 'owner', 'repo6')


async def test_get_github_release_latest_tag_cache_hit() -> None:
    mock_session = MagicMock()
    mock_session.get.return_value = _make_async_response(ok=True, json_data={'tag_name': 'v1.0.0'})
    result1 = await get_github_release_latest_tag(mock_session, 'owner', 'cached_repo')
    result2 = await get_github_release_latest_tag(mock_session, 'owner', 'cached_repo')
    assert result1 == result2 == 'v1.0.0'
    assert mock_session.get.call_count == 1
