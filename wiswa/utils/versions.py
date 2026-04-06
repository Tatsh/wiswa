"""Version fetching and Yarn download utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from functools import cache
from pathlib import Path
from shutil import rmtree
from typing import TYPE_CHECKING, cast
import json
import logging
import operator
import re

from bs4 import BeautifulSoup as Soup, Tag
from packaging.version import InvalidVersion, Version, parse as parse_version
from wiswa.constants import PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI
import anyio
import platformdirs
import tomlkit

if TYPE_CHECKING:
    import niquests

__all__ = ('clear_resolution_caches', 'download_yarn', 'download_yarn_plugins',
           'get_github_release_latest_tag', 'get_latest_yarn_version',
           'get_npm_latest_package_version', 'get_pypi_latest_package_version')

log = logging.getLogger(__name__)

_PYPI_YANKED_RELEASES = {
    'sphinx-8.3.0',
}

_cache: dict[str, str] = {}

# In-memory snapshot of ``github_tag_cache.json``; one-element box avoids ``global``.
_github_tag_disk_store_memo_box: list[dict[str, str] | None] = [None]

_GITHUB_TAG_DISK_FILENAME = 'github_tag_cache.json'

_NPM_AGE_GATE_DEFAULT_MINUTES = 10080
"""Default npm minimum age gate in minutes (7 days)."""


def _parse_duration(value: str) -> timedelta | None:
    """
    Parse a duration string.

    Supports ISO 8601 durations (``P7D``, ``P2W``, ``PT24H``), friendly
    durations (``7 days``, ``24 hours``, ``2 weeks``), and plain integers
    interpreted as days. Calendar units (months, years) are not supported.
    """
    value = value.strip()
    m = re.fullmatch(r'PT(\d+)H', value, re.IGNORECASE)
    if m:
        return timedelta(hours=int(m.group(1)))
    m = re.fullmatch(r'P(\d+)([DW])', value, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        return timedelta(days=n) if m.group(2).upper() == 'D' else timedelta(weeks=n)
    m = re.fullmatch(r'P(\d+)DT(\d+)H', value, re.IGNORECASE)
    if m:
        return timedelta(days=int(m.group(1)), hours=int(m.group(2)))
    m = re.fullmatch(r'(\d+)\s*(hours?|days?|weeks?)', value, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()[0]
        if unit == 'h':
            return timedelta(hours=n)
        if unit == 'd':
            return timedelta(days=n)
        return timedelta(weeks=n)
    try:
        return timedelta(days=int(value))
    except ValueError:
        return None


def _parse_exclude_newer(value: str) -> datetime | None:
    """
    Parse an ``exclude-newer`` value.

    Accepts an RFC 3339 timestamp or a duration (resolved relative to
    now).
    """
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            delta = _parse_duration(value)
            if delta is not None:
                return datetime.now(tz=timezone.utc) - delta
            return None


@cache
def _get_uv_config() -> tuple[datetime | None, dict[str, datetime]]:
    """
    Read ``exclude-newer`` and ``exclude-newer-package`` from uv's user ``uv.toml``.

    The path is ``platformdirs.user_config_path('uv', appauthor=False) / 'uv.toml'``.

    Returns
    -------
    tuple[datetime | None, dict[str, datetime]]
        A global cutoff and a per-package mapping of cutoff datetimes.
    """
    uv_toml = platformdirs.user_config_path('uv', appauthor=False) / 'uv.toml'
    if not uv_toml.exists():
        return None, {}
    try:
        data = tomlkit.loads(uv_toml.read_text(encoding='utf-8')).unwrap()
    except OSError:
        return None, {}
    global_cutoff: datetime | None = None
    raw = data.get('exclude-newer')
    if raw is not None:
        global_cutoff = _parse_exclude_newer(str(raw))
    per_package: dict[str, datetime] = {}
    pkg_map = data.get('exclude-newer-package')
    if isinstance(pkg_map, dict):
        for pkg, val in pkg_map.items():
            dt = _parse_exclude_newer(str(val))
            if dt is not None:
                per_package[str(pkg)] = dt
    return global_cutoff, per_package


def clear_resolution_caches() -> None:
    """
    Drop memoised HTTP version results, ``uv.toml`` cache, and in-memory GitHub tag disk snapshot.

    Does not remove the on-disk GitHub tag store under the user cache directory
    for ``wiswa`` (for example ``~/.cache/wiswa`` on Linux via ``platformdirs``);
    that file is only read when the API responds with 403 or 429.

    Intended for tests and for long-lived processes that need a fresh read of
    uv's ``exclude-newer`` settings from the user ``uv.toml`` path resolved via
    ``platformdirs``.
    """
    _cache.clear()
    _github_tag_disk_store_memo_box[0] = None
    _get_uv_config.cache_clear()


async def get_latest_yarn_version(session: niquests.AsyncSession) -> str:  # pragma: no cover
    """
    Get the latest Yarn version.

    Parameters
    ----------
    session : niquests.AsyncSession
        The HTTP session.

    Returns
    -------
    str
        The latest stable Yarn version string.
    """
    key = 'yarn_latest'
    if key in _cache:
        return _cache[key]
    resp = await session.get('https://repo.yarnpkg.com/tags', timeout=15)
    resp.raise_for_status()
    data = resp.json()
    result = cast('str', data['latest']['stable'])
    _cache[key] = result
    return result


async def get_npm_latest_package_version(session: niquests.AsyncSession,
                                         package: str) -> str:  # pragma: no cover
    """
    Get the latest version of an npm package.

    Filters out versions published within the last
    ``_NPM_AGE_GATE_DEFAULT_MINUTES`` minutes (7 days) to match Yarn's
    ``npmMinimalAgeGate`` default. Versions that appear in the registry
    ``time`` map but are absent from the published ``versions`` map are
    also excluded.

    Parameters
    ----------
    session : niquests.AsyncSession
        The HTTP session.
    package : str
        The npm package name.

    Returns
    -------
    str
        The latest version string that passes the age gate.
    """
    key = f'npm_{package}'
    if key in _cache:
        return _cache[key]
    resp = await session.get(f'https://registry.npmjs.org/{package}', timeout=15)
    resp.raise_for_status()
    data = resp.json()
    time_map: dict[str, str] = data.get('time', {})
    published_versions: set[str] = set(data.get('versions', {}))
    latest_tag = cast('str', data.get('dist-tags', {}).get('latest', ''))
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=_NPM_AGE_GATE_DEFAULT_MINUTES)
    candidates: list[tuple[Version, datetime]] = []
    for ver_str, pub_date_str in time_map.items():
        if ver_str in {'created', 'modified'} or ver_str not in published_versions:
            continue
        try:
            ver = parse_version(ver_str)
        except InvalidVersion:
            continue
        if ver.is_prerelease or ver.is_devrelease:
            continue
        try:
            pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
        except ValueError:
            continue
        if pub_date <= cutoff:
            candidates.append((ver, pub_date))
    if candidates:
        result = str(max(candidates, key=operator.itemgetter(0))[0])
    else:
        result = latest_tag
        log.debug('No npm version of %s passes the age gate of %d minutes; using latest: %s',
                  package, _NPM_AGE_GATE_DEFAULT_MINUTES, result)
    _cache[key] = result
    return result


async def get_pypi_latest_package_version(session: niquests.AsyncSession,
                                          package: str) -> str:  # pragma: no cover
    """
    Get the latest version of a PyPI package.

    Respects ``exclude-newer-package`` (per-package) and ``exclude-newer`` (global) from uv's
    user ``uv.toml`` (via ``platformdirs``) to filter out versions published after the cutoff.

    Parameters
    ----------
    session : niquests.AsyncSession
        The HTTP session.
    package : str
        The PyPI package name.

    Returns
    -------
    str
        The latest non-prerelease, non-dev version string.

    Raises
    ------
    ValueError
        If no versions are found.
    """
    key = f'pypi_{package}'
    if key in _cache:
        return _cache[key]
    global_cutoff, per_package = _get_uv_config()
    cutoff = per_package.get(package, global_cutoff)
    resp = await session.get(f'https://pypi.org/rss/project/{package}/releases.xml', timeout=15)
    resp.raise_for_status()
    content = resp.content or b''
    root = Soup(content, 'xml')
    items = root.select('item')
    if not items:
        msg = f'No versions found for package `{package}`.'
        raise ValueError(msg)

    def _parse_version_safe(v: str) -> Version | None:
        try:
            return parse_version(v)
        except InvalidVersion:
            return None

    def _is_candidate(item: Tag) -> Version | None:
        title = item.select_one('title')
        if not title or not title.text:
            return None
        ver = _parse_version_safe(title.text)
        if (not ver or ver.is_prerelease or ver.is_devrelease
                or f'{package}-{ver}' in _PYPI_YANKED_RELEASES):
            return None
        if cutoff is not None:
            pub_el = item.select_one('pubDate')
            if pub_el and pub_el.text:
                try:
                    if parsedate_to_datetime(pub_el.text) > cutoff:
                        return None
                except (ValueError, TypeError):
                    pass
        return ver

    candidates = [v for item in items if (v := _is_candidate(item)) is not None]
    if not candidates and cutoff is not None:
        unfiltered = [
            v for item in items if (title := item.select_one('title')) and title.text and (
                v := _parse_version_safe(title.text)) is not None and not v.is_prerelease
            and not v.is_devrelease and f'{package}-{v}' not in _PYPI_YANKED_RELEASES
        ]
        if unfiltered:
            candidates = unfiltered
            log.debug('No PyPI version of %s passes exclude-newer; using latest unfiltered: %s',
                      package, max(candidates))
    if not candidates:
        msg = f'No versions found for package `{package}`.'
        raise ValueError(msg)
    result = str(max(candidates))
    _cache[key] = result
    return result


async def download_yarn_plugins(session: niquests.AsyncSession) -> None:
    """
    Download Yarn plugins.

    Parameters
    ----------
    session : niquests.AsyncSession
        The HTTP session.
    """
    resp = await session.get(PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI, timeout=15)
    resp.raise_for_status()
    text = resp.text or ''
    plugins_dir = anyio.Path('.yarn/plugins')
    await plugins_dir.mkdir(parents=True, exist_ok=True)
    await (plugins_dir / 'plugin-prettier-after-all-installed.cjs').write_text(f'{text.strip()}\n',
                                                                               encoding='utf-8')


async def download_yarn(session: niquests.AsyncSession, version: str) -> None:
    """
    Download the specified version of Yarn and save it to ``.yarn/releases``.

    Parameters
    ----------
    session : niquests.AsyncSession
        The HTTP session.
    version : str
        The Yarn version to download.
    """
    resp = await session.get(f'https://repo.yarnpkg.com/{version}/packages/yarnpkg-cli/bin/yarn.js',
                             timeout=15)
    resp.raise_for_status()
    text = resp.text or ''
    releases_dir = Path('.yarn/releases')
    await anyio.to_thread.run_sync(lambda: rmtree(releases_dir, ignore_errors=True))
    aio_releases_dir = anyio.Path(releases_dir)
    await aio_releases_dir.mkdir(parents=True, exist_ok=True)
    target = aio_releases_dir / f'yarn-{version}.cjs'
    await target.write_text(f'{text.strip()}\n', encoding='utf-8')
    await anyio.to_thread.run_sync(lambda: Path(target).chmod(0o755))


def _github_tag_disk_cache_path() -> Path:
    """
    Return the on-disk GitHub tag store path.

    Not memoised: ``platformdirs`` respects runtime environment changes (for example
    tests setting ``XDG_CACHE_HOME`` per case).
    """
    return platformdirs.user_cache_path('wiswa', appauthor=False) / _GITHUB_TAG_DISK_FILENAME


def _read_github_tag_disk_store() -> dict[str, str]:
    """
    Return the GitHub tag disk store, reading the file at most once per snapshot.

    The same mapping object is reused until :func:`clear_resolution_caches` runs or
    a persistence failure invalidates the snapshot, so callers that mutate the
    dict (see :func:`_write_github_tag_disk_entry`) keep the cache aligned.
    """
    cached = _github_tag_disk_store_memo_box[0]
    if cached is not None:
        return cached
    path = _github_tag_disk_cache_path()
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError):
        store: dict[str, str] = {}
    else:
        if not isinstance(raw, dict):
            store = {}
        else:
            store = {
                str(k): str(v)
                for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)
            }
    _github_tag_disk_store_memo_box[0] = store
    return store


def _write_github_tag_disk_entry(key: str, value: str) -> None:
    path = _github_tag_disk_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        store = _read_github_tag_disk_store()
        store[key] = value
        text = f'{json.dumps(store, indent=2, sort_keys=True)}\n'
        tmp = path.with_suffix(f'{path.suffix}.tmp')
        tmp.write_text(text, encoding='utf-8')
        tmp.replace(path)
    except OSError as exc:
        _github_tag_disk_store_memo_box[0] = None
        log.debug('Could not persist GitHub tag cache: %s', exc)


def _blocked_github_response_status(response: object) -> int | None:
    code = getattr(response, 'status_code', None)
    if isinstance(code, int) and code in {403, 429}:
        return code
    return None


async def get_github_release_latest_tag(
    session: niquests.AsyncSession,
    owner: str,
    repo: str,
    *,
    skip_releases: bool = False,
    allow_suffixes: bool = True,
) -> str:
    """
    Get the latest release tag from a GitHub repository.

    Parameters
    ----------
    session : niquests.AsyncSession
        The HTTP session.
    owner : str
        The repository owner.
    repo : str
        The repository name.
    skip_releases : bool
        Whether to skip releases and only consider tags.
    allow_suffixes : bool
        Whether to allow tags with suffixes (e.g. ``-beta``).

    Returns
    -------
    str
        The latest release tag.

    Raises
    ------
    ValueError
        If no tags are found.
    """
    key = f'gh_{owner}/{repo}_{skip_releases}_{allow_suffixes}'
    if key in _cache:
        return _cache[key]
    version: str | None = None
    blocked_status: int | None = None
    if not skip_releases:
        resp = await session.get(f'https://api.github.com/repos/{owner}/{repo}/releases/latest',
                                 timeout=15)
        gh_st = _blocked_github_response_status(resp)
        if gh_st is not None:
            blocked_status = gh_st
        if resp.ok:
            data = resp.json()
            version = data['tag_name']
    if not version:
        resp = await session.get(f'https://api.github.com/repos/{owner}/{repo}/tags', timeout=15)
        gh_st = _blocked_github_response_status(resp)
        if gh_st is not None:
            blocked_status = gh_st
        if resp.ok:
            data = resp.json()
            tags = [x['name'] for x in data if 'name' in x]
            if tags:
                if not allow_suffixes or (owner == 'google' and repo == 'yapf'):
                    version = next(x for x in tags if x.startswith('v') and (
                        re.search(r'\d$', x) if not allow_suffixes else True))
                else:
                    version = tags[0]
    if not version:
        if blocked_status is not None:
            disk_tag = _read_github_tag_disk_store().get(key)
            if disk_tag:
                log.warning(
                    'Using disk-cached GitHub tag %s for %s/%s after HTTP %d '
                    '(for example rate limiting or missing token).', disk_tag, owner, repo,
                    blocked_status)
                _cache[key] = disk_tag
                return disk_tag
        msg = f'Could not get latest tag for {owner}/{repo}.'
        raise ValueError(msg)
    _cache[key] = version
    _write_github_tag_disk_entry(key, version)
    return version
