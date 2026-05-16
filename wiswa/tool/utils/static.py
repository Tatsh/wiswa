"""Copy static files from the Wiswa package into the generated project."""
from __future__ import annotations

from functools import partial
from pathlib import Path
from shutil import copyfile
from typing import TYPE_CHECKING, Any
import json
import logging

from anyio.to_thread import run_sync
import anyio

from .path import non_empty_file_exists, primary_module_to_path, remove_empty_dirs

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiswa.tool.typing import Settings

__all__ = ('copy_static_files',)

log = logging.getLogger(__name__)


def _claude_rule_pairs(module_path: Path, project_type: str, *,
                       stubs_only: bool) -> list[tuple[Path, Path]]:
    base = module_path / 'static/claude/rules'
    pairs: list[tuple[Path, Path]] = [(Path(f'.claude/rules/{name}.md'), base / f'{name}.md')
                                      for name in ('json-yaml', 'toml-ini')]
    match project_type:
        case 'c++':
            pairs.append((Path('.claude/rules/cpp.md'), base / 'cpp.md'))
        case 'python':
            if not stubs_only:
                pairs.append((Path('.claude/rules/python-tests.md'), base / 'python-tests.md'))
        case _:
            pass
    return pairs


async def _sync_file_pairs(pairs: Sequence[tuple[Path, Path]], dir_path: Path, stop_at: Path, *,
                           wanted: bool) -> None:
    if wanted:
        await anyio.Path(dir_path).mkdir(parents=True, exist_ok=True)
        for dest, src in pairs:
            await run_sync(partial(copyfile, src, dest))
            log.debug('Wrote `%s`.', dest)
    else:
        for dest, src in pairs:
            aio_dest = anyio.Path(dest)
            if (await aio_dest.exists() and src.exists() and await
                    aio_dest.read_text(encoding='utf-8') == src.read_text(encoding='utf-8')):
                await aio_dest.unlink()
                log.debug('Removed `%s` (matched would-be content).', dest)
        await remove_empty_dirs(dir_path, stop_at)


async def _sync_json_file(path: Path,
                          content: Mapping[str, Any],
                          stop_at: Path | None = None,
                          *,
                          wanted: bool) -> None:
    stop_at = stop_at or Path()
    expected_text = f'{json.dumps(content, indent=2)}\n'
    aio_path = anyio.Path(path)
    if wanted:
        await aio_path.parent.mkdir(parents=True, exist_ok=True)
        await aio_path.write_text(expected_text, encoding='utf-8')
        log.debug('Wrote `%s`.', path)
    else:
        if await aio_path.exists() and await aio_path.read_text(encoding='utf-8') == expected_text:
            await aio_path.unlink()
            log.debug('Removed `%s` (matched would-be content).', path)
        await remove_empty_dirs(path.parent, stop_at)


async def copy_static_files_python(settings: Settings, module_path: Path) -> None:
    """Copy static files to the current directory."""
    async def copy_file(filename: str) -> None:
        static_path = module_path / 'static' / filename
        module_path_str = primary_module_to_path(settings['primary_module_qualified'])
        output_file = Path(module_path_str) / filename
        if await non_empty_file_exists(output_file):
            log.debug('Skipping `%s`.', output_file)
            return
        await anyio.Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        await run_sync(partial(copyfile, static_path, output_file))
        log.debug('Wrote `%s`.', output_file)

    if settings['stubs_only']:
        return
    if settings['want_main'] and not settings['has_multiple_entry_points']:
        await copy_file('__main__.py')
        await copy_file('main.py')


async def copy_static_files(settings: Settings, module_path: Path) -> None:
    """
    Copy static files to the current directory.

    Parameters
    ----------
    settings : Settings
        Project settings.
    module_path : Path
        Path to the :py:mod:`wiswa` package directory.
    """
    rule_pairs = _claude_rule_pairs(module_path,
                                    settings['project_type'],
                                    stubs_only=settings['stubs_only'])
    await _sync_file_pairs(rule_pairs,
                           Path('.claude/rules'),
                           Path('.claude'),
                           wanted=settings['want_ai'])
    await _sync_json_file(Path('.claude/settings.json'),
                          settings['claude_settings_local'],
                          wanted=settings['want_ai'])
    match settings['project_type']:
        case 'python':
            await copy_static_files_python(settings, module_path)
        case _:
            if settings['project_type'] != 'c++':
                log.warning('No static files to copy for project type `%s`.',
                            settings['project_type'])
