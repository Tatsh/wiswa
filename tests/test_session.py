from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from wiswa.session import cached_session

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_cached_session_returns_cached_session(mocker: MockerFixture) -> None:
    mock_cache_path = mocker.patch('wiswa.session.platformdirs.user_cache_path')
    mock_cls = mocker.patch('wiswa.session.requests_cache.CachedSession')
    cached_session()
    mock_cls.assert_called_once_with(mock_cache_path.return_value / 'wiswa/http',
                                     backend='filesystem',
                                     expire_after=timedelta(minutes=10))


def test_cached_session_expire_after_is_10_minutes(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.session.platformdirs.user_cache_path')
    mock_cls = mocker.patch('wiswa.session.requests_cache.CachedSession')
    cached_session()
    _, kwargs = mock_cls.call_args
    assert kwargs['expire_after'] == timedelta(minutes=10)


def test_cached_session_no_cache_control(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.session.platformdirs.user_cache_path')
    mock_cls = mocker.patch('wiswa.session.requests_cache.CachedSession')
    cached_session()
    _, kwargs = mock_cls.call_args
    assert 'cache_control' not in kwargs


def test_cached_session_uses_filesystem_backend(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.session.platformdirs.user_cache_path')
    mock_cls = mocker.patch('wiswa.session.requests_cache.CachedSession')
    cached_session()
    _, kwargs = mock_cls.call_args
    assert kwargs['backend'] == 'filesystem'


def test_cached_session_uses_user_cache_path(mocker: MockerFixture) -> None:
    mock_cache_path = mocker.patch('wiswa.session.platformdirs.user_cache_path')
    mock_cls = mocker.patch('wiswa.session.requests_cache.CachedSession')
    cached_session()
    args, _ = mock_cls.call_args
    assert args[0] == mock_cache_path.return_value / 'wiswa/http'
