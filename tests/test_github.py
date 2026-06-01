"""Tests for Wiswa's GitHub dispatch wrappers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

from wiswa.tool.utils.github import get_github_pages_build_type, setup_github_project

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from wiswa.tool.typing import Settings


def _make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        'default_branch': 'master',
        'description': 'A test project',
        'homepage': 'https://example.com',
        'keywords': ['test', 'example project'],
        'github': {
            'immutable_oidc_subject': True,
            'immutable_releases': True,
            'sha_pinning_required': True,
            'username': 'testuser'
        },
        'private': False,
        'repository_uri': 'https://github.com/testuser/testrepo',
        'using_github': True
    }
    base |= overrides
    return cast('Settings', base)


async def test_setup_github_project_skips_when_not_using_github(mocker: MockerFixture) -> None:
    configure = mocker.patch('wiswa.tool.utils.github.configure_project', new_callable=AsyncMock)
    await setup_github_project(MagicMock(), _make_settings(using_github=False))
    configure.assert_not_called()


async def test_setup_github_project_delegates_to_wiswa_vcs(mocker: MockerFixture) -> None:
    configure = mocker.patch('wiswa.tool.utils.github.configure_project', new_callable=AsyncMock)
    session = MagicMock()
    await setup_github_project(session, _make_settings())
    configure.assert_awaited_once()
    kwargs = configure.call_args.kwargs
    assert kwargs['repository_uri'] == 'https://github.com/testuser/testrepo'
    assert kwargs['description'] == 'A test project'
    assert kwargs['immutable_releases'] is True
    assert kwargs['sha_pinning_required'] is True
    assert kwargs['immutable_oidc_subject'] is True
    assert kwargs['private'] is False


async def test_setup_github_project_propagates_private_flag(mocker: MockerFixture) -> None:
    configure = mocker.patch('wiswa.tool.utils.github.configure_project', new_callable=AsyncMock)
    await setup_github_project(MagicMock(), _make_settings(private=True))
    assert configure.call_args.kwargs['private'] is True


async def test_get_github_pages_build_type_returns_none_when_no_token(
        mocker: MockerFixture) -> None:
    mocker.patch('wiswa.tool.utils.github.run_sync', side_effect=lambda fn: fn())
    mocker.patch('wiswa.tool.utils.github.get_github_token', return_value=None)
    result = await get_github_pages_build_type(MagicMock(), _make_settings())
    assert result is None


async def test_get_github_pages_build_type_delegates_to_wiswa_vcs(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.tool.utils.github.run_sync', side_effect=lambda fn: fn())
    mocker.patch('wiswa.tool.utils.github.get_github_token', return_value='ghp_test')
    fake_api = MagicMock()
    mocker.patch('wiswa.tool.utils.github.NiquestsGitHubAPI', return_value=fake_api)
    delegate = mocker.patch('wiswa.tool.utils.github.get_pages_build_type',
                            new_callable=AsyncMock,
                            return_value='workflow')
    result = await get_github_pages_build_type(MagicMock(), _make_settings())
    assert result == 'workflow'
    delegate.assert_awaited_once_with(fake_api, 'testuser/testrepo')
