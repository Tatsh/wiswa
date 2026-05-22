"""Evaluate Jsonnet for merged settings and generated project output."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeAlias, cast
from urllib.parse import urlparse
import configparser
import fnmatch
import json
import logging
import re
import shutil
import subprocess as sp
import time

from anyio.from_thread import run as run_async_from_worker_thread
from anyio.to_thread import run_sync
from wiswa.vcs.github import ref_commit_sha
import _jsonnet  # noqa: PLC2701
import anyio
import platformdirs

from .path import tests_dir_has_pytest_modules_excluding_starter_main
from .versions import (
    get_github_release_latest_tag,
    get_latest_yarn_version,
    get_npm_latest_package_version,
    get_pypi_latest_package_version,
    resolve_npm_minimal_age_gate_minutes,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from niquests import AsyncSession
    from wiswa.tool.typing import Settings

JsonnetNativeCallback: TypeAlias = tuple[tuple[str, ...], Callable[..., Any]]

__all__ = ('FlatpakConfigurationError', 'RemoteHostConflictError', 'evaluate_jsonnet_file',
           'evaluate_jsonnet_project', 'evaluate_merged_settings', 'resolve_defaults_only',
           'validate_flatpak_app_id', 'validate_remote_host_flags')

_FLATPAK_APP_ID_HELP = (
    'want_flatpak is true but publishing.flathub (Flatpak app ID) is not set. '
    'Set publishing.flathub to a reverse-DNS id (for example org.example.MyApp).')

_REMOTE_HOST_CONFLICT_HELP = (
    'using_github and using_gitlab cannot both be true. Adjust .wiswa.jsonnet '
    '(or repository_uri and using_* overrides) so only one remote host applies.')

_NO_FINAL_NEWLINE_PATTERNS: tuple[str, ...] = ('vcpkg*.json',)
"""
Filename globs whose generated output must NOT end with a newline.

Dependabot rewrites these files without a trailing newline; matching its convention prevents an
endless regen-versus-Dependabot diff loop.

