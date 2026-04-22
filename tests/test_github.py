"""Tests for GitHub integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

from wiswa.utils.github import get_github_pages_build_type, setup_github_project

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


def _make_resp(status: int = 200, json_data: Any = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.ok = 200 <= status < 400
    response.raise_for_status = MagicMock(return_value=response)
    response.json = MagicMock(return_value=json_data if json_data is not None else [])
    return response


def _mock_github_session(mocker: MockerFixture) -> MagicMock:
    mocker.patch('wiswa.utils.github.run_sync', side_effect=lambda fn: fn())
    mocker.patch('wiswa.utils.github.keyring.get_password', return_value='ghp_test')
    session = MagicMock()
    default_resp = _make_resp()
    session.headers = MagicMock()
    session.patch = AsyncMock(return_value=default_resp)
    session.get = AsyncMock(return_value=default_resp)
    session.put = AsyncMock(return_value=default_resp)
    session.post = AsyncMock(return_value=default_resp)
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
    mocker.patch('wiswa.utils.github.run_sync', side_effect=lambda fn: fn())
    mocker.patch('wiswa.utils.github.keyring.get_password', return_value=None)
    session = MagicMock()
    await setup_github_project(session, _make_settings())
    session.patch.assert_not_called()


async def test_setup_github_project_keyring_tries_host_scoped_before_legacy(
        mocker: MockerFixture) -> None:
    calls: list[tuple[str, str]] = []

    def _fake_get_password(service: str, username: str) -> str | None:
        calls.append((service, username))
        if service == 'wiswa-github:github.com':
            return 'ghp_host'
        return None

    mocker.patch('wiswa.utils.github.run_sync', side_effect=lambda fn: fn())
    mocker.patch('wiswa.utils.github.keyring.get_password', side_effect=_fake_get_password)
    session = MagicMock()
    default_resp = _make_resp()
    session.headers = MagicMock()
    session.patch = AsyncMock(return_value=default_resp)
    session.get = AsyncMock(return_value=default_resp)
    session.put = AsyncMock(return_value=default_resp)
    session.post = AsyncMock(return_value=default_resp)
    await setup_github_project(session, _make_settings())
    assert calls[0][0] == 'wiswa-github:github.com'
    assert len(calls) == 1


async def test_setup_github_project_keyring_falls_back_to_legacy(mocker: MockerFixture) -> None:
    calls: list[tuple[str, str]] = []

    def _fake_get_password(service: str, username: str) -> str | None:
        calls.append((service, username))
        if service == 'tmu-github-api':
            return 'ghp_legacy'
        return None

    mocker.patch('wiswa.utils.github.run_sync', side_effect=lambda fn: fn())
    mocker.patch('wiswa.utils.github.keyring.get_password', side_effect=_fake_get_password)
    session = MagicMock()
    default_resp = _make_resp()
    session.headers = MagicMock()
    session.patch = AsyncMock(return_value=default_resp)
    session.get = AsyncMock(return_value=default_resp)
    session.put = AsyncMock(return_value=default_resp)
    session.post = AsyncMock(return_value=default_resp)
    await setup_github_project(session, _make_settings())
    assert calls[0][0] == 'wiswa-github:github.com'
    assert calls[1][0] == 'tmu-github-api'


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
    session.put.assert_any_call('https://api.github.com/repos/testuser/testrepo/topics',
                                json={'names': ['test', 'multi-word']})


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
    rulesets_resp = _make_resp(200, [{
        'name': 'Protect version tags',
        'id': 1
    }, {
        'name': 'Protect default branch',
        'id': 2
    }, {
        'name': 'Copilot review for default branch',
        'id': 3
    }])
    session.get = AsyncMock(return_value=rulesets_resp)
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
            return pages_resp
        return default_resp

    session.get = AsyncMock(side_effect=side_effect)
    await setup_github_project(session, _make_settings())
    pages_post = [c for c in session.post.call_args_list if 'pages' in str(c.args[0])]
    assert len(pages_post) == 1


async def test_setup_github_project_skips_pages_when_existing(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    default_resp = _make_resp(200)
    pages_resp = _make_resp(200)

    def side_effect(url: str, **kwargs: object) -> MagicMock:
        if 'pages' in url:
            return pages_resp
        return default_resp

    session.get = AsyncMock(side_effect=side_effect)
    await setup_github_project(session, _make_settings())
    pages_post = [c for c in session.post.call_args_list if 'pages' in str(c.args[0])]
    assert len(pages_post) == 0


async def test_setup_github_project_mixed_existing_and_new_rulesets(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    rulesets_resp = _make_resp(200, [{'name': 'Protect version tags', 'id': 10}])
    session.get = AsyncMock(return_value=rulesets_resp)
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


async def test_setup_github_project_returns_none_on_no_keyring(mocker: MockerFixture) -> None:
    import keyring.errors

    mocker.patch('wiswa.utils.github.run_sync', side_effect=lambda fn: fn())
    mocker.patch('wiswa.utils.github.keyring.get_password',
                 side_effect=keyring.errors.NoKeyringError)
    session = MagicMock()
    await setup_github_project(session, _make_settings())
    session.patch.assert_not_called()


async def test_setup_github_project_skips_pages_when_private(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    await setup_github_project(session, _make_settings(private=True))
    pages_calls = [c for c in session.get.call_args_list if 'pages' in str(c.args[0])]
    assert len(pages_calls) == 0
    pages_post = [c for c in session.post.call_args_list if 'pages' in str(c.args[0])]
    assert len(pages_post) == 0


async def test_setup_github_project_handles_http_error(mocker: MockerFixture) -> None:
    import json

    import niquests

    session = _mock_github_session(mocker)
    error_resp = _make_resp(200)
    gh_response = MagicMock()
    gh_response.status_code = 400
    message = 'Problems parsing JSON'
    gh_response.text = json.dumps({'message': message})
    gh_response.json = MagicMock(return_value={'message': message})
    error_resp.raise_for_status.side_effect = niquests.HTTPError(response=gh_response)
    session.patch = AsyncMock(return_value=error_resp)
    mock_log = mocker.patch('wiswa.utils.github.log')
    await setup_github_project(session, _make_settings())
    mock_log.warning.assert_called_once()
    args = mock_log.warning.call_args[0]
    assert 'GitHub setup step failed' in args[0]
    assert args[1] == 'repository settings'
    assert args[2] == f'HTTP 400 — {message}'


async def test_setup_github_project_http_error_json_message_not_truncated(
        mocker: MockerFixture) -> None:
    import json

    import niquests

    session = _mock_github_session(mocker)
    error_resp = _make_resp(200)
    gh_response = MagicMock()
    gh_response.status_code = 422
    long_message = 'x' * 600
    gh_response.text = json.dumps({'message': long_message})
    gh_response.json = MagicMock(return_value={'message': long_message})
    error_resp.raise_for_status.side_effect = niquests.HTTPError(response=gh_response)
    session.patch = AsyncMock(return_value=error_resp)
    mock_log = mocker.patch('wiswa.utils.github.log')
    await setup_github_project(session, _make_settings())
    args = mock_log.warning.call_args[0]
    assert args[2] == f'HTTP 422 — {long_message}'


async def test_setup_github_project_http_error_no_response_uses_exception_text(
        mocker: MockerFixture) -> None:
    import niquests

    session = _mock_github_session(mocker)
    session.patch = AsyncMock(side_effect=niquests.HTTPError('connection reset'))
    mock_log = mocker.patch('wiswa.utils.github.log')
    await setup_github_project(session, _make_settings())
    args = mock_log.warning.call_args[0]
    assert args[2] == 'connection reset'


async def test_setup_github_project_http_error_empty_exception_string_uses_type_name(
        mocker: MockerFixture) -> None:
    import niquests

    session = _mock_github_session(mocker)
    session.patch = AsyncMock(side_effect=niquests.HTTPError('   '))
    mock_log = mocker.patch('wiswa.utils.github.log')
    await setup_github_project(session, _make_settings())
    args = mock_log.warning.call_args[0]
    assert args[2] == 'HTTPError'


async def test_setup_github_project_http_error_no_status_truncates_plain_body(
        mocker: MockerFixture) -> None:
    import niquests

    # Log body max in wiswa.utils.github (500 chars before "...")
    body_max = 500
    session = _mock_github_session(mocker)
    error_resp = _make_resp(200)
    gh_response = MagicMock()
    gh_response.status_code = None
    plain = 'x' * (body_max + 50)
    gh_response.text = plain
    error_resp.raise_for_status.side_effect = niquests.HTTPError(response=gh_response)
    session.patch = AsyncMock(return_value=error_resp)
    mock_log = mocker.patch('wiswa.utils.github.log')
    await setup_github_project(session, _make_settings())
    args = mock_log.warning.call_args[0]
    msg = args[2]
    assert msg.startswith('HTTPError — ')
    assert '...' in msg
    assert len(msg) < len(plain) + 30


async def test_setup_github_project_http_error_json_decode_falls_back_truncated(
        mocker: MockerFixture) -> None:
    import niquests

    body_max = 500
    session = _mock_github_session(mocker)
    error_resp = _make_resp(200)
    gh_response = MagicMock()
    gh_response.status_code = 400
    padding = 'y' * (body_max + 10)
    gh_response.text = '{"message": "x" ' + padding
    gh_response.json = MagicMock(side_effect=ValueError)
    error_resp.raise_for_status.side_effect = niquests.HTTPError(response=gh_response)
    session.patch = AsyncMock(return_value=error_resp)
    mock_log = mocker.patch('wiswa.utils.github.log')
    await setup_github_project(session, _make_settings())
    args = mock_log.warning.call_args[0]
    msg = args[2]
    assert msg.startswith('HTTP 400')
    assert '...' in msg
    assert len(msg.split('HTTP 400 — ', 1)[1]) <= body_max + 5


async def test_setup_github_project_http_error_non_string_message_in_json(
        mocker: MockerFixture) -> None:
    import json

    import niquests

    session = _mock_github_session(mocker)
    error_resp = _make_resp(200)
    gh_response = MagicMock()
    gh_response.status_code = 400
    gh_response.text = json.dumps({'message': 42})
    gh_response.json = MagicMock(return_value={'message': 42})
    error_resp.raise_for_status.side_effect = niquests.HTTPError(response=gh_response)
    session.patch = AsyncMock(return_value=error_resp)
    mock_log = mocker.patch('wiswa.utils.github.log')
    await setup_github_project(session, _make_settings())
    args = mock_log.warning.call_args[0]
    assert '42' in args[2]


async def test_setup_github_project_http_error_json_not_callable_uses_raw_body(
        mocker: MockerFixture) -> None:
    import json

    import niquests

    session = _mock_github_session(mocker)
    error_resp = _make_resp(200)
    gh_response = MagicMock()
    gh_response.status_code = 400
    payload = {'message': 'ignored'}
    gh_response.text = json.dumps(payload)
    gh_response.json = None
    error_resp.raise_for_status.side_effect = niquests.HTTPError(response=gh_response)
    session.patch = AsyncMock(return_value=error_resp)
    mock_log = mocker.patch('wiswa.utils.github.log')
    await setup_github_project(session, _make_settings())
    args = mock_log.warning.call_args[0]
    out = args[2]
    assert json.dumps(payload) in out or '"message"' in out


async def test_setup_github_project_http_error_whitespace_body_returns_status_only(
        mocker: MockerFixture) -> None:
    import niquests

    session = _mock_github_session(mocker)
    error_resp = _make_resp(200)
    gh_response = MagicMock()
    gh_response.status_code = 400
    gh_response.text = '   \n\t  '
    error_resp.raise_for_status.side_effect = niquests.HTTPError(response=gh_response)
    session.patch = AsyncMock(return_value=error_resp)
    mock_log = mocker.patch('wiswa.utils.github.log')
    await setup_github_project(session, _make_settings())
    args = mock_log.warning.call_args[0]
    assert args[2] == 'HTTP 400'


async def test_setup_github_project_http_error_text_not_str_returns_status_only(
        mocker: MockerFixture) -> None:
    import niquests

    session = _mock_github_session(mocker)
    error_resp = _make_resp(200)
    gh_response = MagicMock()
    gh_response.status_code = 400
    gh_response.text = None
    error_resp.raise_for_status.side_effect = niquests.HTTPError(response=gh_response)
    session.patch = AsyncMock(return_value=error_resp)
    mock_log = mocker.patch('wiswa.utils.github.log')
    await setup_github_project(session, _make_settings())
    args = mock_log.warning.call_args[0]
    assert args[2] == 'HTTP 400'


async def test_get_github_pages_build_type_legacy(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    session.get = AsyncMock(return_value=_make_resp(200, {'build_type': 'legacy'}))
    result = await get_github_pages_build_type(session, _make_settings())
    assert result == 'legacy'


async def test_get_github_pages_build_type_workflow(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    session.get = AsyncMock(return_value=_make_resp(200, {'build_type': 'workflow'}))
    result = await get_github_pages_build_type(session, _make_settings())
    assert result == 'workflow'


async def test_get_github_pages_build_type_no_token(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.github.run_sync', side_effect=lambda fn: fn())
    mocker.patch('wiswa.utils.github.keyring.get_password', return_value=None)
    session = MagicMock()
    result = await get_github_pages_build_type(session, _make_settings())
    assert result is None


async def test_get_github_pages_build_type_not_found(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    session.get = AsyncMock(return_value=_make_resp(404))
    result = await get_github_pages_build_type(session, _make_settings())
    assert result is None


async def test_get_github_pages_build_type_request_error(mocker: MockerFixture) -> None:
    import niquests

    session = _mock_github_session(mocker)
    session.get = AsyncMock(side_effect=niquests.RequestException)
    result = await get_github_pages_build_type(session, _make_settings())
    assert result is None
