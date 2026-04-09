"""Tests for miscellaneous utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from wiswa.utils.misc import create_py_typed_files

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


async def test_create_py_typed_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = cast('Any', {'primary_module': 'mymod', 'primary_module_qualified': 'mymod'})
    await create_py_typed_files(settings)
    assert (tmp_path / 'mymod/py.typed').exists()


async def test_create_py_typed_files_nested_module(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = cast('Any', {
        'primary_module': 'parent.child',
        'primary_module_qualified': 'parent.child'
    })
    await create_py_typed_files(settings)
    assert (tmp_path / 'parent/child/py.typed').exists()


async def test_create_py_typed_files_existing_dir(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'mymod').mkdir()
    settings = cast('Any', {'primary_module': 'mymod', 'primary_module_qualified': 'mymod'})
    await create_py_typed_files(settings)
    assert (tmp_path / 'mymod/py.typed').exists()


async def test_create_py_typed_files_implicit_namespace_qualified_pkg(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = cast('Any', {
        'primary_module': 'vendor',
        'primary_module_qualified': 'vendor.product.service'
    })
    await create_py_typed_files(settings)
    assert (tmp_path / 'vendor/product/service/py.typed').exists()
