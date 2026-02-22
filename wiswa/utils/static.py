"""Copying static files into the project."""
from __future__ import annotations

from pathlib import Path
from shutil import copyfile
from typing import TYPE_CHECKING, Any
import json
import logging

from .path import non_empty_file_exists, primary_module_to_path, remove_empty_dirs

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiswa.typing import Settings

__all__ = ('copy_static_files',)

log = logging.getLogger(__name__)


def _cursor_and_instruction_pairs(
    module_path: Path,
    project_type: str,
    *,
    stubs_only: bool,
) -> tuple[list[tuple[Path, Path]], list[tuple[Path, Path]]]:
    cursor_pairs: list[tuple[Path, Path]] = []
    instruction_pairs: list[tuple[Path, Path]] = []
    for name in ('json-yaml', 'markdown', 'toml-ini'):
        cursor_pairs.append((
            Path(f'.cursor/rules/{name}.mdc'),
            module_path / 'static/.cursor/rules' / f'{name}.mdc',
        ))
        instruction_pairs.append((
            Path(f'.github/instructions/{name}.instructions.md'),
            module_path / 'static/.github/instructions' / f'{name}.instructions.md',
        ))
    match project_type:
        case 'c++':
            instruction_pairs.append((
                Path('.github/instructions/cpp.instructions.md'),
                module_path / 'static/.github/instructions/cpp.instructions.md',
            ))
            cursor_pairs.append((
                Path('.cursor/rules/cpp.mdc'),
                module_path / 'static/.cursor/rules/cpp.mdc',
            ))
        case 'python':
            if not stubs_only:
                cursor_pairs.extend([
                    (Path('.cursor/rules/python.mdc'),
                     module_path / 'static/.cursor/rules/python.mdc'),
                    (Path('.cursor/rules/python-tests.mdc'),
                     module_path / 'static/.cursor/rules/python-tests.mdc'),
                ])
                instruction_pairs.extend([
                    (Path('.github/instructions/python.instructions.md'),
                     module_path / 'static/.github/instructions/python.instructions.md'),
                    (Path('.github/instructions/python-tests.instructions.md'),
                     module_path / 'static/.github/instructions/python-tests.instructions.md'),
                ])
        case _:
            pass
    return cursor_pairs, instruction_pairs


def _sync_file_pairs(
    pairs: Sequence[tuple[Path, Path]],
    dir_path: Path,
    stop_at: Path,
    *,
    wanted: bool,
) -> None:
    if wanted:
        dir_path.mkdir(parents=True, exist_ok=True)
        for dest, src in pairs:
            copyfile(src, dest)
            log.debug('Wrote `%s`.', dest)
    else:
        for dest, src in pairs:
            if dest.exists() and src.exists() and dest.read_text() == src.read_text():
                dest.unlink()
                log.debug('Removed `%s` (matched would-be content).', dest)
        remove_empty_dirs(dir_path, stop_at)
        root = dir_path
        while root.parent not in {stop_at, root}:
            root = root.parent
        if root.exists() and root.is_dir() and not any(root.iterdir()):
            root.rmdir()


def _sync_json_file(path: Path,
                    content: Mapping[str, Any],
                    stop_at: Path | None = None,
                    *,
                    wanted: bool) -> None:
    stop_at = stop_at or Path()
    expected_text = f'{json.dumps(content, indent=2)}\n'
    if wanted:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected_text, encoding='utf-8')
        log.debug('Wrote `%s`.', path)
    else:
        if path.exists() and path.read_text(encoding='utf-8') == expected_text:
            path.unlink()
            log.debug('Removed `%s` (matched would-be content).', path)
        remove_empty_dirs(path.parent, stop_at)


def copy_static_files_python(settings: Settings, module_path: Path) -> None:
    """Copy static files to the current directory."""
    def copy_file(filename: str) -> None:
        static_path = module_path / 'static' / filename
        module_path_str = primary_module_to_path(settings['primary_module'])
        output_file = Path(module_path_str) / filename
        if non_empty_file_exists(output_file):
            log.debug('Skipping `%s`.', output_file)
            return
        output_file.parent.mkdir(parents=True, exist_ok=True)
        copyfile(static_path, output_file)
        log.debug('Wrote `%s`.', output_file)

    if settings['stubs_only']:
        return
    if settings['want_main'] and not settings['has_multiple_entry_points']:
        copy_file('__main__.py')
        copy_file('main.py')


def copy_static_files(settings: Settings, module_path: Path) -> None:
    """Copy static files to the current directory."""
    cursor_pairs, instruction_pairs = _cursor_and_instruction_pairs(
        module_path,
        settings['project_type'],
        stubs_only=settings['stubs_only'],
    )
    _sync_file_pairs(cursor_pairs, Path('.cursor/rules'), Path(), wanted=settings['want_cursor'])
    _sync_file_pairs(instruction_pairs,
                     Path('.github/instructions'),
                     Path('.github'),
                     wanted=settings['want_copilot'])
    _sync_json_file(Path('.claude/settings.local.json'),
                    settings['claude_settings_local'],
                    wanted=settings['want_claude'])
    match settings['project_type']:
        case 'python':
            copy_static_files_python(settings, module_path)
        case _:
            if settings['project_type'] != 'c++':
                log.warning('No static files to copy for project type `%s`.',
                            settings['project_type'])
