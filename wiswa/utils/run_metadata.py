"""Write Wiswa run metadata into the generated ``package.json``."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from shlex import join as shlex_join
from typing import TYPE_CHECKING
import asyncio
import importlib.metadata
import json
import logging
import os
import re
import sys

import anyio

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ('get_wiswa_version_or_sha', 'write_wiswa_run_metadata')

log = logging.getLogger(__name__)

_WISWA_PACKAGE_NAME = 'wiswa'
_WISWA_SHORT_SHA_LENGTH = 7
_WISWA_PYPROJECT_NAME_RE = re.compile(r'(?m)^name\s*=\s*[\'"]wiswa[\'"]\s*$')


def _resolve_git_dir(candidate: Path) -> Path | None:
    """
    Resolve ``.git`` to a directory, following the ``gitdir:`` pointer used by worktrees.

    Parameters
    ----------
    candidate : Path
        The ``.git`` path to inspect (either a directory or a ``gitdir:`` pointer file).

    Returns
    -------
    Path | None
        The actual git directory, or ``None`` if it cannot be resolved.
    """
    if candidate.is_dir():
        return candidate
    if not candidate.is_file():
        return None
    text = candidate.read_text(encoding='utf-8').strip()
    if not text.startswith('gitdir:'):
        return None
    pointer = text.removeprefix('gitdir:').strip()
    target = (candidate.parent / pointer).resolve()
    return target if target.is_dir() else None


def _read_head_sha(git_dir: Path) -> str | None:
    head_file = git_dir / 'HEAD'
    if not head_file.is_file():
        return None
    head = head_file.read_text(encoding='utf-8').strip()
    if not head.startswith('ref:'):
        return head or None
    ref = head.removeprefix('ref:').strip()
    ref_path = git_dir / ref
    if ref_path.is_file():
        return ref_path.read_text(encoding='utf-8').strip() or None
    packed = git_dir / 'packed-refs'
    if packed.is_file():
        for line in packed.read_text(encoding='utf-8').splitlines():
            if line.endswith(f' {ref}'):
                return line.split(' ', 1)[0]
    return None


def _is_wiswa_repository_root(root: Path) -> bool:
    pyproject = root / 'pyproject.toml'
    if not pyproject.is_file():
        return False
    return bool(_WISWA_PYPROJECT_NAME_RE.search(pyproject.read_text(encoding='utf-8')))


async def _repository_is_dirty(repo_root: Path) -> bool:
    """
    Return whether *repo_root* has uncommitted changes per ``git status --porcelain``.

    Parameters
    ----------
    repo_root : Path
        Working tree root.

    Returns
    -------
    bool
        :py:data:`True` when the working tree has tracked or untracked changes.
        :py:data:`False` when the tree is clean or the status command cannot run.
    """
    try:
        proc = await asyncio.create_subprocess_exec('git',
                                                    '-C',
                                                    str(repo_root),
                                                    'status',
                                                    '--porcelain',
                                                    stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)
    except (FileNotFoundError, OSError):
        return False
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return False
    return bool(stdout.strip())


def _wiswa_short_sha_and_root() -> tuple[str, Path] | None:
    """
    Locate the wiswa source checkout and return its short SHA and root directory.

    The search walks upward from the installed ``wiswa`` package directory looking for a
    ``.git`` entry whose repository root identifies itself as the wiswa project.

    Returns
    -------
    tuple[str, Path] | None
        Pair of seven-character commit SHA and repository root, or :py:data:`None` when
        no wiswa checkout is found or the SHA cannot be read.
    """
    import wiswa  # noqa: PLC0415
    pkg_path = Path(wiswa.__file__).resolve().parent
    for parent in pkg_path.parents:
        candidate = parent / '.git'
        git_dir = _resolve_git_dir(candidate)
        if git_dir is None:
            continue
        if not _is_wiswa_repository_root(parent):
            return None
        sha = _read_head_sha(git_dir)
        if sha is None:
            return None
        return sha[:_WISWA_SHORT_SHA_LENGTH], parent
    return None


async def get_wiswa_version_or_sha() -> str:
    """
    Return the wiswa identifier to embed in generated ``package.json`` files.

    Prefers the short SHA when wiswa runs from a source checkout (so the generated
    project records the exact commit that produced its files), suffixing it with
    ``-dirty`` when the working tree has uncommitted changes; otherwise falls back to
    the installed distribution version reported by :py:func:`importlib.metadata.version`.

    Returns
    -------
    str
        Seven-character commit SHA (optionally followed by ``-dirty``) when available,
        else the installed package version.
    """
    if (found := _wiswa_short_sha_and_root()) is not None:
        short, root = found
        if await _repository_is_dirty(root):
            return f'{short}-dirty'
        return short
    try:
        return importlib.metadata.version(_WISWA_PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        import wiswa  # noqa: PLC0415
        return wiswa.__version__


def _utc_iso_timestamp() -> str:
    return datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _invocation_command_line() -> str:
    argv = list(sys.argv)
    if not argv:
        return ''
    return shlex_join([Path(argv[0]).name, *argv[1:]])


async def write_wiswa_run_metadata(*, on_command: Callable[[str], None] | None = None) -> None:
    """
    Append ``_wiswa`` metadata at the end of ``package.json`` and reformat with Prettier.

    Writes ``_wiswa.version`` (the wiswa version or short SHA from
    :py:func:`get_wiswa_version_or_sha`), ``_wiswa.lastRun`` (a UTC ISO 8601 timestamp
    accurate to the second), and ``_wiswa.commandLine`` (the invocation rendered with
    only the ``argv[0]`` basename, shell-quoted via :py:func:`shlex.join`). Re-emits
    ``package.json`` without sorting keys so the ``_wiswa`` block remains the last
    property, then runs ``yarn prettier --write package.json`` to produce a canonical
    file. Skips silently when ``package.json`` is missing.

    Parameters
    ----------
    on_command : Callable[[str], None] | None
        Optional callback invoked with the Prettier command string before it runs.
    """
    package_json = anyio.Path('package.json')
    if not await package_json.is_file():
        log.debug('No `package.json` found; skipping Wiswa run metadata write.')
        return
    raw = await package_json.read_text(encoding='utf-8')
    data = json.loads(raw)
    if not isinstance(data, dict):
        log.debug('`package.json` is not a JSON object; skipping Wiswa run metadata write.')
        return
    data.pop('_wiswa', None)
    data['_wiswa'] = {
        'commandLine': _invocation_command_line(),
        'lastRun': _utc_iso_timestamp(),
        'version': await get_wiswa_version_or_sha(),
    }
    await package_json.write_text(f'{json.dumps(data, indent=2)}\n', encoding='utf-8')
    cmd = ('yarn', 'prettier', '--write', '--ignore-unknown', 'package.json')
    cmd_str = ' '.join(cmd)
    log.debug('Running command: `%s`.', cmd_str)
    if on_command is not None:
        on_command(cmd_str)
    yarn_env = os.environ | {'COREPACK_ENABLE_DOWNLOAD_PROMPT': '0'}
    proc = await asyncio.create_subprocess_exec(*cmd,
                                                env=yarn_env,
                                                stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    await proc.communicate()
    if proc.returncode != 0:
        log.debug('Prettier on `package.json` exited with status %d.', proc.returncode)
