"""Shared ``aiohttp`` cached session."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
import logging

from aiohttp import TraceConfig, TraceRequestEndParams
from aiohttp_client_cache import CachedSession  # type: ignore[attr-defined]
from aiohttp_client_cache.backends.filesystem import FileBackend
import platformdirs

if TYPE_CHECKING:
    from aiohttp import ClientSession

__all__ = ('cached_session',)

log = logging.getLogger(__name__)


async def _on_request_end(  # noqa: RUF029
        _session: ClientSession, _ctx: object, params: TraceRequestEndParams) -> None:
    log.debug('%s %s %d', params.method, params.url, params.response.status)


def cached_session() -> CachedSession:
    """
    Get a cached aiohttp session.

    Returns
    -------
    CachedSession
        A filesystem-backed cached aiohttp session (use as async context manager).
    """
    trace = TraceConfig()
    trace.on_request_end.append(_on_request_end)
    return CachedSession(  # type: ignore[no-any-return]
        cache=FileBackend(
            cache_name=str(platformdirs.user_cache_path() / 'wiswa/http'),
            expire_after=timedelta(minutes=10),
        ),
        trace_configs=[trace],
    )
