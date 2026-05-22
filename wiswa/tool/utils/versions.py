"""Version fetching and Yarn download utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import cache
from pathlib import Path
from shutil import rmtree
from typing import TYPE_CHECKING, Any, cast
import logging
import operator
import re

from anyio.to_thread import run_sync
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version, parse as parse_version
from wiswa.tool.constants import PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI
from wiswa.vcs.github import clear_tag_cache, latest_release_tag
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

_PYPI_YANKED_RELEASES = {'sphinx-8.3.0'}

_cache: dict[str, str] = {}

_NPM_AGE_GATE_DEFAULT_MINUTES = 10080
"""Default npm minimum age gate in minutes (7 days)."""

_YARNRC_FILENAME = '.yarnrc.yml'

_NODE_RANGE_RE = re.compile(r'>=\s*(\d+)')
"""
Matches the common node-engine lower-bound pattern ``>=N`` (optionally with trailing minor or
patch components). Only the major component is captured because only that granularity is needed
to decide whether a package version is compatible with a given Node major release.
"""


def _node_engine_min_major(constraint: str) -> int | None:
    """
    Extract the smallest Node major version implied by a node-engine constraint string.

    Only simple ``>=`` lower-bound forms are recognised (for example ``>=20``, ``>=14.17.0``,
    ``>=18 <23``). Anything else (including ``*``, ``^20``, OR-joined clauses, and empty strings)
    returns :data:`None`, which the caller should treat as an unknown or no-constraint case and
    therefore skip filtering.

    Parameters
    ----------
    constraint : str
        The engine constraint string taken from a package manifest.

    Returns
    -------
    int | None
        The smallest Node major version allowed by the constraint, or :data:`None` if no
        ``>=`` lower bound could be parsed.
    """
    if not constraint:
        return None
    majors = [int(m.group(1)) for m in _NODE_RANGE_RE.finditer(constraint)]
    if not majors:
        return None
    return min(majors)


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


def _coerce_per_package_value(val: Any) -> tuple[bool, datetime | None]:
    """
    Coerce a raw ``exclude-newer-package`` entry to a ``(present, cutoff)`` tuple.

    A value of ``False`` means the package is *explicitly opted out* of the global cutoff;
    in that case the entry is present but the cutoff is :py:data:`None`. A timestamp string
    or duration produces a parsed :py:class:`~datetime.datetime`. Anything else (``True``,
    invalid strings) is treated as not-present so the global cutoff continues to apply.

    Parameters
    ----------
    val : Any
        The raw value from the TOML mapping.

    Returns
    -------
    tuple[bool, datetime | None]
        ``(present, cutoff)``. ``present=False`` means the entry should be ignored;
        ``present=True, cutoff=None`` means the package bypasses the cutoff entirely.
    """
    if isinstance(val, bool):
        return (True, None) if val is False else (False, None)
    dt = _parse_exclude_newer(str(val))
    if dt is None:
        return False, None
    return True, dt


def _apply_uv_section(section: Mapping[str, Any], global_cutoff: datetime | None,
                      per_package: dict[str, datetime | None]) -> datetime | None:
    """
    Merge a single ``[tool.uv]``/``uv.toml`` section into the running config.

    Parameters
    ----------
    section : Mapping[str, Any]
        The mapping to read ``exclude-newer`` and ``exclude-newer-package`` from.
    global_cutoff : datetime | None
        The current global cutoff; returned unchanged when the section does not set one.
    per_package : dict[str, datetime | None]
        Per-package map, mutated in place. ``None`` values mean "explicitly opted out".

    Returns
    -------
    datetime | None
        The (possibly updated) global cutoff.
    """
    raw = section.get('exclude-newer')
    if raw is not None:
        parsed = _parse_exclude_newer(str(raw))
        if parsed is not None:
            global_cutoff = parsed
    pkg_map = section.get('exclude-newer-package')
    if isinstance(pkg_map, dict):
        for pkg, val in pkg_map.items():
            present, cutoff = _coerce_per_package_value(val)
            if present:
                per_package[str(pkg)] = cutoff
    return global_cutoff


def _read_toml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return tomlkit.loads(path.read_text(encoding='utf-8')).unwrap()
    except OSError:
        return None


@cache
def _get_uv_config(
        project_root: Path | None = None) -> tuple[datetime | None, dict[str, datetime | None]]:
    """
    Read ``exclude-newer`` and ``exclude-newer-package`` from uv's configuration.

    Reads the user-level ``uv.toml`` (resolved via
    :func:`platformdirs.user_config_path`) first, then merges the project's
    ``pyproject.toml`` ``[tool.uv]`` section on top so project values override the user
    config — matching uv's own precedence.

    Parameters
    ----------
    project_root : Path | None
        Directory to search for ``pyproject.toml``. Defaults to :py:meth:`Path.cwd`.

    Returns
    -------
    tuple[datetime | None, dict[str, datetime | None]]
        The global cutoff (or :py:data:`None`) and the per-package map. A per-package
        value of :py:data:`None` means the package is explicitly exempt from any cutoff.
    """
    global_cutoff: datetime | None = None
    per_package: dict[str, datetime | None] = {}
    user_toml = _read_toml(platformdirs.user_config_path('uv', appauthor=False) / 'uv.toml')
    if user_toml is not None:
        global_cutoff = _apply_uv_section(user_toml, global_cutoff, per_package)
    project_pyproject = _read_toml((project_root or Path.cwd()) / 'pyproject.toml')
    if project_pyproject is not None:
        tool_uv = project_pyproject.get('tool', {}).get('uv')
        if isinstance(tool_uv, dict):
            global_cutoff = _apply_uv_section(tool_uv, global_cutoff, per_package)
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
    _get_uv_config.cache_clear()
    clear_tag_cache()


async def get_latest_yarn_version(session: niquests.AsyncSession) -> str:
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
        node_constraint: str = '',
        npm_age_gate_minutes: int | None = None) -> str:  # pragma: no cover
    """
    Get the latest version of an npm package.

    Filters out versions published after the cutoff implied by ``npmMinimalAgeGate``; see
    :func:`resolve_npm_minimal_age_gate_minutes` for where that value is read when
    *npm_age_gate_minutes* is omitted. Versions that appear in the registry ``time`` map but are
    absent from the published ``versions`` map are also excluded.

    When *node_constraint* is a ``>=`` style range (for example ``>=20`` from
    ``package.json``'s ``engines.node``), package versions whose own ``engines.node`` demands a
    higher Node major than the constraint's minimum are filtered out so the returned version will
    install cleanly on that Node release.

    Parameters
    ----------
    session : niquests.AsyncSession
        The HTTP session.
    package : str
        The npm package name.
    node_constraint : str
        The caller's Node engine constraint (for example ``'>=20'``). An empty string disables
        Node-engine filtering.
    npm_age_gate_minutes : int | None
        Age gate in minutes. When ``None``, :func:`resolve_npm_minimal_age_gate_minutes` is used
        with no settings or snippet (for example from the CLI).

    Returns
    -------
    str
        The latest version string that passes the age gate and the Node-engine filter.
    """
    gate_min = (npm_age_gate_minutes
                if npm_age_gate_minutes is not None else resolve_npm_minimal_age_gate_minutes())
    node_min = _node_engine_min_major(node_constraint)
    key = f'npm_{package}_{gate_min}_{node_min if node_min is not None else ""}'
    if key in _cache:
        return _cache[key]
    resp = await session.get(f'https://registry.npmjs.org/{package}', timeout=15)
    resp.raise_for_status()
    data = resp.json()
    time_map: dict[str, str] = data.get('time', {})
    published_versions: dict[str, Any] = data.get('versions', {})
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
        if pub_date > cutoff:
            continue
        if node_min is not None:
            engines = published_versions[ver_str].get('engines', {})
            pkg_min = _node_engine_min_major(engines.get('node', ''))
            if pkg_min is not None and pkg_min > node_min:
                continue
        candidates.append((ver, pub_date))
    if candidates:
        result = str(max(candidates, key=operator.itemgetter(0))[0])
    else:
        result = latest_tag
        log.debug('No npm version of %s passes the age gate of %d minutes; using latest: %s',
                  package, gate_min, result)
    _cache[key] = result
    return result


def _requires_python_compatible(files: list[dict[str, Any]], python: str) -> bool:
    for f in files:
        raw = f.get('requires_python')
        if not isinstance(raw, str) or not raw.strip():
            return True
        try:
            return Version(python) in SpecifierSet(raw)
        except (InvalidSpecifier, InvalidVersion):
            return True
    return True


def _earliest_upload_time(files: list[dict[str, Any]]) -> datetime | None:
    earliest: datetime | None = None
    for f in files:
        raw = f.get('upload_time_iso_8601')
        if not isinstance(raw, str):
            continue
        try:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError:
            continue
        if earliest is None or dt < earliest:
            earliest = dt
    return earliest


async def get_pypi_latest_package_version(session: niquests.AsyncSession,
                                          package: str,
                                          *,
                                          host: str = 'pypi.org',
                                          python: str | None = None) -> str:
    """
    Get the latest version of a PyPI package.

    Respects ``exclude-newer-package`` (per-package) and ``exclude-newer`` (global) from uv's
    user ``uv.toml`` (via ``platformdirs``) to filter out versions published after the cutoff.

    When *python* is a non-empty version string (for example ``'3.10'``), releases whose
    ``requires_python`` specifier excludes that version are filtered out.

    Parameters
    ----------
    session : niquests.AsyncSession
        The HTTP session.
    package : str
        The PyPI package name.
    host : str
        The PyPI-compatible host to query. Defaults to ``pypi.org``.
    python : str | None
        The Python version to require compatibility with (for example ``'3.10'``). ``None``
        disables Python-version filtering.

    Returns
    -------
    str
        The latest non-prerelease, non-dev version string.

    Raises
    ------
    ValueError
        If no versions are found or no version is compatible with ``python``.
    """
    key = f'pypi_{host}_{package}_{python}'
    if key in _cache:
        return _cache[key]
    global_cutoff, per_package = _get_uv_config()
    cutoff = per_package.get(package, global_cutoff)
    resp = await session.get(f'https://{host}/pypi/{package}/json', timeout=15)
    resp.raise_for_status()
    data = resp.json()
    releases: dict[str, list[dict[str, Any]]] = data.get('releases', {})
    if not releases:
        msg = f'No versions found for package `{package}`.'
        raise ValueError(msg)
    candidates: list[Version] = []
    unfiltered: list[Version] = []
    for ver_str, files in releases.items():
        try:
            ver = parse_version(ver_str)
        except InvalidVersion:
            continue
        if ver.is_prerelease or ver.is_devrelease:
            continue
        if f'{package}-{ver}' in _PYPI_YANKED_RELEASES:
            continue
        if python and not _requires_python_compatible(files, python):
            continue
        if cutoff is not None:
            upload_time = _earliest_upload_time(files)
            if upload_time is not None and upload_time > cutoff:
                unfiltered.append(ver)
                continue
        candidates.append(ver)
    if not candidates and cutoff is not None and unfiltered:
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
    await run_sync(lambda: rmtree(releases_dir, ignore_errors=True))
    aio_releases_dir = anyio.Path(releases_dir)
    await aio_releases_dir.mkdir(parents=True, exist_ok=True)
    target = aio_releases_dir / f'yarn-{version}.cjs'
    await target.write_text(f'{text.strip()}\n', encoding='utf-8')
    await run_sync(lambda: Path(target).chmod(0o755))


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

    Thin Wiswa-side adapter that resolves the npm minimum-release-age gate via
    :py:func:`resolve_npm_minimal_age_gate_minutes` (a Wiswa-only concern that reads
    ``yarnrc.npmMinimalAgeGate`` from ``uv.toml``) and forwards the rest to
    :py:func:`wiswa.vcs.github.latest_release_tag`. The ``google/yapf`` repository is mapped to
    ``require_v_prefix=True`` because its tag scheme allows non-``v`` names that should not be
    picked.

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
        :py:func:`resolve_npm_minimal_age_gate_minutes`) before falling back to unfiltered
        ``releases/latest`` or tag list logic, mirroring
        :py:func:`get_npm_latest_package_version`.
    npm_age_gate_minutes : int | None
        Minutes for the age gate when *apply_npm_min_release_age* is set. When :py:data:`None`,
        uses :py:func:`resolve_npm_minimal_age_gate_minutes` without settings.

    Returns
    -------
    str
        The latest release tag.
    """
    min_age: int | None = None
    if apply_npm_min_release_age:
        min_age = (npm_age_gate_minutes
                   if npm_age_gate_minutes is not None else resolve_npm_minimal_age_gate_minutes())
    require_v_prefix = owner == 'google' and repo == 'yapf'
    return await latest_release_tag(session,
                                    owner,
                                    repo,
                                    skip_releases=skip_releases,
                                    allow_suffixes=allow_suffixes,
                                    require_v_prefix=require_v_prefix,
                                    min_release_age_minutes=min_age)