:meta hide-value:
"""


class RemoteHostConflictError(ValueError):
    """Raised when both ``using_github`` and ``using_gitlab`` are true."""
    def __init__(self) -> None:
        super().__init__(_REMOTE_HOST_CONFLICT_HELP)


class FlatpakConfigurationError(ValueError):
    """Raised when ``want_flatpak`` is true but ``publishing.flathub`` is missing or blank."""
    def __init__(self) -> None:
        super().__init__(_FLATPAK_APP_ID_HELP)


def validate_flatpak_app_id(settings: dict[str, Any]) -> None:
    """
    Validate Flatpak publishing when ``want_flatpak`` is set.

    Parameters
    ----------
    settings : dict[str, Any]
        Merged Wiswa settings dictionary.

    Raises
    ------
    FlatpakConfigurationError
        If ``publishing`` is invalid or ``flathub`` is unset or blank.
    """
    if not settings.get('want_flatpak'):
        return
    publishing = settings.get('publishing')
    if not isinstance(publishing, dict):
        raise FlatpakConfigurationError
    flathub = publishing.get('flathub', '')
    if not isinstance(flathub, str) or not flathub.strip():
        raise FlatpakConfigurationError


def validate_remote_host_flags(settings: dict[str, Any]) -> None:
    """
    Reject merged settings when both GitHub and GitLab remotes are selected.

    Parameters
    ----------
    settings : dict[str, Any]
        Merged Wiswa settings dictionary.

    Raises
    ------
    RemoteHostConflictError
        If ``using_github`` and ``using_gitlab`` are both true.
    """
    if settings.get('using_github') and settings.get('using_gitlab'):
        raise RemoteHostConflictError


log = logging.getLogger(__name__)

# Whether to merge `defaults.jsonnet` from the user config dir is detected by scanning the project
# snippet so Jsonnet runs once. Enabling user defaults only inside that file (without this literal
# in `.wiswa.jsonnet`) is not supported.
_PROJECT_USES_USER_DEFAULTS = re.compile(r'uses_user_defaults\s*:\s*true\b')

_GH_USERNAME_TIMEOUT_SEC = 10
_UNKNOWN_GITHUB_USER = 'unknown'


def _github_cli_username() -> str | None:
    gh_executable = shutil.which('gh')
    if not gh_executable:
        return None
    try:
        proc = sp.run((gh_executable, 'api', 'user', '--jq', '.login'),
                      check=True,
                      capture_output=True,
                      text=True,
                      timeout=_GH_USERNAME_TIMEOUT_SEC)
    except (OSError, sp.CalledProcessError, sp.TimeoutExpired):
        return None
    login = proc.stdout.strip()
    return login or None


def _github_owner_from_remote_url(url: str) -> str | None:
    """
    Return the repository owner from *url* if it targets github.com.

    *url* must be stripped and non-empty (callers skip blank ``remote.origin.url`` values).

    Returns
    -------
    str | None
        Owner login, or ``None`` when *url* does not reference GitHub.
    """
    if url.startswith('git@github.com:'):
        rest = url.removeprefix('git@github.com:')
        segment = rest.split('/')[0]
        return segment.removesuffix('.git') or None
    for prefix in ('git://github.com/', 'ssh://git@github.com/'):
        if url.startswith(prefix):
            rest = url.removeprefix(prefix)
            segment = rest.split('/')[0]
            return segment.removesuffix('.git') or None
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    if host in {'github.com', 'www.github.com'}:
        segments = [segment for segment in parsed.path.strip('/').split('/') if segment]
        if segments:
            return segments[0].removesuffix('.git')
    return None


def _iter_git_config_paths() -> Iterator[Path]:
    """Local ``config`` paths for the current Git checkout (main and worktree common dir).

    Yields
    ------
    Path
        Path to a ``config`` file to try for ``remote.origin.url``.
    """
    git_entry = Path('.git')
    if not git_entry.exists():
        return
    if git_entry.is_dir():
        yield git_entry / 'config'
        return
    try:
        content = git_entry.read_text(encoding='utf-8')
    except OSError:
        return
    for line in content.splitlines():
        line_stripped = line.strip()
        if line_stripped.startswith('gitdir: '):
            git_dir = Path(line_stripped.split(':', 1)[1].strip()).resolve()
            yield git_dir / 'config'
            commondir = git_dir / 'commondir'
            if commondir.is_file():
                try:
                    common_git = (git_dir / commondir.read_text(encoding='utf-8').strip()).resolve()
                except OSError:
                    pass
                else:
                    yield common_git / 'config'
            break


def _origin_url_from_git_config_file(config_path: Path) -> str | None:
    parser = configparser.ConfigParser(interpolation=None)
    # ``str`` preserves key case; ``setattr`` avoids strict stub mismatch on ``optionxform``.
    setattr(parser, 'optionxform', str)  # noqa: B010
    try:
        parser.read(config_path, encoding='utf-8')
    except configparser.Error:
        return None
    section = 'remote "origin"'
    if parser.has_section(section):
        return parser.get(section, 'url', fallback=None)
    return None


def _github_username_from_git_origin() -> str | None:
    seen: set[Path] = set()
    for cfg in _iter_git_config_paths():
        if not cfg.is_file():
            continue
        key = cfg.resolve()
        if key in seen:
            continue
        seen.add(key)
        url_raw = _origin_url_from_git_config_file(cfg)
        url = (url_raw or '').strip()
        if not url:
            continue
        owner = _github_owner_from_remote_url(url)
        if owner:
            return owner
    return None


def _default_github_username() -> str:
    if login := _github_cli_username():
        return login
    if owner := _github_username_from_git_origin():
        return owner
    return _UNKNOWN_GITHUB_USER


def _make_native_callbacks(
        session: AsyncSession | None = None,
        merged_settings: Settings | None = None,
        project_settings_snippet: str | None = None) -> dict[str, JsonnetNativeCallback]:
    github_cli_username_cb: JsonnetNativeCallback = ((), _default_github_username)
    if session is None:
        return {
            'githubCliUsername': github_cli_username_cb,
            'isodate': ((), lambda: datetime.now(tz=timezone.utc).isoformat()[:10]),
            'year': ((), lambda: datetime.now(tz=timezone.utc).year)
        }
    # Jsonnet native callbacks are sync, but our HTTP functions are async. These callbacks run
    # inside run_sync, so we use :func:`anyio.from_thread.run` to schedule the async
    # work on the event loop.

    def _sync_wrap(async_fn: Callable[..., Any], *args: Any,
                   **kwargs: Any) -> Any:  # pragma: no cover
        return run_async_from_worker_thread(partial(async_fn, *args, **kwargs))

    npm_age_gate = resolve_npm_minimal_age_gate_minutes(settings=merged_settings,
                                                        project_snippet=project_settings_snippet)
    node_engine = merged_settings['node_engine'] if merged_settings else ''
    npm_age_gate_exclude: frozenset[str] = frozenset(
        merged_settings.get('npm_age_gate_exclude_packages', ()) if merged_settings else ())
    gh_action = partial(get_github_release_latest_tag,
                        session,
                        skip_releases=True,
                        allow_suffixes=False)
    gh_tag = partial(get_github_release_latest_tag, session, skip_releases=True)
    gh_ref_sha = partial(ref_commit_sha, session)
    return {
        # The argument names here cannot conflict with a wrapping function.
        # f(arg):: std.native('f', arg) will fail if it's defined here as 'f': (('arg',), ...).
        'githubCliUsername': github_cli_username_cb,
        'githubLatestActionTag': (('o', 'r'), lambda o, r: _sync_wrap(gh_action, o, r)),
        'githubLatestReleaseTag': (
            ('o', 'r', 'g'), lambda o, r, g=False: _sync_wrap(get_github_release_latest_tag,
                                                              session,
                                                              o,
                                                              r,
                                                              apply_npm_min_release_age=bool(g),
                                                              npm_age_gate_minutes=npm_age_gate)),
        'githubLatestTag': (('o', 'r'), lambda o, r: _sync_wrap(gh_tag, o, r)),
        'githubRefCommitSha': (('o', 'r', 'f'), lambda o, r, f: _sync_wrap(gh_ref_sha, o, r, f)),
        'isodate': ((), lambda: datetime.now(tz=timezone.utc).isoformat()[:10]),
        'latestNpmPackageVersion': (('p',), lambda p: _sync_wrap(
            get_npm_latest_package_version,
            session,
            p,
            node_constraint=node_engine,
            npm_age_gate_minutes=(0 if p in npm_age_gate_exclude else npm_age_gate))),
        'latestPypiPackageVersion': (('p', 'h', 'py'), lambda p, h='pypi.org', py='': _sync_wrap(
            get_pypi_latest_package_version, session, p, host=h, python=py or None)),
        'latestYarnVersion': ((), lambda: _sync_wrap(get_latest_yarn_version, session)),
        'year': ((), lambda: datetime.now(tz=timezone.utc).year)
    }


async def evaluate_jsonnet_file(jpathdir: Sequence[str],
                                file: Path,
                                merged_settings: str,
                                session: AsyncSession | None = None) -> str:
    """
    Evaluate a Jsonnet file with the given settings.

    Parameters
    ----------
    jpathdir : Sequence[str]
        The Jsonnet library search path.
    file : Path
        The path to the Jsonnet file to evaluate.
    merged_settings : str
        The merged settings as a JSON string.
    session : AsyncSession | None
        HTTP session for live package and release native callbacks, or ``None`` to use only
        username and date native helpers.

    Returns
    -------
    str
        The evaluated Jsonnet output as a string.
    """
    merged_dict: Settings | None = None
    try:
        raw_merged = json.loads(merged_settings)
        if isinstance(raw_merged, dict):
            merged_dict = cast('Settings', raw_merged)
    except json.JSONDecodeError:
        merged_dict = None
    native_callbacks = _make_native_callbacks(session, merged_settings=merged_dict)
    path_str = str(file)

    def _evaluate() -> str:
        return _jsonnet.evaluate_file(path_str,
                                      jpathdir=list(jpathdir),
                                      native_callbacks=native_callbacks,
                                      tla_codes={'settings': merged_settings})

    t0 = time.perf_counter()
    result = await run_sync(_evaluate)
    log.debug('Jsonnet evaluation of `%s` took %.3fs.', path_str, time.perf_counter() - t0)
    return result


async def evaluate_jsonnet_project(lib_path: Path,
                                   jpathdir: Sequence[str],
                                   merged_settings: str,
                                   session: AsyncSession | None = None,
                                   file: Path | None = None,
                                   output_dir: Path | None = None) -> None:
    """
    Evaluate ``project.jsonnet`` to output generated files.

    Parameters
    ----------
    lib_path : Path
        The path to the Jsonnet library.
    jpathdir : Sequence[str]
        The Jsonnet library search path.
    merged_settings : str
        The merged settings as a JSON string.
    session : AsyncSession | None
        HTTP session for live package and release native callbacks, or ``None`` to use only
        username and date native helpers.
    file : Path | None
        The path to the Jsonnet file to evaluate (defaults to ``project.jsonnet`` in the library).
    output_dir : Path | None
        Output directory for generated files (defaults to the current directory).

    Notes
    -----
    Generated files are written with a trailing newline, except for filenames matching the globs in
    ``_NO_FINAL_NEWLINE_PATTERNS`` (for example ``vcpkg*.json``) which are written without one to
    match Dependabot's formatting and avoid regen-versus-Dependabot diff loops.
    """
    if output_dir:
        await anyio.Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_dir = output_dir or Path()
    filename: str
    for filename, content in json.loads(await evaluate_jsonnet_file(
            jpathdir, file or (lib_path / 'project.jsonnet'), merged_settings, session)).items():
        output_file = anyio.Path(output_dir / filename)
        await output_file.parent.mkdir(parents=True, exist_ok=True)
        stripped = content.strip()
        base = Path(filename).name
        if any(fnmatch.fnmatchcase(base, pat) for pat in _NO_FINAL_NEWLINE_PATTERNS):
            await output_file.write_text(stripped)
        else:
            await output_file.write_text(f'{stripped}\n')
        log.debug('Wrote `%s`.', output_file)


async def evaluate_merged_settings(jpathdir: Sequence[str],
                                   lib_path: Path,
                                   settings: str,
                                   session: AsyncSession | None = None) -> tuple[str, Settings]:
    """
    Evaluate the merged settings using Jsonnet.

    The merge order is built-in ``defaults.libsonnet``, then user-level ``defaults.jsonnet``, then
    the project file. The user-level file is read only when the project snippet contains the literal
    pattern ``uses_user_defaults: true`` (regex, not a full Jsonnet parse).

    Parameters
    ----------
    jpathdir : Sequence[str]
        The Jsonnet library search path.
    lib_path : Path
        The path to the Jsonnet library.
    settings : str
        The project settings snippet (for example the contents of ``.wiswa.jsonnet``).
    session : AsyncSession | None
        HTTP session for live package and release native callbacks, or ``None`` to use only
        username and date native helpers.

    Returns
    -------
    tuple[str, Settings]
        The evaluated merged settings as a JSON string and as a Settings object.
    """
    user_defaults_jsonnet = (platformdirs.user_config_path('wiswa', appauthor=False) /
                             'defaults.jsonnet')
    native_callbacks = _make_native_callbacks(session,
                                              merged_settings=None,
                                              project_settings_snippet=settings)
    defaults_path = anyio.Path(
        lib_path.resolve(strict=True) / 'defaults.libsonnet')  # noqa: ASYNC240
    defaults_text = await defaults_path.read_text()
    user_defaults_text = '{}'
    if _PROJECT_USES_USER_DEFAULTS.search(settings):
        aio_user = anyio.Path(user_defaults_jsonnet)
        if await aio_user.exists():
            user_defaults_text = await aio_user.read_text(encoding='utf-8')

    async def _eval_merge(user_overlay: str) -> str:
        t0 = time.perf_counter()
        result = await run_sync(lambda: _jsonnet.evaluate_snippet(
            '',
            'function(defaults, user_defaults, settings) defaults + user_defaults + settings',
            jpathdir=list(jpathdir),
            native_callbacks=native_callbacks,
            tla_codes={
                'defaults': defaults_text,
                'settings': settings,
                'user_defaults': user_overlay
            }))
        log.debug('Jsonnet evaluation (merged settings) took %.3fs.', time.perf_counter() - t0)
        return result

    merged_json = await _eval_merge(user_defaults_text)
    merged_dict = json.loads(merged_json)
    validate_flatpak_app_id(merged_dict)
    validate_remote_host_flags(merged_dict)
    readme_existed = await anyio.Path('README.md').exists()
    established_pytest = await tests_dir_has_pytest_modules_excluding_starter_main()
    return merged_json, cast('Settings', (merged_dict
                                          | {
                                              '_readme_existed': readme_existed,
                                              '_has_established_pytest_modules': established_pytest
                                          }))


async def resolve_defaults_only(jpathdir: Sequence[str],
                                lib_path: Path,
                                session: AsyncSession | None = None) -> dict[str, Any]:
    """
    Resolve the default settings without any project or user overrides.

    Parameters
    ----------
    jpathdir : Sequence[str]
        The Jsonnet library search path.
    lib_path : Path
        The path to the Jsonnet library.
    session : AsyncSession | None
        HTTP session for live package and release native callbacks, or ``None`` to use only
        username and date native helpers.

    Returns
    -------
    dict[str, Any]
        The resolved default settings.
    """
    native_callbacks = _make_native_callbacks(session,
                                              merged_settings=None,
                                              project_settings_snippet=None)
    defaults_path = anyio.Path(
        lib_path.resolve(strict=True) / 'defaults.libsonnet')  # noqa: ASYNC240
    defaults_text = await defaults_path.read_text()
    t0 = time.perf_counter()
    s = await run_sync(lambda: _jsonnet.evaluate_snippet(
        '',
        'function(defaults, user_defaults, settings) defaults + user_defaults + settings',
        jpathdir=list(jpathdir),
        native_callbacks=native_callbacks,
        tla_codes={
            'defaults': defaults_text,
            'settings': '{}',
            'user_defaults': '{}'
        }))
    log.debug('Jsonnet evaluation (defaults only) took %.3fs.', time.perf_counter() - t0)
    result: dict[str, Any] = json.loads(s)
    validate_remote_host_flags(result)
    return result
