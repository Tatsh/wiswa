"""Path and file helpers."""
from __future__ import annotations

from pathlib import Path

__all__ = ('non_empty_file_exists', 'primary_module_to_path', 'remove_empty_dirs')


def non_empty_file_exists(output_file: Path) -> bool:
    """Check if a file exists and is not empty."""
    return output_file.exists() and len(output_file.read_text(encoding='utf-8').strip()) != 0


def primary_module_to_path(primary_module: str) -> str:
    """Convert a dotted module name to a filesystem path, validating against path traversal.

    Raises
    ------
    ValueError
        If the module name contains path traversal or empty segments.
    """
    path_str = primary_module.replace('.', '/')
    parts = path_str.split('/')
    for part in parts:
        if part in {'', '.', '..'}:
            msg = f'Invalid primary_module (path traversal or empty segment): {primary_module!r}'
            raise ValueError(msg)
    return path_str


def remove_empty_dirs(path: Path, stop_at: Path | None = None) -> None:
    """Remove directory and parents while empty, until ``stop_at``."""
    stop_at = stop_at or Path()
    while path.exists() and path.is_dir() and path != stop_at:
        if any(path.iterdir()):
            break
        path.rmdir()
        path = path.parent
