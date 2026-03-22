from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import ANY

from wiswa.session import cached_session

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_cached_session_returns_cached_session(mocker: MockerFixture) -> None:
    mock_cache_path = mocker.patch('wiswa.session.platformdirs.user_cache_path')
    mock_backend_cls = mocker.patch('wiswa.session.FileBackend')
    mock_session_cls = mocker.patch('wiswa.session.CachedSession')
    cached_session()
    mock_backend_cls.assert_called_once_with(
        cache_name=str(mock_cache_path.return_value / 'wiswa/http'),
        expire_after=timedelta(minutes=10),
    )
    mock_session_cls.assert_called_once_with(cache=mock_backend_cls.return_value, trace_configs=ANY)


def test_cached_session_expire_after_is_10_minutes(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.session.platformdirs.user_cache_path')
    mock_backend_cls = mocker.patch('wiswa.session.FileBackend')
    mocker.patch('wiswa.session.CachedSession')
    cached_session()
    _, kwargs = mock_backend_cls.call_args
    assert kwargs['expire_after'] == timedelta(minutes=10)


def test_cached_session_uses_filebackend(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.session.platformdirs.user_cache_path')
    mock_backend_cls = mocker.patch('wiswa.session.FileBackend')
    mock_session_cls = mocker.patch('wiswa.session.CachedSession')
    cached_session()
    _, kwargs = mock_session_cls.call_args
    assert kwargs['cache'] == mock_backend_cls.return_value


def test_cached_session_uses_user_cache_path(mocker: MockerFixture) -> None:
    mock_cache_path = mocker.patch('wiswa.session.platformdirs.user_cache_path')
    mock_backend_cls = mocker.patch('wiswa.session.FileBackend')
    mocker.patch('wiswa.session.CachedSession')
    cached_session()
    _args, kwargs = mock_backend_cls.call_args
    assert kwargs['cache_name'] == str(mock_cache_path.return_value / 'wiswa/http')


def test_cached_session_includes_trace_config(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.session.platformdirs.user_cache_path')
    mocker.patch('wiswa.session.FileBackend')
    mock_session_cls = mocker.patch('wiswa.session.CachedSession')
    cached_session()
    _, kwargs = mock_session_cls.call_args
    assert 'trace_configs' in kwargs
    assert len(kwargs['trace_configs']) == 1
