"""Path and file helpers."""
from __future__ import annotations

from pathlib import Path

import anyio

__all__ = ('non_empty_file_exists', 'primary_module_to_path', 'remove_empty_dirs')


async def non_empty_file_exists(output_file: Path) -> bool:
    """
    Check if a file exists and is not empty.

    Parameters
    ----------
    output_file : Path
        The file to check.

    Returns
    -------
    bool
        :py:data:`True` if the file exists and contains non-whitespace content.
    """
    aio_path = anyio.Path(output_file)
    return await aio_path.exists() and len(
        (await aio_path.read_text(encoding='utf-8')).strip()) != 0


def primary_module_to_path(primary_module: str) -> str:
    """
    Convert a dotted module name to a filesystem path, validating against path traversal.

    Parameters
    ----------
    primary_module : str
        A dotted module name (e.g. ``'wiswa.utils'``).

    Returns
    -------
    str
        The corresponding filesystem path with dots replaced by ``/``.

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


async def remove_empty_dirs(path: Path, stop_at: Path | None = None) -> None:
    """
    Remove directory and parents while empty, stopping at ``stop_at``.

    Parameters
    ----------
    path : Path
        The directory to start removing from.
    stop_at : Path | None
        The directory at which to stop removing parents.
    """
    stop_at = stop_at or Path()
    aio_path = anyio.Path(path)
    aio_stop = anyio.Path(stop_at)
    while await aio_path.exists() and await aio_path.is_dir() and aio_path != aio_stop:
        if [p async for p in aio_path.iterdir()]:
            break
        await aio_path.rmdir()
        aio_path = aio_path.parent
