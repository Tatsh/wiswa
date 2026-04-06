"""Shared ``niquests`` cached session."""
from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from time import time
from typing import TYPE_CHECKING, Any, cast
import contextlib
import json
import logging

import niquests
import platformdirs

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ('CachedAsyncSession', 'cached_session')

log = logging.getLogger(__name__)

_DEFAULT_EXPIRE = timedelta(minutes=10)


class CachedAsyncSession(niquests.AsyncSession):
    """An async niquests session with simple filesystem response caching."""
    def __init__(self,
                 cache_dir: Path,
                 expire_after: timedelta = _DEFAULT_EXPIRE,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._cache_dir = cache_dir
        self._expire_seconds = expire_after.total_seconds()
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def cache_directory(self) -> Path:
        """Filesystem directory used for this session's response cache."""
        return self._cache_dir

    @property
    def expire_after_total_seconds(self) -> float:
        """Cache TTL in seconds for GET and HEAD responses."""
        return self._expire_seconds

    def _cache_key(self, method: str, url: str) -> Path:
        key = sha256(f'{method} {url}'.encode()).hexdigest()
        return self._cache_dir / key

    async def request(  # type: ignore[override]
            self,
            method: str,
            url: str,
            *,
            expire_after: float | None = None,
            **kwargs: Any) -> niquests.Response:
        """
        Send a request, returning a cached response when available.

        Parameters
        ----------
        method : str
            The HTTP method.
        url : str
            The URL.
        expire_after : float | None
            Override cache expiry for this request. Set to ``0`` to bypass the cache.
        **kwargs : Any
            Additional keyword arguments passed to the parent.

        Returns
        -------
        niquests.Response
            The HTTP response.
        """
        bypass = expire_after == 0
        ttl = self._expire_seconds if expire_after is None else expire_after
        if method.upper() in {'GET', 'HEAD'} and not bypass:
            cache_path = self._cache_key(method, url)
            if cache_path.exists():
                try:
                    data = json.loads(cache_path.read_text(encoding='utf-8'))
                    if time() - data['ts'] < ttl:
                        log.debug('Cache hit: %s %s', method, url)
                        resp = niquests.Response()
                        resp.status_code = data['status_code']
                        resp._content = data['content'].encode('utf-8')  # noqa: SLF001
                        resp.headers.update(data['headers'])
                        resp.url = data['url']
                        resp.encoding = data.get('encoding', 'utf-8')
                        return resp
                except (json.JSONDecodeError, KeyError, OSError):
                    pass
        resp = cast('niquests.Response', await super().request(method, url, **kwargs))
        if method.upper() in {'GET', 'HEAD'} and resp.ok and not bypass:
            log.debug('Caching response: %s %s', method, url)
            cache_path = self._cache_key(method, url)
            with contextlib.suppress(OSError):  # pragma: no cover
                cache_path.write_text(json.dumps({
                    'ts': time(),
                    'status_code': resp.status_code,
                    'content': resp.text or '',
                    'headers': dict(resp.headers),
                    'url': str(resp.url),
                    'encoding': resp.encoding,
                }),
                                      encoding='utf-8')
        return resp


def cached_session(*,
                   no_cache: bool = False,
                   expire_after: timedelta = _DEFAULT_EXPIRE) -> niquests.AsyncSession:
    """
    Get an async niquests session, optionally with filesystem caching.

    Parameters
    ----------
    no_cache : bool
        If ``True``, return a plain session without caching.
    expire_after : timedelta
        Cache expiry duration (ignored when *no_cache* is ``True``).

    Returns
    -------
    niquests.AsyncSession
        An async session (use as async context manager).
    """
    if no_cache:
        return niquests.AsyncSession()
    return CachedAsyncSession(
        cache_dir=platformdirs.user_cache_path('wiswa', appauthor=False) / 'http',
        expire_after=expire_after)
