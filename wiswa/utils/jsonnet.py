"""Jsonnet evaluation."""
from __future__ import annotations

from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any
import json
import logging

import _jsonnet  # noqa: PLC2701
import anyio
import platformdirs

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from niquests import AsyncSession
    from wiswa.typing import Settings

__all__ = ('evaluate_jsonnet_file', 'evaluate_jsonnet_project', 'evaluate_merged_settings',
           'resolve_defaults_only')

log = logging.getLogger(__name__)


def _make_native_callbacks(
        session: AsyncSession | None = None
) -> dict[str, tuple[tuple[str, ...], Callable[..., Any]]]:
    from .versions import (  # noqa: PLC0415, I001
        get_github_release_latest_tag, get_latest_yarn_version, get_npm_latest_package_version,
        get_pypi_latest_package_version,
    )

    if session is None:
        return {
            'isodate': ((), lambda: datetime.now(tz=timezone.utc).isoformat()[:10]),
            'year': ((), lambda: datetime.now(tz=timezone.utc).year),
        }
    # Jsonnet native callbacks are sync, but our HTTP functions are async. These callbacks run
    # inside anyio.to_thread.run_sync, so we use anyio.from_thread.run to schedule the async
    # call back on the event loop.

    def _sync_wrap(async_fn: Callable[..., Any], *args: Any) -> Any:  # pragma: no cover
        return anyio.from_thread.run(async_fn, *args)

    gh_action = partial(get_github_release_latest_tag,
                        session,
                        actions=True,
                        skip_releases=True,
                        allow_suffixes=False)
    gh_tag = partial(get_github_release_latest_tag, session, skip_releases=True)

    return {
        # The argument names here cannot conflict with a wrapping function.
        # f(arg):: std.native('f', arg) will fail if it's defined here as 'f': (('arg',), ...).
        'githubLatestActionTag': (('o', 'r'), lambda o, r: _sync_wrap(gh_action, o, r)),
        'githubLatestReleaseTag': (
            ('o', 'r'), lambda o, r: _sync_wrap(get_github_release_latest_tag, session, o, r)),
        'githubLatestTag': (('o', 'r'), lambda o, r: _sync_wrap(gh_tag, o, r)),
        'isodate': ((), lambda: datetime.now(tz=timezone.utc).isoformat()[:10]),
        'latestNpmPackageVersion': (
            ('p',), lambda p: _sync_wrap(get_npm_latest_package_version, session, p)),
        'latestPypiPackageVersion': (
            ('p',), lambda p: _sync_wrap(get_pypi_latest_package_version, session, p)),
        'latestYarnVersion': ((), lambda: _sync_wrap(get_latest_yarn_version, session)),
        'year': ((), lambda: datetime.now(tz=timezone.utc).year),
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
        Optional HTTP session for callbacks.

    Returns
    -------
    str
        The evaluated Jsonnet output as a string.
    """
    native_callbacks = _make_native_callbacks(session)
    return await anyio.to_thread.run_sync(
        lambda: _jsonnet.evaluate_file(str(file),
                                       jpathdir=list(jpathdir),
                                       native_callbacks=native_callbacks,
                                       tla_codes={'settings': merged_settings}))


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
        Optional HTTP session for callbacks.
    file : Path | None
        The path to the Jsonnet file to evaluate (defaults to ``project.jsonnet`` in the library).
    output_dir : Path | None
        The directory to output generated files to (defaults to the current directory).
    """
    log.debug('Evaluating Jsonnet. Please be patient.')
    if output_dir:
        await anyio.Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_dir = output_dir or Path()
    filename: str
    for filename, content in json.loads(await evaluate_jsonnet_file(
            jpathdir, file or (lib_path / 'project.jsonnet'), merged_settings, session)).items():
        output_file = anyio.Path(output_dir / filename)
        await output_file.parent.mkdir(parents=True, exist_ok=True)
        await output_file.write_text(f'{content.strip()}\n')
        log.debug('Wrote `%s`.', output_file)


async def evaluate_merged_settings(jpathdir: Sequence[str],
                                   lib_path: Path,
                                   settings: str,
                                   session: AsyncSession | None = None,
                                   *,
                                   user_defaults: bool = False) -> tuple[str, Settings]:
    """
    Evaluate the merged settings using Jsonnet.

    Parameters
    ----------
    jpathdir : Sequence[str]
        The Jsonnet library search path.
    lib_path : Path
        The path to the Jsonnet library.
    settings : str
        The settings to merge with defaults and user defaults.
    session : AsyncSession | None
        Optional HTTP session for callbacks.
    user_defaults : bool
        Whether to include user defaults from the user preferences directory.

    Returns
    -------
    tuple[str, Settings]
        The evaluated merged settings as a JSON string and as a Settings object.

    Raises
    ------
    FileNotFoundError
        If the ``user_defaults`` option is given but no user defaults file exists.
    """
    user_defaults_jsonnet = platformdirs.user_config_path('wiswa') / 'defaults.jsonnet'
    if user_defaults and not user_defaults_jsonnet.exists():
        msg = ('The user_defaults=True option was given, but no defaults.jsonnet file exists in'
               f' the user preferences directory (path: {user_defaults_jsonnet}).')
        raise FileNotFoundError(msg)
    native_callbacks = _make_native_callbacks(session)
    defaults_path = anyio.Path(
        lib_path.resolve(strict=True) / 'defaults.libsonnet')  # noqa: ASYNC240
    defaults_text = await defaults_path.read_text()
    user_defaults_text = (await anyio.Path(user_defaults_jsonnet).read_text()
                          if user_defaults else '{}')
    s = await anyio.to_thread.run_sync(lambda: _jsonnet.evaluate_snippet(
        '',
        'function(defaults, user_defaults, settings) defaults + user_defaults + settings',
        jpathdir=list(jpathdir),
        native_callbacks=native_callbacks,
        tla_codes={
            'defaults': defaults_text,
            'settings': settings,
            'user_defaults': user_defaults_text,
        }))
    return s, (json.loads(s) | {'_readme_existed': await anyio.Path('README.md').exists()})


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
        Optional HTTP session for callbacks.

    Returns
    -------
    dict[str, Any]
        The resolved default settings.
    """
    native_callbacks = _make_native_callbacks(session)
    defaults_path = anyio.Path(
        lib_path.resolve(strict=True) / 'defaults.libsonnet')  # noqa: ASYNC240
    defaults_text = await defaults_path.read_text()
    s = await anyio.to_thread.run_sync(lambda: _jsonnet.evaluate_snippet(
        '',
        'function(defaults, user_defaults, settings) defaults + user_defaults + settings',
        jpathdir=list(jpathdir),
        native_callbacks=native_callbacks,
        tla_codes={
            'defaults': defaults_text,
            'settings': '{}',
            'user_defaults': '{}',
        }))
    result: dict[str, Any] = json.loads(s)
    return result
