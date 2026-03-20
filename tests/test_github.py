from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

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


def _mock_github_session(mocker: MockerFixture) -> MagicMock:
    mocker.patch('wiswa.utils.github.keyring.get_password', return_value='ghp_test')
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=[]))
    mocker.patch('wiswa.utils.github.cached_session', return_value=session)
    return session


def _put_urls(session: MagicMock) -> list[str]:
    return [c.args[0] for c in session.put.call_args_list]


def test_setup_github_project_enables_immutable_releases(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    setup_github_project(_make_settings())
    assert 'https://api.github.com/repos/testuser/testrepo/immutable-releases' in _put_urls(session)


def test_setup_github_project_skips_immutable_releases_when_disabled(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    settings = _make_settings(github={'immutable_releases': False, 'username': 'testuser'})
    setup_github_project(settings)
    assert 'https://api.github.com/repos/testuser/testrepo/immutable-releases' not in _put_urls(
        session)


def test_setup_github_project_skips_when_not_using_github(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    setup_github_project(_make_settings(using_github=False))
    session.patch.assert_not_called()


def test_setup_github_project_skips_when_no_token(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.github.keyring.get_password', return_value=None)
    session = MagicMock()
    mocker.patch('wiswa.utils.github.cached_session', return_value=session)
    setup_github_project(_make_settings())
    session.patch.assert_not_called()


def test_setup_github_project_enables_security_features(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    setup_github_project(_make_settings())
    urls = _put_urls(session)
    host = 'https://api.github.com/repos/testuser/testrepo'
    assert f'{host}/automated-security-fixes' in urls
    assert f'{host}/private-vulnerability-reporting' in urls
    assert f'{host}/vulnerability-alerts' in urls


def test_setup_github_project_sets_topics(mocker: MockerFixture) -> None:
    session = _mock_github_session(mocker)
    setup_github_project(_make_settings(keywords=['test', 'multi word']))
    session.put.assert_any_call('https://api.github.com/repos/testuser/testrepo/topics',
                                json={'names': ['test', 'multi-word']})
