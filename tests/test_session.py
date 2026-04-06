from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from time import time
from typing import TYPE_CHECKING
import json

from wiswa.session import CachedAsyncSession, cached_session
import niquests
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def _cached_entry_path(cache_dir: Path, method: str, url: str) -> Path:
    digest = sha256(f'{method} {url}'.encode()).hexdigest()
    return cache_dir / digest


def test_cached_session_returns_cached_async_session(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.session.platformdirs.user_cache_path')
    session = cached_session()
    assert isinstance(session, CachedAsyncSession)


def test_cached_session_expire_after_is_10_minutes(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.session.platformdirs.user_cache_path')
    session = cached_session()
    assert isinstance(session, CachedAsyncSession)
    assert session.expire_after_total_seconds == timedelta(minutes=10).total_seconds()


def test_cached_session_uses_user_cache_path(mocker: MockerFixture) -> None:
    mock_cache_path = mocker.patch('wiswa.session.platformdirs.user_cache_path')
    session = cached_session()
    assert isinstance(session, CachedAsyncSession)
    assert session.cache_directory == mock_cache_path.return_value / 'http'
    mock_cache_path.assert_called_once_with('wiswa', appauthor=False)


def test_cached_session_no_cache_returns_plain_session(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.session.platformdirs.user_cache_path')
    session = cached_session(no_cache=True)
    assert type(session) is niquests.AsyncSession


def test_cached_session_custom_expire_after(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.session.platformdirs.user_cache_path')
    session = cached_session(expire_after=timedelta(hours=1))
    assert isinstance(session, CachedAsyncSession)
    assert session.expire_after_total_seconds == pytest.approx(3600.0)


def test_cached_async_session_creates_cache_dir(tmp_path: Path) -> None:
    cache_dir = tmp_path / 'sub' / 'cache'
    session = CachedAsyncSession(cache_dir=cache_dir)
    assert cache_dir.is_dir()
    assert session.cache_directory == cache_dir


def test_cached_async_session_cache_key_deterministic(tmp_path: Path) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path)
    key1 = _cached_entry_path(session.cache_directory, 'GET', 'https://example.com')
    key2 = _cached_entry_path(session.cache_directory, 'GET', 'https://example.com')
    assert key1 == key2


def test_cached_async_session_cache_key_differs_by_method(tmp_path: Path) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path)
    get_key = _cached_entry_path(session.cache_directory, 'GET', 'https://example.com')
    head_key = _cached_entry_path(session.cache_directory, 'HEAD', 'https://example.com')
    assert get_key != head_key


def test_cached_async_session_cache_key_differs_by_url(tmp_path: Path) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path)
    key1 = _cached_entry_path(session.cache_directory, 'GET', 'https://a.com')
    key2 = _cached_entry_path(session.cache_directory, 'GET', 'https://b.com')
    assert key1 != key2


async def test_cached_async_session_cache_hit(tmp_path: Path, mocker: MockerFixture) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path)
    cache_path = _cached_entry_path(session.cache_directory, 'GET', 'https://example.com/data')
    cache_path.write_text(json.dumps({
        'ts': time(),
        'status_code': 200,
        'content': 'cached body',
        'headers': {
            'X-Custom': 'val'
        },
        'url': 'https://example.com/data',
        'encoding': 'utf-8',
    }),
                          encoding='utf-8')
    parent_request = mocker.patch.object(niquests.AsyncSession, 'request', return_value=None)
    response = await session.request('GET', 'https://example.com/data')
    parent_request.assert_not_called()
    assert response.status_code == 200
    assert response.text == 'cached body'
    assert response.headers['X-Custom'] == 'val'


async def test_cached_async_session_cache_expired(tmp_path: Path, mocker: MockerFixture) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path, expire_after=timedelta(seconds=0))
    cache_path = _cached_entry_path(session.cache_directory, 'GET', 'https://example.com/old')
    cache_path.write_text(json.dumps({
        'ts': time() - 100,
        'status_code': 200,
        'content': 'stale',
        'headers': {},
        'url': 'https://example.com/old',
        'encoding': 'utf-8',
    }),
                          encoding='utf-8')
    mock_resp = niquests.Response()
    mock_resp.status_code = 200
    mock_resp._content = b'fresh'  # noqa: SLF001
    mock_resp.headers.update({})
    mock_resp.url = 'https://example.com/old'
    mock_resp.encoding = 'utf-8'
    mocker.patch.object(niquests.AsyncSession, 'request', return_value=mock_resp)
    resp = await session.request('GET', 'https://example.com/old')
    assert resp.text == 'fresh'


async def test_cached_async_session_bypass_cache(tmp_path: Path, mocker: MockerFixture) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path)
    cache_path = _cached_entry_path(session.cache_directory, 'GET', 'https://example.com/bypass')
    cache_path.write_text(json.dumps({
        'ts': time(),
        'status_code': 200,
        'content': 'cached',
        'headers': {},
        'url': 'https://example.com/bypass',
        'encoding': 'utf-8',
    }),
                          encoding='utf-8')
    mock_resp = niquests.Response()
    mock_resp.status_code = 200
    mock_resp._content = b'fresh'  # noqa: SLF001
    mock_resp.url = 'https://example.com/bypass'
    mock_resp.encoding = 'utf-8'
    mocker.patch.object(niquests.AsyncSession, 'request', return_value=mock_resp)
    resp = await session.request('GET', 'https://example.com/bypass', expire_after=0)
    assert resp.text == 'fresh'


