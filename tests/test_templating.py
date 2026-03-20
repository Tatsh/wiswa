from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

from wiswa.utils.templating import write_templated_files
import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


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
        'want_tests': False,
        'want_docs': False,
        'using_github': False,
        'supported_platforms': 'all',
        'package_manager': 'uv',
        'private': False,
        'using_django': False,
    }
    base.update(overrides)
    return base


def _mock_template_env(mocker: MockerFixture,
                       tmp_path: Path) -> tuple[MagicMock, MagicMock, list[str]]:
    mock_resolve = MagicMock()
    written_files: list[str] = []

    def mock_write(template: object, output: object, **kwargs: object) -> None:
        written_files.append(str(output))

    mocker.patch('wiswa.utils.templating._template_env',
                 return_value=(MagicMock(), tmp_path, mock_resolve, mock_write))
    mocker.patch('pathlib.Path.unlink')
    return mock_resolve, MagicMock(), written_files


def test_write_templated_files_claude_agents_wanted(tmp_path: Path, mocker: MockerFixture) -> None:
    agents_dir = tmp_path / '.claude/agents'
    agents_dir.mkdir(parents=True)
    (agents_dir / 'my-agent.md.j2').write_text('agent content')
    (agents_dir / 'readme.txt').write_text('not a template')
    skills_dir = tmp_path / '.claude/skills/ci'
    skills_dir.mkdir(parents=True)
    (skills_dir / 'skill.md.j2').write_text('skill content')
    (tmp_path / 'CLAUDE.md.j2').write_text('claude')
    (tmp_path / 'AGENTS.md.j2').write_text('agents')
    _, _, written_files = _mock_template_env(mocker, tmp_path)
    mocker.patch('wiswa.utils.templating._should_overwrite_contributing', return_value=False)
    mocker.patch('wiswa.utils.templating._write_templated_files_python')
    settings = cast('Any', _make_settings(want_claude_agents=True, want_copilot=False))
    write_templated_files(tmp_path, settings)
    assert '.claude/agents/my-agent.md' in written_files
    assert '.claude/skills/ci/skill.md' in written_files
    assert 'CLAUDE.md' in written_files
    assert 'AGENTS.md' in written_files
    assert not any('readme.txt' in f for f in written_files)


def test_write_templated_files_claude_agents_not_wanted(tmp_path: Path,
                                                        mocker: MockerFixture) -> None:
    _, _, written_files = _mock_template_env(mocker, tmp_path)
    mocker.patch('wiswa.utils.templating._should_overwrite_contributing', return_value=False)
    mocker.patch('wiswa.utils.templating._write_templated_files_python')
    settings = cast('Any', _make_settings(want_claude_agents=False, want_copilot=False))
    write_templated_files(tmp_path, settings)
    assert 'CLAUDE.md' not in written_files
    assert 'AGENTS.md' not in written_files
    assert not any('.claude/agents' in f for f in written_files)


def test_write_templated_files_claude_no_agents_dir(tmp_path: Path, mocker: MockerFixture) -> None:
    (tmp_path / 'CLAUDE.md.j2').write_text('claude')
    (tmp_path / 'AGENTS.md.j2').write_text('agents')
    _, _, written_files = _mock_template_env(mocker, tmp_path)
    mocker.patch('wiswa.utils.templating._should_overwrite_contributing', return_value=False)
    mocker.patch('wiswa.utils.templating._write_templated_files_python')
    settings = cast('Any', _make_settings(want_claude_agents=True, want_copilot=False))
    write_templated_files(tmp_path, settings)
    assert 'CLAUDE.md' in written_files
    assert 'AGENTS.md' in written_files
    agent_files = [f for f in written_files if '.claude/agents' in f]
    assert agent_files == []


def test_write_templated_files_copilot_wanted(tmp_path: Path, mocker: MockerFixture) -> None:
    _, _, written_files = _mock_template_env(mocker, tmp_path)
    mocker.patch('wiswa.utils.templating._should_overwrite_contributing', return_value=False)
    mocker.patch('wiswa.utils.templating._write_templated_files_python')
    settings = cast('Any', _make_settings(want_copilot=True, want_claude_agents=False))
    write_templated_files(tmp_path, settings)
    assert any('general.instructions.md' in f for f in written_files)


