"""Shared ``requests`` session."""
from __future__ import annotations

from datetime import timedelta

import platformdirs
import requests_cache

__all__ = ('cached_session',)


def cached_session() -> requests_cache.CachedSession:
    """
    Get a cached requests session.

    Returns
    -------
    requests_cache.CachedSession
        A filesystem-backed cached session.
    """
    return requests_cache.CachedSession(platformdirs.user_cache_path() / 'wiswa/http',
                                        backend='filesystem',
                                        expire_after=timedelta(minutes=10))
