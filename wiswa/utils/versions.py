"""Version fetching and Yarn download utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from functools import cache
from pathlib import Path
from shutil import rmtree
from typing import TYPE_CHECKING, Any, cast
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
    from collections.abc import Mapping

    import niquests

__all__ = ('clear_resolution_caches', 'download_yarn', 'download_yarn_plugins',
           'get_github_release_latest_tag', 'get_latest_yarn_version',
           'get_npm_latest_package_version', 'get_pypi_latest_package_version',
           'resolve_npm_minimal_age_gate_minutes')

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

_YARNRC_FILENAME = '.yarnrc.yml'

_GITHUB_RELEASES_PAGE_CAP = 20
_GITHUB_RELEASES_PER_PAGE = 100


def _npm_minimal_age_from_settings(settings: Mapping[str, Any] | None) -> int | None:
    if settings is None:
        return None
    yarnrc = settings.get('yarnrc')
    if not isinstance(yarnrc, dict):
        return None
    raw = yarnrc.get('npmMinimalAgeGate')
    if isinstance(raw, int):
        return max(0, raw)
    if isinstance(raw, str) and raw.strip().isdigit():
        return max(0, int(raw.strip()))
    return None


def _npm_minimal_age_from_project_snippet(snippet: str | None) -> int | None:
    if not snippet:
        return None
    m = re.search(r'npmMinimalAgeGate\s*:\s*(\d+)', snippet)
    if m:
        return max(0, int(m.group(1)))
    return None


def _npm_minimal_age_from_yarnrc_file(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return None
    for line in text.splitlines():
        stripped = line.split('#', 1)[0].strip()
        if stripped.startswith('npmMinimalAgeGate:'):
            rest = stripped.split(':', 1)[1].strip()
            try:
                return max(0, int(rest))
            except ValueError:
                return None
    return None


def _npm_minimal_age_from_yarnrc_files() -> int | None:
    for path in (Path.cwd() / _YARNRC_FILENAME, Path.home() / _YARNRC_FILENAME):
        if (v := _npm_minimal_age_from_yarnrc_file(path)) is not None:
            return v
    return None


def _npm_minimal_age_from_user_npmrc() -> int | None:
    path = Path.home() / '.npmrc'
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return None
    for line in text.splitlines():
        stripped = line.split('#', 1)[0].strip()
        if not stripped or '=' not in stripped:
            continue
        key, _, val = stripped.partition('=')
        if key.strip().lower() in {'min-release-age', 'min_release_age'}:
            try:
                days = max(0, int(val.strip()))
            except ValueError:
                return None
            return days * 24 * 60
    return None


def resolve_npm_minimal_age_gate_minutes(*,
                                         settings: Mapping[str, Any] | None = None,
                                         project_snippet: str | None = None) -> int:
    """
    Resolve npm minimal age gate in minutes for Yarn-aligned version filtering.

    Precedence: merged ``settings['yarnrc']['npmMinimalAgeGate']`` (minutes), a numeric match in
    the ``.wiswa.jsonnet`` project snippet, the repository or user ``.yarnrc.yml`` (minutes), then
    the user ``~/.npmrc`` key ``min-release-age`` (days, converted to minutes), then the 10080-
    minute default.

    Parameters
    ----------
    settings : Mapping[str, Any] | None
        Merged Wiswa settings, or ``None`` to skip this source.
    project_snippet : str | None
        Contents of the project ``.wiswa.jsonnet`` snippet, or ``None``.

    Returns
    -------
    int
        Minimal package age gate in minutes.
    """
    if (v := _npm_minimal_age_from_settings(settings)) is not None:
        return v
    if (v := _npm_minimal_age_from_project_snippet(project_snippet)) is not None:
        return v
    if (v := _npm_minimal_age_from_yarnrc_files()) is not None:
        return v
    if (v := _npm_minimal_age_from_user_npmrc()) is not None:
        return v
    return _NPM_AGE_GATE_DEFAULT_MINUTES


def _parse_duration(value: str) -> timedelta | None:
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
    response = await session.get('https://repo.yarnpkg.com/tags', timeout=15)
    response.raise_for_status()
    data = response.json()
    result = cast('str', data['latest']['stable'])
    _cache[key] = result
    return result


async def get_npm_latest_package_version(
        session: niquests.AsyncSession,
        package: str,
        *,
        npm_age_gate_minutes: int | None = None) -> str:  # pragma: no cover
    """
    Get the latest version of an npm package.

    Filters out versions published after the cutoff implied by ``npmMinimalAgeGate``; see
    :func:`resolve_npm_minimal_age_gate_minutes` for where that value is read when
    *npm_age_gate_minutes* is omitted. Versions that appear in the registry ``time`` map but are
    absent from the published ``versions`` map are also excluded.

    Parameters
    ----------
    session : niquests.AsyncSession
        The HTTP session.
    package : str
        The npm package name.
    npm_age_gate_minutes : int | None
        Age gate in minutes. When ``None``, :func:`resolve_npm_minimal_age_gate_minutes` is used
        with no settings or snippet (for example from the CLI).

    Returns
    -------
    str
        The latest version string that passes the age gate.
    """
    gate_min = (npm_age_gate_minutes
                if npm_age_gate_minutes is not None else resolve_npm_minimal_age_gate_minutes())
    key = f'npm_{package}_{gate_min}'
    if key in _cache:
        return _cache[key]
    resp = await session.get(f'https://registry.npmjs.org/{package}', timeout=15)
    resp.raise_for_status()
    data = resp.json()
    time_map: dict[str, str] = data.get('time', {})
    published_versions: set[str] = set(data.get('versions', {}))
    latest_tag = cast('str', data.get('dist-tags', {}).get('latest', ''))
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=gate_min)
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
                  package, gate_min, result)
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
    return platformdirs.user_cache_path('wiswa', appauthor=False) / _GITHUB_TAG_DISK_FILENAME


def _read_github_tag_disk_store() -> dict[str, str]:
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


def _version_from_github_tag_name(tag: str) -> Version | None:
    body = tag.removeprefix('v')
    try:
        ver = parse_version(body)
    except InvalidVersion:
        return None
    return ver


def _github_tag_allowed_for_policy(tag: str, *, allow_suffixes: bool, owner: str,
                                   repo: str) -> bool:
    if owner == 'google' and repo == 'yapf':
        if not tag.startswith('v'):
            return False
        return True if allow_suffixes else bool(re.search(r'\d$', tag))
    if not allow_suffixes:
        return tag.startswith('v') and bool(re.search(r'\d$', tag))
    return True


async def _github_newest_release_tag_respecting_cutoff(
        session: niquests.AsyncSession, owner: str, repo: str, *, cutoff: datetime,
        allow_suffixes: bool) -> tuple[str | None, int | None]:
    """
    Return the highest semantic version among GitHub releases published on or before *cutoff*.

    Returns
    -------
    tuple[str | None, int | None]
        Selected ``tag_name``, or ``(None, status)`` when the GitHub API blocks access.
    """
    best: tuple[Version, str] | None = None
    for page in range(1, _GITHUB_RELEASES_PAGE_CAP + 1):
        resp = await session.get(
            f'https://api.github.com/repos/{owner}/{repo}/releases'
            f'?per_page={_GITHUB_RELEASES_PER_PAGE}&page={page}',
            timeout=15)
        gh_st = _blocked_github_response_status(resp)
        if gh_st is not None:
            return None, gh_st
        if not resp.ok:
            break
        batch = resp.json()
        if not isinstance(batch, list) or not batch:
            break
        for rel in batch:
            if not isinstance(rel, dict):
                continue
            if rel.get('draft'):
                continue
            if rel.get('prerelease'):
                continue
            tag = rel.get('tag_name')
            if not isinstance(tag, str) or not tag:
                continue
            published = rel.get('published_at')
            if not isinstance(published, str):
                continue
            try:
                pub_dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
            except ValueError:
                continue
            if pub_dt > cutoff:
                continue
            if not _github_tag_allowed_for_policy(
                    tag, allow_suffixes=allow_suffixes, owner=owner, repo=repo):
                continue
            ver_obj = _version_from_github_tag_name(tag)
            if ver_obj is None or ver_obj.is_prerelease or ver_obj.is_devrelease:
                continue
            if best is None or ver_obj > best[0]:
                best = (ver_obj, tag)
        if len(batch) < _GITHUB_RELEASES_PER_PAGE:
            break
    return (best[1] if best else None), None


async def get_github_release_latest_tag(session: niquests.AsyncSession,
                                        owner: str,
                                        repo: str,
                                        *,
                                        skip_releases: bool = False,
                                        allow_suffixes: bool = True,
                                        apply_npm_min_release_age: bool = False,
                                        npm_age_gate_minutes: int | None = None) -> str:
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
    apply_npm_min_release_age : bool
        When set, prefer releases at least as old as the resolved npm age gate (see
        :func:`resolve_npm_minimal_age_gate_minutes`) before falling back to unfiltered
        ``releases/latest`` or tag list logic, mirroring :func:`get_npm_latest_package_version`.
    npm_age_gate_minutes : int | None
        Minutes for the age gate when *apply_npm_min_release_age* is set. When ``None``, uses
        :func:`resolve_npm_minimal_age_gate_minutes` without settings (callers from Jsonnet supply
        the value computed from merged settings and the project snippet).

    Returns
    -------
    str
        The latest release tag.

    Raises
    ------
    ValueError
        If no tags are found.
    """
    rg_for_gate: int | None = None
    if apply_npm_min_release_age:
        rg_for_gate = (npm_age_gate_minutes if npm_age_gate_minutes is not None else
                       resolve_npm_minimal_age_gate_minutes())
    key = f'gh_{owner}/{repo}_{skip_releases}_{allow_suffixes}'
    if rg_for_gate is not None:
        key += f'_npmage{rg_for_gate}'
    if key in _cache:
        return _cache[key]
    version: str | None = None
    blocked_status: int | None = None

    if apply_npm_min_release_age:
        gate_minutes = cast('int', rg_for_gate)
        cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=gate_minutes)
        gated, gh_st = await _github_newest_release_tag_respecting_cutoff(
            session, owner, repo, cutoff=cutoff, allow_suffixes=allow_suffixes)
        if gh_st is not None:
            blocked_status = gh_st
        if gated:
            version = gated
        else:
            log.debug(
                'No GitHub release for %s/%s is older than the npm minimal age gate (%d minutes); '
                'falling back to latest tag logic.', owner, repo, gate_minutes)

    if not version and not skip_releases:
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
