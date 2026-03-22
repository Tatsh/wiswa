"""Tests for path utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiswa.utils.path import non_empty_file_exists, primary_module_to_path, remove_empty_dirs
import pytest

if TYPE_CHECKING:
    from pathlib import Path


async def test_remove_empty_dirs_single(tmp_path: Path) -> None:
    d = tmp_path / 'a/b/c'
    d.mkdir(parents=True)
    await remove_empty_dirs(d, stop_at=tmp_path)
    assert not (tmp_path / 'a').exists()


async def test_remove_empty_dirs_stops_at_boundary(tmp_path: Path) -> None:
    d = tmp_path / 'a/b/c'
    d.mkdir(parents=True)
    await remove_empty_dirs(d, stop_at=tmp_path / 'a')
    assert (tmp_path / 'a').exists()
    assert not (tmp_path / 'a/b').exists()


async def test_remove_empty_dirs_stops_at_non_empty(tmp_path: Path) -> None:
    d = tmp_path / 'a/b/c'
    d.mkdir(parents=True)
    (tmp_path / 'a/file.txt').write_text('content')
    await remove_empty_dirs(d, stop_at=tmp_path)
    assert (tmp_path / 'a').exists()
    assert not (tmp_path / 'a/b').exists()


async def test_remove_empty_dirs_default_stop_at(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    d = tmp_path / 'x/y'
    d.mkdir(parents=True)
    await remove_empty_dirs(d)
    assert not (tmp_path / 'x').exists()


async def test_remove_empty_dirs_nonexistent(tmp_path: Path) -> None:
    d = tmp_path / 'nonexistent'
    await remove_empty_dirs(d, stop_at=tmp_path)


def test_primary_module_to_path_simple() -> None:
    assert primary_module_to_path('mymod') == 'mymod'


def test_primary_module_to_path_dotted() -> None:
    assert primary_module_to_path('parent.child') == 'parent/child'


def test_primary_module_to_path_traversal_raises() -> None:
    with pytest.raises(ValueError, match='path traversal'):
        primary_module_to_path('..')


def test_primary_module_to_path_empty_segment_raises() -> None:
    with pytest.raises(ValueError, match='path traversal'):
        primary_module_to_path('a..b')


async def test_non_empty_file_exists_true(tmp_path: Path) -> None:
    f = tmp_path / 'file.txt'
    f.write_text('content')
    assert await non_empty_file_exists(f) is True


async def test_non_empty_file_exists_empty(tmp_path: Path) -> None:
    f = tmp_path / 'file.txt'
    f.write_text('')
    assert await non_empty_file_exists(f) is False


async def test_non_empty_file_exists_whitespace_only(tmp_path: Path) -> None:
    f = tmp_path / 'file.txt'
    f.write_text('   \n  ')
    assert await non_empty_file_exists(f) is False


async def test_non_empty_file_exists_missing(tmp_path: Path) -> None:
    f = tmp_path / 'missing.txt'
    assert await non_empty_file_exists(f) is False
