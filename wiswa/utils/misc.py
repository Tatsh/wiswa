"""Create py.typed marker files."""
from __future__ import annotations

from typing import TYPE_CHECKING
import logging

import anyio

from .path import primary_module_to_path

if TYPE_CHECKING:
    from wiswa.typing import Settings

__all__ = ('create_py_typed_files',)

log = logging.getLogger(__name__)


async def create_py_typed_files(settings: Settings) -> None:
    """Create ``py.typed`` in the primary module directory (same location as its __init__.py)."""
    path = anyio.Path(primary_module_to_path(settings['primary_module']))
    await path.mkdir(parents=True, exist_ok=True)
    target = path / 'py.typed'
    await target.touch()
    log.debug('Touched `%s`.', target)
