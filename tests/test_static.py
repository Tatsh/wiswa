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
        'want_cursor': True,
        'want_copilot': True,
        'want_claude': True,
        'want_claude_agents': False,
        'claude_settings_local': {},
        'want_main': False,
        'has_multiple_entry_points': False,
        'primary_module': 'mymod',
    }
    base |= overrides
    return base


def _setup_module_path(tmp_path: Path) -> Path:
    """Set up a fake ``module_path`` with static files for ``copy_static_files``."""
    module_path = tmp_path / 'wiswa_pkg'
    for name in ('json-yaml', 'markdown', 'toml-ini'):
        cursor_dir = module_path / 'static/.cursor/rules'
        cursor_dir.mkdir(parents=True, exist_ok=True)
        (cursor_dir / f'{name}.mdc').write_text(f'{name} cursor content')
        inst_dir = module_path / 'static/.github/instructions'
        inst_dir.mkdir(parents=True, exist_ok=True)
        (inst_dir / f'{name}.instructions.md').write_text(f'{name} instruction content')
    for name in ('python', 'python-tests'):
        (module_path / 'static/.cursor/rules' / f'{name}.mdc').write_text(f'{name} cursor')
        (module_path / 'static/.github/instructions' /
         f'{name}.instructions.md').write_text(f'{name} instruction')
    return module_path


def test_copy_static_files_creates_cursor_and_instruction_files(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    settings = cast('Any', _make_settings())
    copy_static_files(settings, module_path)
    assert (tmp_path / '.cursor/rules/json-yaml.mdc').exists()
    assert (tmp_path / '.cursor/rules/python.mdc').exists()
    assert (tmp_path / '.github/instructions/json-yaml.instructions.md').exists()
    assert (tmp_path / '.github/instructions/python.instructions.md').exists()


def test_copy_static_files_stubs_only_skips_python_rules(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    settings = cast('Any', _make_settings(stubs_only=True))
    copy_static_files(settings, module_path)
    assert (tmp_path / '.cursor/rules/json-yaml.mdc').exists()
    assert not (tmp_path / '.cursor/rules/python.mdc').exists()
    assert not (tmp_path / '.cursor/rules/python-tests.mdc').exists()


def test_copy_static_files_not_wanted_cursor_removes_matching(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    cursor_dir = tmp_path / '.cursor/rules'
    cursor_dir.mkdir(parents=True)
    (cursor_dir / 'json-yaml.mdc').write_text('json-yaml cursor content')
    settings = cast('Any', _make_settings(want_cursor=False))
    copy_static_files(settings, module_path)
    assert not (cursor_dir / 'json-yaml.mdc').exists()


def test_copy_static_files_not_wanted_cursor_keeps_different(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    cursor_dir = tmp_path / '.cursor/rules'
    cursor_dir.mkdir(parents=True)
    (cursor_dir / 'json-yaml.mdc').write_text('custom user content')
    settings = cast('Any', _make_settings(want_cursor=False))
    copy_static_files(settings, module_path)
    assert (cursor_dir / 'json-yaml.mdc').read_text() == 'custom user content'


def test_copy_static_files_claude_agents_wanted(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    agents_dir = module_path / 'static/.claude/agents'
    agents_dir.mkdir(parents=True)
    (agents_dir / 'qa-fixer.md').write_text('qa agent')
    (agents_dir / 'copy-editor.md').write_text('copy agent')
    settings = cast('Any', _make_settings(want_claude_agents=True))
    copy_static_files(settings, module_path)
    assert (tmp_path / '.claude/agents/qa-fixer.md').read_text() == 'qa agent'
    assert (tmp_path / '.claude/agents/copy-editor.md').read_text() == 'copy agent'


def test_copy_static_files_claude_agents_not_wanted(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    agents_dir = module_path / 'static/.claude/agents'
    agents_dir.mkdir(parents=True)
    (agents_dir / 'qa-fixer.md').write_text('qa agent')
    settings = cast('Any', _make_settings(want_claude_agents=False))
    copy_static_files(settings, module_path)
    assert not (tmp_path / '.claude/agents/qa-fixer.md').exists()


def test_copy_static_files_claude_agents_not_wanted_removes_matching(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    agents_dir = module_path / 'static/.claude/agents'
    agents_dir.mkdir(parents=True)
    (agents_dir / 'qa-fixer.md').write_text('qa agent')
    out_agents = tmp_path / '.claude/agents'
    out_agents.mkdir(parents=True)
    (out_agents / 'qa-fixer.md').write_text('qa agent')
    settings = cast('Any', _make_settings(want_claude_agents=False))
    copy_static_files(settings, module_path)
    assert not (out_agents / 'qa-fixer.md').exists()


def test_copy_static_files_claude_json_written_when_wanted(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    settings = cast('Any', _make_settings(want_claude=True, claude_settings_local={'key': 'val'}))
    copy_static_files(settings, module_path)
    assert (tmp_path / '.claude/settings.local.json').exists()
    assert '"key": "val"' in (tmp_path / '.claude/settings.local.json').read_text()
    assert (tmp_path / '.claude/settings.local.json.dist').exists()
    assert '"key": "val"' in (tmp_path / '.claude/settings.local.json.dist').read_text()


def test_copy_static_files_cpp_project_type(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    cpp_cursor = module_path / 'static/.cursor/rules/cpp.mdc'
    cpp_cursor.write_text('cpp cursor')
    cpp_inst = module_path / 'static/.github/instructions/cpp.instructions.md'
    cpp_inst.write_text('cpp instruction')
    settings = cast('Any', _make_settings(project_type='c++'))
    copy_static_files(settings, module_path)
    assert (tmp_path / '.cursor/rules/cpp.mdc').exists()
    assert (tmp_path / '.github/instructions/cpp.instructions.md').exists()


def test_copy_static_files_unknown_project_type_warns(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch,
                                                      mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    module_path = _setup_module_path(tmp_path)
    mock_log = mocker.patch('wiswa.utils.static.log')
    settings = cast('Any', _make_settings(project_type='generic'))
    copy_static_files(settings, module_path)
    mock_log.warning.assert_called_once()


def test_copy_static_files_python_stubs_only(tmp_path: Path) -> None:
    settings = cast('Any', _make_settings(stubs_only=True))
    copy_static_files_python(settings, tmp_path)


def test_copy_static_files_python_copies_main_files(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    static_dir = tmp_path / 'pkg/static'
    static_dir.mkdir(parents=True)
    (static_dir / '__main__.py').write_text('# main entry')
    (static_dir / 'main.py').write_text('# main')
    settings = cast(
        'Any',
        _make_settings(want_main=True,
                       has_multiple_entry_points=False,
                       stubs_only=False,
                       primary_module='mymod'))
    copy_static_files_python(settings, tmp_path / 'pkg')
    assert (tmp_path / 'mymod/__main__.py').exists()
    assert (tmp_path / 'mymod/main.py').exists()


def test_copy_static_files_python_skips_existing_non_empty(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    static_dir = tmp_path / 'pkg/static'
    static_dir.mkdir(parents=True)
    (static_dir / '__main__.py').write_text('# main entry')
    (static_dir / 'main.py').write_text('# main')
    (tmp_path / 'mymod').mkdir()
    (tmp_path / 'mymod/__main__.py').write_text('existing content')
    settings = cast(
        'Any',
        _make_settings(want_main=True,
                       has_multiple_entry_points=False,
                       stubs_only=False,
                       primary_module='mymod'))
    copy_static_files_python(settings, tmp_path / 'pkg')
    assert (tmp_path / 'mymod/__main__.py').read_text() == 'existing content'