def test_write_templated_files_copilot_not_wanted_removes_matching(tmp_path: Path,
                                                                   mocker: MockerFixture,
                                                                   monkeypatch: Any) -> None:
    monkeypatch.chdir(tmp_path)
    instructions_dir = tmp_path / '.github/instructions'
    instructions_dir.mkdir(parents=True)
    general_file = instructions_dir / 'general.instructions.md'
    mock_template = MagicMock()
    mock_template.render.return_value = 'expected content'
    general_file.write_text('expected content\n')
    mock_resolve = MagicMock(return_value=mock_template)
    mock_write_file = MagicMock()
    mocker.patch('wiswa.utils.templating._template_env',
                 return_value=(MagicMock(), tmp_path, mock_resolve, mock_write_file))
    mocker.patch('wiswa.utils.templating._should_overwrite_contributing', return_value=False)
    mocker.patch('wiswa.utils.templating._write_templated_files_python')
    settings = cast('Any', _make_settings(want_copilot=False, want_claude_agents=False))
    write_templated_files(tmp_path, settings)
    assert not general_file.exists()


@pytest.mark.parametrize('project_type', ['c++', 'c', 'lua', 'typescript'])
def test_write_templated_files_dispatches_project_types(project_type: str, tmp_path: Path,
                                                        mocker: MockerFixture) -> None:
    _, _, _ = _mock_template_env(mocker, tmp_path)
    mocker.patch('wiswa.utils.templating._should_overwrite_contributing', return_value=False)
    mock_c_cpp = mocker.patch('wiswa.utils.templating._write_templated_files_c_cpp')
    mock_cpp = mocker.patch('wiswa.utils.templating._write_templated_files_cpp')
    mock_c = mocker.patch('wiswa.utils.templating._write_templated_files_c')
    mock_lua = mocker.patch('wiswa.utils.templating._write_template_files_lua')
    mock_ts = mocker.patch('wiswa.utils.templating._write_templated_files_typescript')
    settings = cast(
        'Any',
        _make_settings(project_type=project_type, want_copilot=False, want_claude_agents=False))
    write_templated_files(tmp_path, settings)
    match project_type:
        case 'c++':
            mock_c_cpp.assert_called_once()
            mock_cpp.assert_called_once()
        case 'c':
            mock_c_cpp.assert_called_once()
            mock_c.assert_called_once()
        case 'lua':
            mock_lua.assert_called_once()
        case 'typescript':
            mock_ts.assert_called_once()


def test_write_templated_files_unknown_type_warns(tmp_path: Path, mocker: MockerFixture) -> None:
    _, _, _ = _mock_template_env(mocker, tmp_path)
    mocker.patch('wiswa.utils.templating._should_overwrite_contributing', return_value=False)
    mock_log = mocker.patch('wiswa.utils.templating.log')
    settings = cast(
        'Any', _make_settings(project_type='generic', want_copilot=False, want_claude_agents=False))
    write_templated_files(tmp_path, settings)
    mock_log.warning.assert_called_once()


def test_write_templated_files_contributing_overwrite_uv_with_poetry(tmp_path: Path,
                                                                     mocker: MockerFixture,
                                                                     monkeypatch: Any) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'CONTRIBUTING.md').write_text('Install with Poetry\n')
    _, _, written_files = _mock_template_env(mocker, tmp_path)
    mocker.patch('wiswa.utils.templating._write_templated_files_python')
    settings = cast(
        'Any', _make_settings(package_manager='uv', want_copilot=False, want_claude_agents=False))
    write_templated_files(tmp_path, settings)
    contrib_writes = [f for f in written_files if 'CONTRIBUTING' in f]
    assert len(contrib_writes) == 1


def test_write_templated_files_contributing_no_overwrite_matching(tmp_path: Path,
                                                                  mocker: MockerFixture,
                                                                  monkeypatch: Any) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'CONTRIBUTING.md').write_text('Use uv to manage deps\n')
    _, _, written_files = _mock_template_env(mocker, tmp_path)
    mocker.patch('wiswa.utils.templating._write_templated_files_python')
    settings = cast(
        'Any', _make_settings(package_manager='uv', want_copilot=False, want_claude_agents=False))
    write_templated_files(tmp_path, settings)
    contrib_writes = [f for f in written_files if 'CONTRIBUTING' in f]
    assert len(contrib_writes) == 1
