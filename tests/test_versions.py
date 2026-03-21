"""Tests for version utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock
import stat

from wiswa.utils.versions import download_yarn, download_yarn_plugins
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_download_yarn_plugins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                               mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    mock_response = MagicMock()
    mock_response.text = '  plugin content  '
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mocker.patch('wiswa.utils.versions.cached_session', return_value=mock_session)
    download_yarn_plugins()
    plugin_file = tmp_path / '.yarn/plugins/plugin-prettier-after-all-installed.cjs'
    assert plugin_file.exists()
    assert plugin_file.read_text(encoding='utf-8') == 'plugin content\n'


def test_download_yarn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                       mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    mock_response = MagicMock()
    mock_response.text = '  yarn content  '
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mocker.patch('wiswa.utils.versions.cached_session', return_value=mock_session)
    download_yarn('4.0.0')
    target = tmp_path / '.yarn/releases/yarn-4.0.0.cjs'
    assert target.exists()
    assert target.read_text(encoding='utf-8') == 'yarn content\n'
    assert target.stat().st_mode & stat.S_IXUSR


def test_download_yarn_removes_old_releases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                            mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    releases_dir = tmp_path / '.yarn/releases'
    releases_dir.mkdir(parents=True)
    (releases_dir / 'yarn-3.0.0.cjs').write_text('old')
    mock_response = MagicMock()
    mock_response.text = 'new yarn'
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mocker.patch('wiswa.utils.versions.cached_session', return_value=mock_session)
    download_yarn('4.0.0')
    assert not (releases_dir / 'yarn-3.0.0.cjs').exists()
    assert (releases_dir / 'yarn-4.0.0.cjs').exists()


def test_get_github_release_latest_tag_from_release(mocker: MockerFixture) -> None:
    from wiswa.utils.versions import get_github_release_latest_tag

    get_github_release_latest_tag.cache_clear()
    mock_session = MagicMock()
    release_response = MagicMock(ok=True)
    release_response.json.return_value = {'tag_name': 'v1.2.3'}
    mock_session.get.return_value = release_response
    mocker.patch('wiswa.utils.versions.cached_session', return_value=mock_session)
    result = get_github_release_latest_tag('owner', 'repo')
    assert result == 'v1.2.3'


def test_get_github_release_latest_tag_from_tags_fallback(mocker: MockerFixture) -> None:
    from wiswa.utils.versions import get_github_release_latest_tag

    get_github_release_latest_tag.cache_clear()
    mock_session = MagicMock()
    release_response = MagicMock(ok=False)
    tags_response = MagicMock(ok=True)
    tags_response.json.return_value = [{'name': 'v2.0.0'}, {'name': 'v1.0.0'}]
    mock_session.get.side_effect = [release_response, tags_response]
    mocker.patch('wiswa.utils.versions.cached_session', return_value=mock_session)
    result = get_github_release_latest_tag('owner', 'repo2')
    assert result == 'v2.0.0'


def test_get_github_release_latest_tag_actions_mode(mocker: MockerFixture) -> None:
    from wiswa.utils.versions import get_github_release_latest_tag

    get_github_release_latest_tag.cache_clear()
    mock_session = MagicMock()
    tags_response = MagicMock(ok=True)
    tags_response.json.return_value = [{'name': 'v4.1.2'}, {'name': 'v3.0.0'}]
    mock_session.get.return_value = tags_response
    mocker.patch('wiswa.utils.versions.cached_session', return_value=mock_session)
    result = get_github_release_latest_tag('owner',
                                           'repo3',
                                           actions=True,
                                           skip_releases=True,
                                           allow_suffixes=False)
    assert result == 'v4'


def test_get_github_release_latest_tag_no_tags_raises(mocker: MockerFixture) -> None:
    from wiswa.utils.versions import get_github_release_latest_tag

    get_github_release_latest_tag.cache_clear()
    mock_session = MagicMock()
    release_response = MagicMock(ok=False)
    tags_response = MagicMock(ok=True)
    tags_response.json.return_value = []
    mock_session.get.side_effect = [release_response, tags_response]
    mocker.patch('wiswa.utils.versions.cached_session', return_value=mock_session)
    with pytest.raises(ValueError, match='Could not get latest tag'):
        get_github_release_latest_tag('owner', 'empty_repo')


def test_get_github_release_latest_tag_skip_releases(mocker: MockerFixture) -> None:
    from wiswa.utils.versions import get_github_release_latest_tag

    get_github_release_latest_tag.cache_clear()
    mock_session = MagicMock()
    tags_response = MagicMock(ok=True)
    tags_response.json.return_value = [{'name': 'v5.0.0'}]
    mock_session.get.return_value = tags_response
    mocker.patch('wiswa.utils.versions.cached_session', return_value=mock_session)
    result = get_github_release_latest_tag('owner', 'repo4', skip_releases=True)
    assert result == 'v5.0.0'
    assert mock_session.get.call_count == 1


def test_get_github_release_latest_tag_actions_no_suffix(mocker: MockerFixture) -> None:
    from wiswa.utils.versions import get_github_release_latest_tag

    get_github_release_latest_tag.cache_clear()
    mock_session = MagicMock()
    tags_response = MagicMock(ok=True)
    tags_response.json.return_value = [{'name': 'v4.0.0-beta'}, {'name': 'v3.0.1'}]
    mock_session.get.return_value = tags_response
    mocker.patch('wiswa.utils.versions.cached_session', return_value=mock_session)
    result = get_github_release_latest_tag('owner',
                                           'repo5',
                                           actions=True,
                                           skip_releases=True,
                                           allow_suffixes=False)
    assert result == 'v3'


def test_get_github_release_latest_tag_both_fail(mocker: MockerFixture) -> None:
    from wiswa.utils.versions import get_github_release_latest_tag

    get_github_release_latest_tag.cache_clear()
    mock_session = MagicMock()
    release_response = MagicMock(ok=False)
    tags_response = MagicMock(ok=False)
    mock_session.get.side_effect = [release_response, tags_response]
    mocker.patch('wiswa.utils.versions.cached_session', return_value=mock_session)
    with pytest.raises(ValueError, match='Could not get latest tag'):
        get_github_release_latest_tag('owner', 'repo6')
