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

from wiswa.vcs.git import changed_files, diff, restore_from_head
import anyio

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ('get_wiswa_version_or_sha', 'maybe_revert_package_json_if_only_wiswa_metadata_changed',
           'package_json_diff_changes_only_wiswa_metadata', 'write_wiswa_run_metadata')

log = logging.getLogger(__name__)

_WISWA_PACKAGE_NAME = 'wiswa'
_WISWA_SHORT_SHA_LENGTH = 7
_WISWA_PYPROJECT_NAME_RE = re.compile(r'(?m)^name\s*=\s*[\'"]wiswa[\'"]\s*$')
_WISWA_METADATA_KEY = '_wiswa'
_RE_PACKAGE_JSON_TOP_LEVEL_KEY = re.compile(r'^  "([^"]+)"\s*:')
"""Match a top-level key line in the 2-space-indented, sorted ``package.json``.

:meta hide-value:
"""


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
    import wiswa.tool  # ruff:ignore[import-outside-top-level]
    pkg_path = Path(wiswa.tool.__file__).resolve().parent
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
        import wiswa.tool  # ruff:ignore[import-outside-top-level]
        return wiswa.tool.__version__


def _utc_iso_timestamp() -> str:
    return datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _invocation_command_line() -> str:
    argv = list(sys.argv)
    if not argv:
        return ''
    return shlex_join([Path(argv[0]).name, *argv[1:]])


async def _run_prettier_on_package_json(on_command: Callable[[str], None] | None) -> None:
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


def package_json_diff_changes_only_wiswa_metadata(diff_text: str) -> bool:
    """
    Return whether a ``package.json`` unified diff touches only the ``_wiswa`` block.

    The ``_wiswa`` object holds Wiswa run metadata (``commandLine``, ``lastRun``, and
    ``version``) that :py:func:`write_wiswa_run_metadata` rewrites on every run, so a diff
    confined to it is incidental churn. Nesting is tracked by watching lines indented exactly
    two spaces (the top-level keys of the sorted, 2-space-indented file): an added or removed
    line counts only while the enclosing top-level key is ``_wiswa``. A top-level key that is
    itself added or removed, or any change under a different key (including the top-level
    ``version``, which shares a name with ``_wiswa.version``), fails the check.

    Parameters
    ----------
    diff_text : str
        Unified diff text from comparing ``package.json`` revisions.

    Returns
    -------
    bool
        ``True`` when every ``+``/``-`` line lies within the ``_wiswa`` object.
    """
    if not diff_text.strip():
        return False
    top_level_key: str | None = None
    saw_wiswa_change = False
    for line in diff_text.splitlines():
        if line.startswith('@@'):
            top_level_key = None
            continue
        if not line or line.startswith(('diff --git ', 'index ', '--- ', '+++ ', '\\')):
            continue
        marker, content = line[0], line[1:]
        if (match := _RE_PACKAGE_JSON_TOP_LEVEL_KEY.match(content)) is not None:
            if marker in '+-':
                return False
            top_level_key = match.group(1)
            continue
        if marker == ' ':
            continue
        if marker in '+-':
            if top_level_key != _WISWA_METADATA_KEY:
                return False
            saw_wiswa_change = True
            continue
        return False
    return saw_wiswa_change


async def maybe_revert_package_json_if_only_wiswa_metadata_changed() -> None:
    """
    Restore ``package.json`` from ``HEAD`` when only its ``_wiswa`` block drifted.

    Mirrors :py:func:`wiswa.tool.utils.postprocess.maybe_revert_uv_lock_if_only_lockfile_changed`
    in intent, but applies the predicate even when ``package.json`` is the only changed file:
    ``package.json`` carries real project configuration that a regen may legitimately update,
    so it is restored only when :py:func:`package_json_diff_changes_only_wiswa_metadata`
    accepts the diff. A run that genuinely changes scripts, dependencies, or any other key is
    left untouched.
    """
    if 'package.json' not in await changed_files():
        return
    if not package_json_diff_changes_only_wiswa_metadata(await diff('package.json')):
        return
    if await restore_from_head('package.json'):
        log.debug('Restored package.json from HEAD.')


async def write_wiswa_run_metadata(*,
                                   enabled: bool = True,
                                   on_command: Callable[[str], None] | None = None) -> None:
    """
    Append or remove the ``_wiswa`` metadata block in ``package.json``.

    When *enabled* is :py:data:`True`, writes ``_wiswa.commandLine`` (the invocation rendered
    with only the ``argv[0]`` basename, shell-quoted via :py:func:`shlex.join`),
    ``_wiswa.lastRun`` (a UTC ISO 8601 timestamp accurate to the second), and
    ``_wiswa.version`` (the wiswa version or short SHA from
    :py:func:`get_wiswa_version_or_sha`). Re-emits ``package.json`` without sorting keys so
    the ``_wiswa`` block remains the last property, then runs
    ``yarn prettier --write package.json`` to produce a canonical file. Finally,
    :py:func:`maybe_revert_package_json_if_only_wiswa_metadata_changed` restores the file from
    ``HEAD`` when the metadata refresh is the only drift, so incidental ``_wiswa`` churn does
    not show up as a change.

    When *enabled* is :py:data:`False`, removes any existing ``_wiswa`` block, rewriting and
    reformatting only when the file actually changes. Skips silently when ``package.json``
    is missing.

    Parameters
    ----------
    enabled : bool
        Whether to write the ``_wiswa`` block. When :py:data:`False`, an existing block is
        deleted on the next run.
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
    if not enabled:
        if '_wiswa' not in data:
            return
        del data['_wiswa']
        await package_json.write_text(f'{json.dumps(data, indent=2)}\n', encoding='utf-8')
        await _run_prettier_on_package_json(on_command)
        return
    data.pop('_wiswa', None)
    data['_wiswa'] = {
        'commandLine': _invocation_command_line(),
        'lastRun': _utc_iso_timestamp(),
        'version': await get_wiswa_version_or_sha(),
    }
    await package_json.write_text(f'{json.dumps(data, indent=2)}\n', encoding='utf-8')
    await _run_prettier_on_package_json(on_command)
    await maybe_revert_package_json_if_only_wiswa_metadata_changed()
