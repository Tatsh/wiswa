"""Tests for static file copying."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from wiswa.utils.static import copy_static_files, copy_static_files_python

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture
    import pytest


def _make_settings(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        'project_type': 'python',
        'stubs_only': False,
        'want_ai': True,
        'claude_settings_local': {},
        'want_main': False,
        'has_multiple_entry_points': False,
        'primary_module': 'mymod',
        'primary_module_qualified': 'mymod',
    }
    base |= overrides
    return base


def _setup_module_path(tmp_path: Path) -> Path:
    """Set up a fake ``module_path`` with static files for ``copy_static_files``."""
    module_path = tmp_path / 'wiswa_pkg'
    rules_dir = module_path / 'static/claude/rules'
    rules_dir.mkdir(parents=True, exist_ok=True)
    for name in ('json-yaml', 'toml-ini'):
        (rules_dir / f'{name}.md').write_text(f'{name} rules content')
    for name in ('python', 'python-tests'):
        (rules_dir / f'{name}.md').write_text(f'{name} rules')
    return module_path


async def test_copy_static_files_creates_claude_rules_and_settings(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    settings = cast('Any', _make_settings(claude_settings_local={'x': 1}))
    await copy_static_files(settings, module_path)
    assert (tmp_path / '.claude/rules/json-yaml.md').exists()
    assert (tmp_path / '.claude/rules/python.md').exists()
    assert (tmp_path / '.claude/settings.local.json').exists()
    assert '"x": 1' in (tmp_path / '.claude/settings.local.json').read_text()


async def test_copy_static_files_stubs_only_skips_python_rules(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    settings = cast('Any', _make_settings(stubs_only=True))
    await copy_static_files(settings, module_path)
    assert (tmp_path / '.claude/rules/json-yaml.md').exists()
    assert not (tmp_path / '.claude/rules/python.md').exists()
    assert not (tmp_path / '.claude/rules/python-tests.md').exists()


async def test_copy_static_files_not_wanted_ai_removes_matching_rule(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    rules_dir = tmp_path / '.claude/rules'
    rules_dir.mkdir(parents=True)
    (rules_dir / 'json-yaml.md').write_text('json-yaml rules content')
    settings = cast('Any', _make_settings(want_ai=False))
    await copy_static_files(settings, module_path)
    assert not (rules_dir / 'json-yaml.md').exists()


async def test_copy_static_files_not_wanted_ai_keeps_different_rule(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    rules_dir = tmp_path / '.claude/rules'
    rules_dir.mkdir(parents=True)
    (rules_dir / 'json-yaml.md').write_text('custom user content')
    settings = cast('Any', _make_settings(want_ai=False))
    await copy_static_files(settings, module_path)
    assert (rules_dir / 'json-yaml.md').read_text() == 'custom user content'


async def test_copy_static_files_claude_json_written_when_wanted(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    settings = cast('Any', _make_settings(want_ai=True, claude_settings_local={'key': 'val'}))
    await copy_static_files(settings, module_path)
    assert (tmp_path / '.claude/settings.local.json').exists()
    assert '"key": "val"' in (tmp_path / '.claude/settings.local.json').read_text()
    assert (tmp_path / '.claude/settings.local.json.dist').exists()
    assert '"key": "val"' in (tmp_path / '.claude/settings.local.json.dist').read_text()


async def test_copy_static_files_cpp_project_type(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    cpp_rule = module_path / 'static/claude/rules/cpp.md'
    cpp_rule.write_text('cpp rules')
    settings = cast('Any', _make_settings(project_type='c++'))
    await copy_static_files(settings, module_path)
    assert (tmp_path / '.claude/rules/cpp.md').exists()


async def test_copy_static_files_unknown_project_type_warns(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch,
                                                            mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    mock_log = mocker.patch('wiswa.utils.static.log')
    settings = cast('Any', _make_settings(project_type='generic'))
    await copy_static_files(settings, module_path)
    mock_log.warning.assert_called_once()


async def test_copy_static_files_python_stubs_only(tmp_path: Path) -> None:
    settings = cast('Any', _make_settings(stubs_only=True))
    await copy_static_files_python(settings, tmp_path)


async def test_copy_static_files_python_copies_main_files(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    static_dir = tmp_path / 'pkg/static'
    static_dir.mkdir(parents=True)
    (static_dir / '__main__.py').write_text('# main entry')
    (static_dir / 'main.py').write_text('# main')
    settings = cast(
        'Any',
        _make_settings(
            want_main=True,
            has_multiple_entry_points=False,
            stubs_only=False,
            primary_module='mymod',
        ),
    )
    await copy_static_files_python(settings, tmp_path / 'pkg')
    assert (tmp_path / 'mymod/__main__.py').exists()
    assert (tmp_path / 'mymod/main.py').exists()


async def test_copy_static_files_python_skips_existing_non_empty(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    static_dir = tmp_path / 'pkg/static'
    static_dir.mkdir(parents=True)
    (static_dir / '__main__.py').write_text('# main entry')
    (static_dir / 'main.py').write_text('# main')
    (tmp_path / 'mymod').mkdir()
    (tmp_path / 'mymod/__main__.py').write_text('existing content')
    settings = cast(
        'Any',
        _make_settings(
            want_main=True,
            has_multiple_entry_points=False,
            stubs_only=False,
            primary_module='mymod',
        ),
    )
    await copy_static_files_python(settings, tmp_path / 'pkg')
    assert (tmp_path / 'mymod/__main__.py').read_text() == 'existing content'


async def test_copy_static_files_not_wanted_ai_removes_rules_and_trims_empty_dirs(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    rules_dir = tmp_path / '.claude/rules'
    rules_dir.mkdir(parents=True)
    for name in ('json-yaml', 'toml-ini'):
        (rules_dir / f'{name}.md').write_text(f'{name} rules content')
    settings = cast('Any', _make_settings(want_ai=False, project_type='generic'))
    await copy_static_files(settings, module_path)
    assert not (tmp_path / '.claude').exists()


async def test_copy_static_files_claude_not_wanted_removes_matching_json(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    import json

    claude_dir = tmp_path / '.claude'
    claude_dir.mkdir(parents=True)
    content = {'key': 'val'}
    (claude_dir / 'settings.local.json').write_text(f'{json.dumps(content, indent=2)}\n',
                                                    encoding='utf-8')
    (claude_dir / 'settings.local.json.dist').write_text(f'{json.dumps(content, indent=2)}\n',
                                                         encoding='utf-8')
    settings = cast('Any', _make_settings(want_ai=False, claude_settings_local={'key': 'val'}))
    await copy_static_files(settings, module_path)
    assert not (claude_dir / 'settings.local.json').exists()
    assert not (claude_dir / 'settings.local.json.dist').exists()


async def test_copy_static_files_claude_not_wanted_keeps_different_json(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    claude_dir = tmp_path / '.claude'
    claude_dir.mkdir(parents=True)
    (claude_dir / 'settings.local.json').write_text('{"custom": "content"}\n', encoding='utf-8')
    settings = cast('Any', _make_settings(want_ai=False, claude_settings_local={'key': 'val'}))
    await copy_static_files(settings, module_path)
    assert (claude_dir / 'settings.local.json').exists()
