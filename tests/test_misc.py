"""Tests for miscellaneous utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from wiswa.utils.misc import create_py_typed_files

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_create_py_typed_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = cast('Any', {'primary_module': 'mymod'})
    create_py_typed_files(settings)
    assert (tmp_path / 'mymod/py.typed').exists()


def test_create_py_typed_files_nested_module(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = cast('Any', {'primary_module': 'parent.child'})
    create_py_typed_files(settings)
    assert (tmp_path / 'parent/child/py.typed').exists()


def test_create_py_typed_files_existing_dir(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'mymod').mkdir()
    settings = cast('Any', {'primary_module': 'mymod'})
    create_py_typed_files(settings)
    assert (tmp_path / 'mymod/py.typed').exists()