async def test_cached_async_session_post_not_cached(tmp_path: Path, mocker: MockerFixture) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path)
    mock_resp = niquests.Response()
    mock_resp.status_code = 201
    mock_resp._content = b'created'  # noqa: SLF001
    mock_resp.url = 'https://example.com/api'
    mock_resp.encoding = 'utf-8'
    parent_request = mocker.patch.object(niquests.AsyncSession, 'request', return_value=mock_resp)
    resp = await session.request('POST', 'https://example.com/api')
    parent_request.assert_called_once()
    assert resp.status_code == 201


async def test_cached_async_session_cache_miss_stores(tmp_path: Path,
                                                      mocker: MockerFixture) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path)
    mock_resp = niquests.Response()
    mock_resp.status_code = 200
    mock_resp._content = b'new data'  # noqa: SLF001
    mock_resp.headers.update({'Content-Type': 'text/plain'})
    mock_resp.url = 'https://example.com/new'
    mock_resp.encoding = 'utf-8'
    mocker.patch.object(niquests.AsyncSession, 'request', return_value=mock_resp)
    await session.request('GET', 'https://example.com/new')
    cache_path = _cached_entry_path(session.cache_directory, 'GET', 'https://example.com/new')
    assert cache_path.exists()
    data = json.loads(cache_path.read_text(encoding='utf-8'))
    assert data['status_code'] == 200
    assert data['content'] == 'new data'


async def test_cached_async_session_corrupted_cache(tmp_path: Path, mocker: MockerFixture) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path)
    cache_path = _cached_entry_path(session.cache_directory, 'GET', 'https://example.com/bad')
    cache_path.write_text('not json', encoding='utf-8')
    mock_resp = niquests.Response()
    mock_resp.status_code = 200
    mock_resp._content = b'real data'  # noqa: SLF001
    mock_resp.url = 'https://example.com/bad'
    mock_resp.encoding = 'utf-8'
    mocker.patch.object(niquests.AsyncSession, 'request', return_value=mock_resp)
    resp = await session.request('GET', 'https://example.com/bad')
    assert resp.text == 'real data'


async def test_cached_async_session_cache_missing_key(tmp_path: Path,
                                                      mocker: MockerFixture) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path)
    cache_path = _cached_entry_path(session.cache_directory, 'GET',
                                    'https://example.com/missing-key')
    cache_path.write_text(json.dumps({'ts': time()}), encoding='utf-8')
    mock_resp = niquests.Response()
    mock_resp.status_code = 200
    mock_resp._content = b'fallback'  # noqa: SLF001
    mock_resp.url = 'https://example.com/missing-key'
    mock_resp.encoding = 'utf-8'
    mocker.patch.object(niquests.AsyncSession, 'request', return_value=mock_resp)
    resp = await session.request('GET', 'https://example.com/missing-key')
    assert resp.text == 'fallback'


async def test_cached_async_session_failed_response_not_cached(tmp_path: Path,
                                                               mocker: MockerFixture) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path)
    mock_resp = niquests.Response()
    mock_resp.status_code = 404
    mock_resp._content = b'not found'  # noqa: SLF001
    mock_resp.url = 'https://example.com/missing'
    mock_resp.encoding = 'utf-8'
    mocker.patch.object(niquests.AsyncSession, 'request', return_value=mock_resp)
    await session.request('GET', 'https://example.com/missing')
    cache_path = _cached_entry_path(session.cache_directory, 'GET', 'https://example.com/missing')
    assert not cache_path.exists()


async def test_cached_async_session_head_request_cached(tmp_path: Path,
                                                        mocker: MockerFixture) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path)
    mock_resp = niquests.Response()
    mock_resp.status_code = 200
    mock_resp._content = b''  # noqa: SLF001
    mock_resp.headers.update({'Content-Length': '0'})
    mock_resp.url = 'https://example.com/head'
    mock_resp.encoding = 'utf-8'
    mocker.patch.object(niquests.AsyncSession, 'request', return_value=mock_resp)
    await session.request('HEAD', 'https://example.com/head')
    cache_path = _cached_entry_path(session.cache_directory, 'HEAD', 'https://example.com/head')
    assert cache_path.exists()


async def test_cached_async_session_custom_expire_after_per_request(tmp_path: Path,
                                                                    mocker: MockerFixture) -> None:
    session = CachedAsyncSession(cache_dir=tmp_path, expire_after=timedelta(hours=1))
    cache_path = _cached_entry_path(session.cache_directory, 'GET', 'https://example.com/ttl')
    cache_path.write_text(json.dumps({
        'ts': time() - 5,
        'status_code': 200,
        'content': 'old',
        'headers': {},
        'url': 'https://example.com/ttl',
        'encoding': 'utf-8',
    }),
                          encoding='utf-8')
    mock_resp = niquests.Response()
    mock_resp.status_code = 200
    mock_resp._content = b'new'  # noqa: SLF001
    mock_resp.url = 'https://example.com/ttl'
    mock_resp.encoding = 'utf-8'
    mocker.patch.object(niquests.AsyncSession, 'request', return_value=mock_resp)
    resp = await session.request('GET', 'https://example.com/ttl', expire_after=1)
    assert resp.text == 'new'
