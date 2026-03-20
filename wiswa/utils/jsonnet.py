"""Jsonnet evaluation."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
import json
import logging

import _jsonnet  # noqa: PLC2701
import platformdirs

from .versions import (
    get_github_release_latest_tag,
    get_latest_yarn_version,
    get_npm_latest_package_version,
    get_pypi_latest_package_version,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from wiswa.typing import Settings

__all__ = ('evaluate_jsonnet_file', 'evaluate_jsonnet_project', 'evaluate_merged_settings')

log = logging.getLogger(__name__)

NATIVE_CALLBACKS: dict[str, tuple[tuple[str, ...], Callable[..., Any]]] = {
    'githubLatestActionTag': (('owner', 'repo'), lambda owner, repo: get_github_release_latest_tag(
        owner, repo, actions=True, skip_releases=True, allow_suffixes=False)),
    'githubLatestReleaseTag': (('owner', 'repo'), get_github_release_latest_tag),
    'githubLatestTag': (
        ('owner', 'repo'),
        lambda owner, repo: get_github_release_latest_tag(owner, repo, skip_releases=True)),
    'isodate': ((), lambda: datetime.now(tz=timezone.utc).isoformat()[:10]),
    'latestNpmPackageVersion': (('package',), get_npm_latest_package_version),
    'latestPypiPackageVersion': (('package',), get_pypi_latest_package_version),
    'latestYarnVersion': ((), get_latest_yarn_version),
    'year': ((), lambda: datetime.now(tz=timezone.utc).year),
}
"""Native callbacks for Jsonnet evaluation."""


def evaluate_jsonnet_file(jpathdir: Sequence[str], file: Path, merged_settings: str) -> str:
    """Evaluate a Jsonnet file with the given settings."""
    return _jsonnet.evaluate_file(str(file),
                                  jpathdir=list(jpathdir),
                                  native_callbacks=NATIVE_CALLBACKS,
                                  tla_codes={'settings': merged_settings})


def evaluate_jsonnet_project(lib_path: Path,
                             jpathdir: Sequence[str],
                             merged_settings: str,
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
    file : Path | None
        The path to the Jsonnet file to evaluate (defaults to ``project.jsonnet`` in the library).
    output_dir : Path | None
        The directory to output generated files to (defaults to the current directory).
    """
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir or Path()
    filename: str
    for filename, content in json.loads(
            evaluate_jsonnet_file(jpathdir, file or (lib_path / 'project.jsonnet'),
                                  merged_settings)).items():
        output_file = output_dir / filename
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(f'{content.strip()}\n')
        log.debug('Wrote `%s`.', output_file)


def evaluate_merged_settings(jpathdir: Sequence[str],
                             lib_path: Path,
                             settings: str,
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
    s = _jsonnet.evaluate_snippet(
        '',
        'function(defaults, user_defaults, settings) defaults + user_defaults + settings',
        jpathdir=list(jpathdir),
        native_callbacks=NATIVE_CALLBACKS,
        tla_codes={
            'defaults': (lib_path.resolve(strict=True) / 'defaults.libjsonnet').read_text(),
            'settings': settings,
            'user_defaults': user_defaults_jsonnet.read_text() if user_defaults else '{}',
        })
    return s, (json.loads(s) | {'_readme_existed': Path('README.md').exists()})
