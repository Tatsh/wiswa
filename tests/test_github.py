"""Tests for GitHub integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

from wiswa.utils.github import setup_github_project

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from wiswa.typing import Settings


def _make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        'default_branch': 'master',
        'description': 'A test project',
        'homepage': 'https://example.com',
        'keywords': ['test', 'example project'],
        'github': {
            'immutable_releases': True,
            'username': 'testuser',
        },
        'repository_uri': 'https://github.com/testuser/testrepo',
        'using_github': True,
    }
    base |= overrides
    return cast('Settings', base)


def _make_async_cm(mock_resp: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_resp(status: int = 200, json_data: Any = None) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=json_data if json_data is not None else [])
    return resp


def _mock_github_session(mocker: MockerFixture) -> MagicMock:
    mocker.patch('wiswa.utils.github.anyio.to_thread.run_sync', side_effect=lambda fn: fn())
    mocker.patch('wiswa.utils.github.keyring.get_password', return_value='ghp_test')
    session = MagicMock()
    default_resp = _make_resp()
    session.headers = MagicMock()
    session.patch.return_value = _make_async_cm(default_resp)
    session.get.return_value = _make_async_cm(default_resp)
    session.put.return_value = _make_async_cm(default_resp)
    session.post.return_value = _make_async_cm(default_resp)
    return session


def _put_urls(session: MagicMock) -> list[str]:
    return [c.args[0] for c in session.put.call_args_list]


async def test_setup_github_project_enables_immutable_releases(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    await setup_github_project(session, _make_settings())
    assert 'https://api.github.com/repos/testuser/testrepo/immutable-releases' in _put_urls(session)


async def test_setup_github_project_skips_immutable_releases_when_disabled(
        mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    settings = _make_settings(github={'immutable_releases': False, 'username': 'testuser'})
    await setup_github_project(session, settings)
    assert 'https://api.github.com/repos/testuser/testrepo/immutable-releases' not in _put_urls(
        session)


async def test_setup_github_project_skips_when_not_using_github(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    await setup_github_project(session, _make_settings(using_github=False))
    session.patch.assert_not_called()


async def test_setup_github_project_skips_when_no_token(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.github.anyio.to_thread.run_sync', side_effect=lambda fn: fn())
    mocker.patch('wiswa.utils.github.keyring.get_password', return_value=None)
    session = MagicMock()
    await setup_github_project(session, _make_settings())
    session.patch.assert_not_called()


async def test_setup_github_project_enables_security_features(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    await setup_github_project(session, _make_settings())
    urls = _put_urls(session)
    host = 'https://api.github.com/repos/testuser/testrepo'
    assert f'{host}/automated-security-fixes' in urls
    assert f'{host}/private-vulnerability-reporting' in urls
    assert f'{host}/vulnerability-alerts' in urls


async def test_setup_github_project_sets_topics(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    await setup_github_project(session, _make_settings(keywords=['test', 'multi word']))
    session.put.assert_any_call(
        'https://api.github.com/repos/testuser/testrepo/topics',
        json={'names': ['test', 'multi-word']},
    )


async def test_setup_github_project_creates_protect_version_tags_ruleset(
        mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    await setup_github_project(session, _make_settings())
    post_calls = list(session.post.call_args_list)
    ruleset_names = [
        c.kwargs.get('json', {}).get('name', '') for c in post_calls if 'rulesets' in c.args[0]
    ]
    assert 'Protect version tags' in ruleset_names
    assert 'Protect default branch' in ruleset_names
    assert 'Copilot review for default branch' in ruleset_names


async def test_setup_github_project_updates_existing_rulesets(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    rulesets_resp = _make_resp(200, [
        {
            'name': 'Protect version tags',
            'id': 1
        },
        {
            'name': 'Protect default branch',
            'id': 2
        },
        {
            'name': 'Copilot review for default branch',
            'id': 3
        },
    ])
    session.get.return_value = _make_async_cm(rulesets_resp)
    await setup_github_project(session, _make_settings())
    post_calls = [
        c for c in session.post.call_args_list if 'rulesets' in str(c.args[0] if c.args else '')
    ]
    assert len(post_calls) == 0
    put_calls = [
        c for c in session.put.call_args_list if 'rulesets/' in str(c.args[0] if c.args else '')
    ]
    assert len(put_calls) == 3


async def test_setup_github_project_creates_pages_when_not_existing(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    default_resp = _make_resp(200)
    pages_resp = _make_resp(404)

    def side_effect(url: str, **kwargs: object) -> MagicMock:
        if 'pages' in url:
            return _make_async_cm(pages_resp)
        return _make_async_cm(default_resp)

    session.get.side_effect = side_effect
    await setup_github_project(session, _make_settings())
    pages_post = [c for c in session.post.call_args_list if 'pages' in str(c.args[0])]
    assert len(pages_post) == 1


async def test_setup_github_project_skips_pages_when_existing(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    default_resp = _make_resp(200)
    pages_resp = _make_resp(200)

    def side_effect(url: str, **kwargs: object) -> MagicMock:
        if 'pages' in url:
            return _make_async_cm(pages_resp)
        return _make_async_cm(default_resp)

    session.get.side_effect = side_effect
    await setup_github_project(session, _make_settings())
    pages_post = [c for c in session.post.call_args_list if 'pages' in str(c.args[0])]
    assert len(pages_post) == 0


async def test_setup_github_project_mixed_existing_and_new_rulesets(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    rulesets_resp = _make_resp(200, [{'name': 'Protect version tags', 'id': 10}])
    session.get.return_value = _make_async_cm(rulesets_resp)
    await setup_github_project(session, _make_settings())
    put_ruleset_calls = [
        c for c in session.put.call_args_list if 'rulesets/' in str(c.args[0] if c.args else '')
    ]
    assert len(put_ruleset_calls) == 1
    assert put_ruleset_calls[0].args[0].endswith('/rulesets/10')
    post_ruleset_calls = [
        c for c in session.post.call_args_list if 'rulesets' in str(c.args[0] if c.args else '')
    ]
    post_names = [c.kwargs.get('json', {}).get('name', '') for c in post_ruleset_calls]
    assert 'Protect default branch' in post_names
    assert 'Copilot review for default branch' in post_names


async def test_setup_github_project_rulesets_get_skips_cache(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    await setup_github_project(session, _make_settings())
    rulesets_get = [c for c in session.get.call_args_list if 'rulesets' in str(c.args[0])]
    assert len(rulesets_get) == 1
    assert rulesets_get[0].kwargs.get('expire_after') == 0


async def test_setup_github_project_handles_http_error(mocker: MockerFixture) -> None:
    import aiohttp

    session = _mock_github_session(mocker)
    error_resp = _make_resp(200)
    error_resp.raise_for_status.side_effect = aiohttp.ClientResponseError(request_info=MagicMock(),
                                                                          history=(),
                                                                          status=400,
                                                                          message='Bad Request')
    session.patch.return_value = _make_async_cm(error_resp)
    mock_log = mocker.patch('wiswa.utils.github.log')
    await setup_github_project(session, _make_settings())
    mock_log.warning.assert_called_once()
