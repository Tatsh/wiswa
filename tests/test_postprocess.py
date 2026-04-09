"""Tests for post-processing utilities."""

from __future__ import annotations

from shutil import which
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock
import asyncio
import logging
import os
import subprocess

from wiswa.utils.postprocess import (
    apply_python_pyproject_manifest_edits,
    maybe_revert_uv_lock_if_only_lockfile_changed,
    post_process_steps,
    uv_lock_diff_changes_only_exclude_newer,
)
import niquests
import pytest
import tomlkit

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def _make_settings(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        'project_type': 'python',
        'package_manager': 'uv',
        'want_tests': True,
        'want_docs': True,
        'want_codeql': True,
        'want_man': False,
        'want_yapf': True,
        'private': False,
        'stubs_only': False,
        'using_github': True,
        'using_gitlab': False,
        'using_django': False,
        'project_name': 'myproject',
        'pypi_project_name': 'myproject',
        'primary_module': 'mymod',
        'primary_module_qualified': 'mymod',
        'version': '0.0.1',
        'default_branch': 'master',
        'repository_uri': 'https://github.com/testuser/myproject',
        'github': {
            'username': 'testuser',
            'immutable_releases': True,
        },
        'social': {},
        'keywords': [],
        'documentation_uri': 'https://myproject.readthedocs.io',
        'package_json': {
            'dependencies': {},
            'devDependencies': {},
        },
        'python_deps': {
            'main': {},
        },
        'pyproject': {
            'project': {
                'dependencies': [],
            },
        },
        'export_requirements': {
            'enabled': False,
            'format': 'requirements.txt',
            'output_filename': 'requirements.txt',
            'all_extras': False,
            'all_groups': False,
            'all_packages': False,
            'extra': [],
            'frozen': False,
            'group': [],
            'locked': False,
            'no_annotate': False,
            'no_default_groups': False,
            'no_dev': False,
            'no_editable': False,
            'no_emit_local': False,
            'no_emit_package': [],
            'no_emit_project': True,
            'no_emit_workspace': False,
            'no_extra': [],
            'no_group': [],
            'no_hashes': False,
            'no_header': False,
            'only_dev': False,
            'only_group': [],
            'package': [],
            'prune': [],
            'script': '',
            'with_hashes': True,
        },
        'vscode': {
            'launch': None,
        },
        'regenerate_yarn_lock': False,
        '_readme_existed': False,
        '_has_established_pytest_modules': False,
        'want_ai': True,
        'using_beads': False,
    }
    return base | overrides


async def test_apply_python_pyproject_manifest_edits_prunes_empty_tool_tables(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.commitizen]\n'
        'name = "cz_path"\n'
        'version_files = ["README.md"]\n'
        '[tool.coverage]\nrun = {}\n'
        '[tool.pytest]\nini_options = {}\n'
        '[tool.yapf]\nbased_on_style = "pep8"\n'
        '[tool.yapfignore]\nignore_patterns = []\n'
        '[tool.ruff.lint]\nignore = []\n'
        '[tool.poetry]\n'
        '[dependency-groups]\n'
        'docs = []\ntests = []\ndev = []\n',
        encoding='utf-8',
    )
    (tmp_path / 'package.json').write_text(
        '{"scripts": {"check-formatting": "x", "format": "y"}}',
        encoding='utf-8',
    )
    settings = cast('Any', _make_settings(want_yapf=False))
    await apply_python_pyproject_manifest_edits(settings)
    root = tomlkit.loads((tmp_path / 'pyproject.toml').read_text(encoding='utf-8')).unwrap()
    assert 'poetry' not in root.get('tool', {})
    assert root['tool']


def _setup_python_project(tmp_path: Path) -> None:
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text(
        '[tool.commitizen]\n'
        'version_files = ["wiswa/__init__.py:^__version__"]\n'
        '[tool.coverage]\nrun = {}\n'
        '[tool.pytest]\nini_options = {}\n'
        '[tool.yapf]\nbased_on_style = "pep8"\n'
        '[tool.yapfignore]\nignore_patterns = []\n'
        '[tool.ruff.lint]\nignore = []\n'
        '[dependency-groups]\n'
        'docs = []\ntests = []\ndev = []\n',
        encoding='utf-8',
    )
    package_json = tmp_path / 'package.json'
    package_json.write_text(
        '{"scripts": {"check-formatting": "old", "format": "old"}}',
        encoding='utf-8',
    )


def _mock_subprocess(mocker: MockerFixture) -> AsyncMock:
    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b'', b''))
    mock_process.returncode = 0
    mocker.patch('wiswa.utils.postprocess.asyncio.create_subprocess_exec',
                 return_value=mock_process)
    return mock_process


async def test_post_process_steps_python_uv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                            mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / 'poetry.lock').write_text('lock')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings())
    await post_process_steps(settings)
    assert not (tmp_path / 'poetry.lock').exists()


async def test_post_process_steps_removes_legacy_wiswa_ai_files(tmp_path: Path,
                                                                monkeypatch: pytest.MonkeyPatch,
                                                                mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    legacy_cursor = tmp_path / '.cursor' / 'rules' / 'general.mdc'
    legacy_cursor.parent.mkdir(parents=True)
    legacy_cursor.write_text('legacy')
    legacy_gh = tmp_path / '.github' / 'instructions' / 'python.instructions.md'
    legacy_gh.parent.mkdir(parents=True)
    legacy_gh.write_text('legacy')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings())
    await post_process_steps(settings)
    assert not legacy_cursor.exists()
    assert not legacy_gh.exists()


async def test_post_process_steps_python_no_tests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                  mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_foo.py').write_text('pass')
    (tmp_path / '.github/workflows').mkdir(parents=True)
    (tmp_path / '.github/workflows/tests.yml').write_text('test')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(want_tests=False))
    await post_process_steps(settings)
    assert not (tmp_path / 'tests').exists()
    assert not (tmp_path / '.github/workflows/tests.yml').exists()


async def test_post_process_steps_python_no_tests_removes_launch_json(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / '.vscode').mkdir()
    (tmp_path / '.vscode/launch.json').write_text('{}')
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(
            want_tests=False,
            vscode={
                'launch': {
                    'configurations': [{
                        'name': 'Run tests'
                    }],
                },
            },
        ),
    )
    await post_process_steps(settings)
    assert not (tmp_path / '.vscode/launch.json').exists()


async def test_post_process_steps_python_no_docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                 mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs/conf.py').write_text('pass')
    (tmp_path / '.readthedocs.yaml').write_text('test')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(want_docs=False))
    await post_process_steps(settings)
    assert not (tmp_path / 'docs').exists()
    assert not (tmp_path / '.readthedocs.yaml').exists()


async def test_post_process_steps_python_no_codeql(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                   mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / '.github/workflows').mkdir(parents=True)
    (tmp_path / '.github/workflows/codeql.yml').write_text('test')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(want_codeql=False))
    await post_process_steps(settings)
    assert not (tmp_path / '.github/workflows/codeql.yml').exists()


async def test_post_process_steps_python_want_man_with_man_dir(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch,
                                                               mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    man_dir = tmp_path / 'man'
    man_dir.mkdir()
    (man_dir / 'mymod.1').write_text('.TH mymod 1')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(want_man=True))
    await post_process_steps(settings)


async def test_post_process_steps_python_want_man_without_man_dir(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch,
                                                                  mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(want_man=True, primary_module='mymod'))
    await post_process_steps(settings)


async def test_post_process_steps_python_no_yapf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                 mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(want_yapf=False))
    await post_process_steps(settings)
    import json

    pkg = json.loads((tmp_path / 'package.json').read_text(encoding='utf-8'))
    assert 'ruff format' in pkg['scripts']['check-formatting']
    assert 'ruff format' in pkg['scripts']['format']


async def test_post_process_steps_python_poetry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text(
        '[tool.commitizen]\n'
        'version_files = ["wiswa/__init__.py:^__version__"]\n'
        '[tool.coverage]\nrun = {}\n'
        '[tool.pytest]\nini_options = {}\n'
        '[tool.yapf]\nbased_on_style = "pep8"\n'
        '[tool.yapfignore]\nignore_patterns = []\n'
        '[tool.ruff.lint]\nignore = []\n'
        '[tool.poetry.group.docs.dependencies]\nsphinx = "^7"\n'
        '[tool.poetry.group.tests.dependencies]\npytest = "^8"\n',
        encoding='utf-8',
    )
    (tmp_path / 'package.json').write_text(
        '{"scripts": {"check-formatting": "old", "format": "old"}}',
        encoding='utf-8',
    )
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(package_manager='poetry'))
    await post_process_steps(settings)


async def test_post_process_steps_python_poetry_no_docs_no_tests(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch,
                                                                 mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text(
        '[tool.commitizen]\n'
        'version_files = ["wiswa/__init__.py:^__version__"]\n'
        '[tool.coverage]\nrun = {}\n'
        '[tool.pytest]\nini_options = {}\n'
        '[tool.yapf]\nbased_on_style = "pep8"\n'
        '[tool.yapfignore]\nignore_patterns = []\n'
        '[tool.ruff.lint]\nignore = []\n'
        '[tool.poetry.group.docs.dependencies]\nsphinx = "^7"\n'
        '[tool.poetry.group.tests.dependencies]\npytest = "^8"\n',
        encoding='utf-8',
    )
    (tmp_path / 'package.json').write_text(
        '{"scripts": {"check-formatting": "old", "format": "old"}}',
        encoding='utf-8',
    )
    _mock_subprocess(mocker)
    settings = cast('Any',
                    _make_settings(package_manager='poetry', want_docs=False, want_tests=False))
    await post_process_steps(settings)


async def test_post_process_steps_unknown_type_warns(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{}', encoding='utf-8')
    _mock_subprocess(mocker)
    mock_log = mocker.patch('wiswa.utils.postprocess.log')
    settings = cast('Any', _make_settings(project_type='generic', _readme_existed=False))
    await post_process_steps(settings)
    mock_log.warning.assert_called_once()


async def test_post_process_steps_checks_readme_badges(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch,
                                                       mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# My Project\n\n[![old badge](http://example.com)]\n\nContent here.\n',
                      encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(_readme_existed=True))
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert '# My Project' in content


async def test_post_process_steps_readme_not_existed(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(_readme_existed=False))
    await post_process_steps(settings)


async def test_post_process_steps_readme_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                 mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(_readme_existed=True))
    await post_process_steps(settings)


async def test_post_process_steps_updates_changelog_reference_urls(tmp_path: Path,
                                                                   monkeypatch: pytest.MonkeyPatch,
                                                                   mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / 'poetry.lock').write_text('lock')
    changelog = tmp_path / 'CHANGELOG.md'
    changelog.write_text(
        '# Changelog\n\nThe format is based on [Keep a Changelog]'
        '(https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning]'
        '(https://semver.org/spec/v1.2.3.html).\n',
        encoding='utf-8',
    )
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings())
    await post_process_steps(settings)
    body = changelog.read_text(encoding='utf-8')
    assert 'https://keepachangelog.com/en/1.1.1/' in body
    assert 'https://semver.org/spec/v2.0.0.html' in body
    assert 'keepachangelog.com/en/1.0.0' not in body
    assert 'semver.org/spec/v1.2.3.html' not in body


async def test_post_process_steps_changelog_urls_resolve_from_github(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / 'poetry.lock').write_text('lock')
    changelog = tmp_path / 'CHANGELOG.md'
    changelog.write_text(
        '# Changelog\n\nThe format is based on [Keep a Changelog]'
        '(https://keepachangelog.com/en/0.3.0/), and this project adheres to [Semantic Versioning]'
        '(https://semver.org/spec/v0.0.0.html).\n',
        encoding='utf-8',
    )
    _mock_subprocess(mocker)
    mocker.patch(
        'wiswa.utils.postprocess.get_github_release_latest_tag',
        new_callable=AsyncMock,
        side_effect=['v1.1.1', '3.0.0'],
    )
    settings = cast('Any', _make_settings())
    await post_process_steps(settings, session=mocker.MagicMock())
    body = changelog.read_text(encoding='utf-8')
    assert 'https://semver.org/spec/v3.0.0.html' in body
    assert 'https://keepachangelog.com/en/1.1.1/' in body


async def test_post_process_steps_changelog_keepachangelog_resolution_failure_fallback(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / 'poetry.lock').write_text('lock')
    changelog = tmp_path / 'CHANGELOG.md'
    changelog.write_text(
        '# Changelog\n\nThe format is based on [Keep a Changelog]'
        '(https://keepachangelog.com/en/0.3.0/), and this project adheres to [Semantic Versioning]'
        '(https://semver.org/spec/v0.0.0.html).\n',
        encoding='utf-8',
    )
    _mock_subprocess(mocker)
    mocker.patch(
        'wiswa.utils.postprocess.get_github_release_latest_tag',
        new_callable=AsyncMock,
        side_effect=[niquests.RequestException('simulated'), 'v2.0.0'],
    )
    settings = cast('Any', _make_settings())
    await post_process_steps(settings, session=mocker.MagicMock())
    body = changelog.read_text(encoding='utf-8')
    assert 'https://keepachangelog.com/en/1.1.1/' in body
    assert 'https://semver.org/spec/v2.0.0.html' in body


async def test_post_process_steps_changelog_semver_resolution_failure_fallback(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / 'poetry.lock').write_text('lock')
    changelog = tmp_path / 'CHANGELOG.md'
    changelog.write_text(
        '# Changelog\n\nThe format is based on [Keep a Changelog]'
        '(https://keepachangelog.com/en/0.3.0/), and this project adheres to [Semantic Versioning]'
        '(https://semver.org/spec/v0.0.0.html).\n',
        encoding='utf-8',
    )
    _mock_subprocess(mocker)
    mocker.patch(
        'wiswa.utils.postprocess.get_github_release_latest_tag',
        new_callable=AsyncMock,
        side_effect=['v1.1.1', niquests.RequestException('simulated')],
    )
    settings = cast('Any', _make_settings())
    await post_process_steps(settings, session=mocker.MagicMock())
    body = changelog.read_text(encoding='utf-8')
    assert 'https://keepachangelog.com/en/1.1.1/' in body
    assert 'https://semver.org/spec/v2.0.0.html' in body


async def test_post_process_steps_changelog_skips_rewrite_when_no_matching_links(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / 'poetry.lock').write_text('lock')
    changelog = tmp_path / 'CHANGELOG.md'
    original = '# Changelog\n\nNo boilerplate hyperlinks here.\n'
    changelog.write_text(original, encoding='utf-8')
    _mock_subprocess(mocker)
    mocker.patch(
        'wiswa.utils.postprocess.get_github_release_latest_tag',
        new_callable=AsyncMock,
        side_effect=['v9.9.9', 'v9.9.9'],
    )
    settings = cast('Any', _make_settings())
    await post_process_steps(settings, session=mocker.MagicMock())
    assert changelog.read_text(encoding='utf-8') == original


async def test_post_process_steps_python_no_tests_no_launch_vscode(tmp_path: Path,
                                                                   monkeypatch: pytest.MonkeyPatch,
                                                                   mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(
            want_tests=False,
            vscode={
                'launch': None,
            },
        ),
    )
    await post_process_steps(settings)


async def test_post_process_steps_python_no_tests_multiple_launch_configs(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / '.vscode').mkdir()
    (tmp_path / '.vscode/launch.json').write_text('{}')
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(
            want_tests=False,
            vscode={
                'launch': {
                    'configurations': [{
                        'name': 'Run tests'
                    }, {
                        'name': 'Debug'
                    }],
                },
            },
        ),
    )
    await post_process_steps(settings)
    assert (tmp_path / '.vscode/launch.json').exists()


async def test_post_process_steps_badges_c_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                   mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{}', encoding='utf-8')
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(project_type='c', _readme_existed=True))
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert '# Project' in content


async def test_post_process_steps_badges_cpp_project(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{}', encoding='utf-8')
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(project_type='c++', _readme_existed=True))
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'C++' in content or '# Project' in content


async def test_post_process_steps_badges_lua_project(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{}', encoding='utf-8')
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(project_type='lua', _readme_existed=True))
    await post_process_steps(settings)


async def test_post_process_steps_badges_xcode_project(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch,
                                                       mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{}', encoding='utf-8')
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(project_type='xcode', _readme_existed=True))
    await post_process_steps(settings)


async def test_post_process_steps_badges_github_with_tests_codeql(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch,
                                                                  mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(
            _readme_existed=True,
            want_tests=True,
            want_codeql=True,
            want_docs=True,
        ),
    )
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'Tests' in content
    assert 'CodeQL' in content
    assert 'Coverage' in content
    assert 'Documentation' in content


async def test_post_process_steps_badges_not_using_github(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch,
                                                          mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(_readme_existed=True, using_github=False))
    await post_process_steps(settings)


async def test_post_process_steps_badges_docs_github_pages(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch,
                                                           mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(
            _readme_existed=True,
            want_docs=True,
            project_type='c++',
            using_github=True,
        ),
    )
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'GitHub Pages' in content


async def test_post_process_steps_badges_python_poetry_django(tmp_path: Path,
                                                              monkeypatch: pytest.MonkeyPatch,
                                                              mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(
            _readme_existed=True,
            using_django=True,
            package_manager='poetry',
            python_deps={'main': {
                'numpy': '>=1',
            }},
        ),
    )
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'Django' in content
    assert 'Poetry' in content
    assert 'numpy' in content


async def test_post_process_steps_badges_private_project(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch,
                                                         mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(_readme_existed=True, private=True))
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'pypi' not in content.lower() or 'Downloads' not in content


async def test_post_process_steps_badges_typescript_project(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch,
                                                            mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{}', encoding='utf-8')
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(
            project_type='typescript',
            _readme_existed=True,
            package_json={
                'dependencies': {
                    'react': '^18',
                    'next': '^14',
                },
                'devDependencies': {
                    'eslint': '^8',
                    'jest': '^29',
                },
            },
        ),
    )
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'TypeScript' in content


async def test_post_process_steps_badges_dockerfile_exists(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch,
                                                           mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / 'Dockerfile').write_text('FROM python:3.13')
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(_readme_existed=True))
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'Docker' in content


async def test_post_process_steps_badges_cmake_c(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                 mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)')
    (tmp_path / 'package.json').write_text('{}', encoding='utf-8')
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(project_type='c', _readme_existed=True))
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'CMake' in content


async def test_post_process_steps_social_badges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(
            _readme_existed=True,
            keywords=['dotnet', 'ffmpeg', 'kde', 'qt', 'swift'],
            social={
                'bsky': 'testuser',
                'buymeacoffee': 'testuser',
                'calendly': {
                    'text': 'Book a call',
                    'uri': 'https://calendly.com/test',
                },
                'cashapp': '$testuser',
                'libera_irc': 'testuser',
                'mastodon': {
                    'id': '123456',
                    'domain': 'mastodon.social',
                },
                'patreon': 'testuser',
                'slashdot': 'testuser',
                'youtube': {
                    'text': 'My Channel',
                    'uri': 'https://youtube.com/@test',
                },
                'custom_badges': ['[![Custom](http://example.com)]'],
            },
        ),
    )
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert '@testuser' in content
    assert 'Buy Me' in content or 'buymeacoffee' in content


async def test_post_process_steps_social_badges_empty(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch,
                                                      mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(_readme_existed=True, social={}, keywords=[]))
    await post_process_steps(settings)


async def test_post_process_steps_python_uv_with_deps(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch,
                                                      mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(
            _readme_existed=True,
            python_deps={
                'main': {
                    'jinja': '>=3',
                    'pydantic': '>=2',
                    'sqlalchemy': '>=2',
                },
            },
            pyproject={
                'project': {
                    'dependencies': ['pandas>=2', 'scrapy>=2'],
                },
            },
        ),
    )
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'Jinja' in content or 'jinja' in content


async def test_post_process_steps_stubs_only_no_pydocstyle(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch,
                                                           mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(_readme_existed=True, stubs_only=True, want_tests=True))
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'pydocstyle' not in content


async def test_post_process_steps_on_command_callback(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch,
                                                      mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings())
    await post_process_steps(settings, on_command=commands.append)
    assert len(commands) > 0
    assert any('uv' in c for c in commands)


async def test_post_process_steps_uv_lock_has_upgrade_flag(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch,
                                                           mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings())
    await post_process_steps(settings, on_command=commands.append)
    lock_cmds = [c for c in commands if 'uv' in c and 'lock' in c]
    assert len(lock_cmds) == 1
    assert '--upgrade' in lock_cmds[0]


async def test_post_process_steps_uv_quiet_by_default(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch,
                                                      mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings())
    await post_process_steps(settings, on_command=commands.append)
    uv_cmds = [c for c in commands if c.startswith('uv')]
    assert all('--quiet' in c for c in uv_cmds)


async def test_post_process_steps_uv_no_quiet_in_debug(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch,
                                                       mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings())
    await post_process_steps(settings, debug=True, on_command=commands.append)
    uv_cmds = [c for c in commands if c.startswith('uv')]
    assert all('--quiet' not in c for c in uv_cmds)


async def test_post_process_steps_poetry_quiet_by_default(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch,
                                                          mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text(
        '[tool.commitizen]\n'
        'version_files = ["wiswa/__init__.py:^__version__"]\n'
        '[tool.coverage]\nrun = {}\n'
        '[tool.pytest]\nini_options = {}\n'
        '[tool.yapf]\nbased_on_style = "pep8"\n'
        '[tool.yapfignore]\nignore_patterns = []\n'
        '[tool.ruff.lint]\nignore = []\n'
        '[tool.poetry.group.docs.dependencies]\nsphinx = "^7"\n'
        '[tool.poetry.group.tests.dependencies]\npytest = "^8"\n',
        encoding='utf-8',
    )
    (tmp_path / 'package.json').write_text(
        '{"scripts": {"check-formatting": "old", "format": "old"}}',
        encoding='utf-8',
    )
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings(package_manager='poetry'))
    await post_process_steps(settings, on_command=commands.append)
    poetry_cmds = [c for c in commands if c.startswith('poetry')]
    assert len(poetry_cmds) >= 4
    assert all('--quiet' in c for c in poetry_cmds)


async def test_post_process_steps_poetry_no_quiet_in_debug(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch,
                                                           mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text(
        '[tool.commitizen]\n'
        'version_files = ["wiswa/__init__.py:^__version__"]\n'
        '[tool.coverage]\nrun = {}\n'
        '[tool.pytest]\nini_options = {}\n'
        '[tool.yapf]\nbased_on_style = "pep8"\n'
        '[tool.yapfignore]\nignore_patterns = []\n'
        '[tool.ruff.lint]\nignore = []\n'
        '[tool.poetry.group.docs.dependencies]\nsphinx = "^7"\n'
        '[tool.poetry.group.tests.dependencies]\npytest = "^8"\n',
        encoding='utf-8',
    )
    (tmp_path / 'package.json').write_text(
        '{"scripts": {"check-formatting": "old", "format": "old"}}',
        encoding='utf-8',
    )
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings(package_manager='poetry'))
    await post_process_steps(settings, debug=True, on_command=commands.append)
    poetry_cmds = [c for c in commands if c.startswith('poetry')]
    assert len(poetry_cmds) >= 4
    assert all('--quiet' not in c for c in poetry_cmds)


async def test_post_process_steps_subprocess_failure(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b'', b''))
    mock_proc.returncode = 1
    mocker.patch('wiswa.utils.postprocess.asyncio.create_subprocess_exec', return_value=mock_proc)
    settings = cast('Any', _make_settings())
    with pytest.raises(RuntimeError, match='non-zero exit status'):
        await post_process_steps(settings)


async def test_post_process_steps_custom_project_badges(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch,
                                                        mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(
            _readme_existed=True,
            custom_project_badges=[
                {
                    'anchor': '[![High Priority](http://example.com/high.svg)',
                    'href': 'http://example.com/high',
                    'priority': -1,
                },
                {
                    'anchor': '[![Low Priority](http://example.com/low.svg)',
                    'href': 'http://example.com/low',
                    'priority': 1,
                },
            ],
        ),
    )
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'High Priority' in content
    assert 'Low Priority' in content


async def test_post_process_steps_yarn_env_has_corepack_flag(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch,
                                                             mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b'', b''))
    mock_proc.returncode = 0
    mock_create = mocker.patch('wiswa.utils.postprocess.asyncio.create_subprocess_exec',
                               return_value=mock_proc)
    settings = cast('Any', _make_settings())
    await post_process_steps(settings)
    yarn_calls = [c for c in mock_create.call_args_list if c.args and c.args[0] == 'yarn']
    assert len(yarn_calls) == 4
    for call in yarn_calls:
        env = call.kwargs.get('env', {})
        assert env.get('COREPACK_ENABLE_DOWNLOAD_PROMPT') == '0'


async def test_post_process_steps_clang_format_expands_globs_and_literals(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{}', encoding='utf-8')
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'x.cpp').write_text('int x;\n', encoding='utf-8')
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b'', b''))
    mock_proc.returncode = 0
    mock_create = mocker.patch('wiswa.utils.postprocess.asyncio.create_subprocess_exec',
                               return_value=mock_proc)
    settings = cast(
        'Any',
        _make_settings(
            project_type='c',
            clang_format_args=('src/*.cpp src/x.cpp orphaned.hpp orphaned.hpp'),
            _readme_existed=False,
        ),
    )
    await post_process_steps(settings)
    clang = [c for c in mock_create.call_args_list if c.args and c.args[0] == 'clang-format']
    assert len(clang) == 1
    cmd = clang[0].args
    assert '--in-place' in cmd
    assert cmd.count('src/x.cpp') == 1
    assert cmd.count('orphaned.hpp') == 1


async def test_post_process_steps_clang_format_skipped_when_no_paths(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{}', encoding='utf-8')
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b'', b''))
    mock_proc.returncode = 0
    mock_create = mocker.patch('wiswa.utils.postprocess.asyncio.create_subprocess_exec',
                               return_value=mock_proc)
    settings = cast(
        'Any',
        _make_settings(project_type='c++', clang_format_args='', _readme_existed=False),
    )
    await post_process_steps(settings)
    clang = [c for c in mock_create.call_args_list if c.args and c.args[0] == 'clang-format']
    assert clang == []


async def test_post_process_steps_badges_no_codeql_no_tests(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch,
                                                            mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(_readme_existed=True, want_codeql=False, want_tests=False),
    )
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'CodeQL' not in content
    assert 'Tests' not in content
    assert 'QA' in content


async def test_post_process_steps_badges_docs_non_python_non_github(tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch,
                                                                    mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'package.json').write_text('{}', encoding='utf-8')
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast(
        'Any',
        _make_settings(
            project_type='c',
            _readme_existed=True,
            want_docs=True,
            using_github=False,
        ),
    )
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'readthedocs' not in content
    assert 'GitHub Pages' not in content


async def test_post_process_steps_no_docs_badges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                 mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    readme = tmp_path / 'README.md'
    readme.write_text('# Project\n\n[![old](http://example.com)]\n\nContent.\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(_readme_existed=True, want_docs=False))
    await post_process_steps(settings)
    content = readme.read_text(encoding='utf-8')
    assert 'readthedocs' not in content


def _export_settings(**overrides: Any) -> dict[str, Any]:
    er: dict[str, Any] = {
        'enabled': True,
        'format': 'requirements.txt',
        'output_filename': 'requirements.txt',
        'all_extras': False,
        'all_groups': False,
        'all_packages': False,
        'extra': [],
        'frozen': False,
        'group': [],
        'locked': False,
        'no_annotate': False,
        'no_default_groups': False,
        'no_dev': False,
        'no_editable': False,
        'no_emit_local': False,
        'no_emit_package': [],
        'no_emit_project': True,
        'no_emit_workspace': False,
        'no_extra': [],
        'no_group': [],
        'no_hashes': False,
        'no_header': False,
        'only_dev': False,
        'only_group': [],
        'package': [],
        'prune': [],
        'script': '',
        'with_hashes': True,
    }
    return er | overrides


def _setup_poetry_project(tmp_path: Path) -> None:
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.commitizen]\n'
        'version_files = ["wiswa/__init__.py:^__version__"]\n'
        '[tool.coverage]\nrun = {}\n'
        '[tool.pytest]\nini_options = {}\n'
        '[tool.yapf]\nbased_on_style = "pep8"\n'
        '[tool.yapfignore]\nignore_patterns = []\n'
        '[tool.ruff.lint]\nignore = []\n'
        '[tool.poetry.group.docs.dependencies]\nsphinx = "^7"\n'
        '[tool.poetry.group.tests.dependencies]\npytest = "^8"\n',
        encoding='utf-8',
    )
    (tmp_path / 'package.json').write_text(
        '{"scripts": {"check-formatting": "old", "format": "old"}}',
        encoding='utf-8',
    )


def _get_export_cmd(commands: list[str], tool: str = 'uv') -> str | None:
    for c in commands:
        if tool in c and 'export' in c:
            return c
    return None


async def test_post_process_steps_uv_export_defaults(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings(export_requirements=_export_settings()))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands)
    assert cmd is not None
    assert '--output-file requirements.txt' in cmd
    assert '--no-emit-project' in cmd
    assert '--format' not in cmd


async def test_post_process_steps_uv_export_disabled(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings())
    await post_process_steps(settings, on_command=commands.append)
    assert _get_export_cmd(commands) is None


async def test_post_process_steps_uv_export_all_flags(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch,
                                                      mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast(
        'Any',
        _make_settings(export_requirements=_export_settings(
            format='pylock.toml',
            output_filename='deps.txt',
            all_extras=True,
            all_groups=True,
            all_packages=True,
            extra=['docs'],
            frozen=True,
            group=['tests'],
            locked=True,
            no_annotate=True,
            no_default_groups=True,
            no_dev=True,
            no_editable=True,
            no_emit_local=True,
            no_emit_package=['foo'],
            no_emit_project=True,
            no_emit_workspace=True,
            no_extra=['bar'],
            no_group=['ci'],
            no_hashes=True,
            no_header=True,
            only_dev=True,
            only_group=['lint'],
            package=['pkg1'],
            prune=['pkg2'],
            script='script.py',
        )))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands)
    assert cmd is not None
    for flag in ('--format pylock.toml', '--all-packages', '--package pkg1', '--prune pkg2',
                 '--extra docs', '--all-extras', '--no-extra bar', '--no-dev', '--only-dev',
                 '--group tests', '--no-group ci', '--no-default-groups', '--only-group lint',
                 '--all-groups', '--no-annotate', '--no-header', '--no-editable', '--no-hashes',
                 '--output-file deps.txt', '--no-emit-project', '--no-emit-workspace',
                 '--no-emit-local', '--no-emit-package foo', '--locked', '--frozen',
                 '--script script.py'):
        assert flag in cmd


async def test_post_process_steps_uv_export_with_hashes_false(tmp_path: Path,
                                                              monkeypatch: pytest.MonkeyPatch,
                                                              mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings(export_requirements=_export_settings(with_hashes=False)))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands)
    assert cmd is not None
    assert '--no-hashes' in cmd


async def test_post_process_steps_uv_export_hashes_default(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch,
                                                           mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings(export_requirements=_export_settings()))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands)
    assert cmd is not None
    assert '--no-hashes' not in cmd


async def test_post_process_steps_uv_export_no_emit_project_false(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch,
                                                                  mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any',
                    _make_settings(export_requirements=_export_settings(no_emit_project=False)))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands)
    assert cmd is not None
    assert '--no-emit-project' not in cmd


async def test_post_process_steps_uv_export_pylock_derives_filename(tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch,
                                                                    mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast(
        'Any',
        _make_settings(
            export_requirements=_export_settings(format='pylock.toml', output_filename='')))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands)
    assert cmd is not None
    assert '--output-file pylock.toml' in cmd


async def test_post_process_steps_uv_export_quiet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                  mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings(export_requirements=_export_settings()))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands)
    assert cmd is not None
    assert cmd.startswith('uv --quiet export')


async def test_post_process_steps_uv_export_debug_no_quiet(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch,
                                                           mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings(export_requirements=_export_settings()))
    await post_process_steps(settings, debug=True, on_command=commands.append)
    cmd = _get_export_cmd(commands)
    assert cmd is not None
    assert '--quiet' not in cmd


async def test_post_process_steps_poetry_export_defaults(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch,
                                                         mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_poetry_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast(
        'Any', _make_settings(package_manager='poetry', export_requirements=_export_settings()))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands, tool='poetry')
    assert cmd is not None
    assert '--format requirements.txt' in cmd
    assert '--output requirements.txt' in cmd
    assert '--with=dev' in cmd


async def test_post_process_steps_poetry_export_disabled(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch,
                                                         mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_poetry_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast('Any', _make_settings(package_manager='poetry'))
    await post_process_steps(settings, on_command=commands.append)
    assert _get_export_cmd(commands, tool='poetry') is None


async def test_post_process_steps_poetry_export_all_groups(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch,
                                                           mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_poetry_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast(
        'Any',
        _make_settings(package_manager='poetry',
                       export_requirements=_export_settings(all_groups=True)))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands, tool='poetry')
    assert cmd is not None
    assert '--with=dev,docs,tests' in cmd


async def test_post_process_steps_poetry_export_no_dev(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch,
                                                       mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_poetry_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast(
        'Any',
        _make_settings(package_manager='poetry',
                       export_requirements=_export_settings(no_dev=True, group=['tests'])))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands, tool='poetry')
    assert cmd is not None
    assert '--with=tests' in cmd
    assert 'dev' not in cmd.split('--with=')[1].split(' ')[0]


async def test_post_process_steps_poetry_export_without_hashes(tmp_path: Path,
                                                               monkeypatch: pytest.MonkeyPatch,
                                                               mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_poetry_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast(
        'Any',
        _make_settings(package_manager='poetry',
                       export_requirements=_export_settings(no_hashes=True)))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands, tool='poetry')
    assert cmd is not None
    assert '--without-hashes' in cmd


async def test_post_process_steps_poetry_export_all_extras(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch,
                                                           mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_poetry_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast(
        'Any',
        _make_settings(package_manager='poetry',
                       export_requirements=_export_settings(all_extras=True)))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands, tool='poetry')
    assert cmd is not None
    assert '--all-extras' in cmd
    assert '--extras=' not in cmd


async def test_post_process_steps_poetry_export_extras(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch,
                                                       mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_poetry_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast(
        'Any',
        _make_settings(package_manager='poetry',
                       export_requirements=_export_settings(extra=['docs', 'tests'])))
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands, tool='poetry')
    assert cmd is not None
    assert '--extras=docs' in cmd
    assert '--extras=tests' in cmd


async def test_post_process_steps_poetry_export_all_groups_empty_with(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_poetry_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast(
        'Any',
        _make_settings(
            package_manager='poetry',
            want_docs=False,
            want_tests=False,
            export_requirements=_export_settings(all_groups=True, no_dev=True),
        ),
    )
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands, tool='poetry')
    assert cmd is not None
    assert '--with=' not in cmd


async def test_post_process_steps_poetry_export_only_dev(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch,
                                                         mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_poetry_project(tmp_path)
    _mock_subprocess(mocker)
    commands: list[str] = []
    settings = cast(
        'Any',
        _make_settings(
            package_manager='poetry',
            export_requirements=_export_settings(only_dev=True),
        ),
    )
    await post_process_steps(settings, on_command=commands.append)
    cmd = _get_export_cmd(commands, tool='poetry')
    assert cmd is not None
    assert '--only=dev' in cmd


async def test_post_process_steps_regenerate_yarn_lock_true(tmp_path: Path,
                                                            monkeypatch: pytest.MonkeyPatch,
                                                            mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    yarn_lock = tmp_path / 'yarn.lock'
    yarn_lock.write_text('# yarn lockfile v1\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(regenerate_yarn_lock=True))
    await post_process_steps(settings)
    assert not yarn_lock.exists()


async def test_post_process_steps_regenerate_yarn_lock_false(tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch,
                                                             mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    yarn_lock = tmp_path / 'yarn.lock'
    yarn_lock.write_text('# yarn lockfile v1\n', encoding='utf-8')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings(regenerate_yarn_lock=False))
    await post_process_steps(settings)
    assert yarn_lock.exists()


class _FakeAsyncSubprocess:
    """Minimal stand-in for asyncio subprocess.Process in create_subprocess_exec tests."""

    __slots__ = ('_stdout', 'returncode')

    def __init__(self, returncode: int, stdout: bytes = b'') -> None:
        self.returncode = returncode
        self._stdout = stdout

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, b''


_MINIMAL_UV_LOCK = ('version = 1\n'
                    'revision = 1\n'
                    'requires-python = ">=3.10"\n'
                    '\n'
                    '[options]\n'
                    'exclude-newer = "2025-01-01T00:00:00Z"\n'
                    'exclude-newer-span = "P1W"\n'
                    '\n'
                    '[[package]]\n'
                    'name = "w"\n'
                    'version = "1.0.0"\n'
                    'source = { registry = "https://pypi.org/simple" }\n')

_UV_LOCK_DIFF_OK = ('diff --git a/uv.lock b/uv.lock\n'
                    '--- a/uv.lock\n'
                    '+++ b/uv.lock\n'
                    '@@ -2,2 +2,2 @@\n'
                    ' [options]\n'
                    '-exclude-newer = "a"\n'
                    '+exclude-newer = "b"\n'
                    ' exclude-newer-span = "P1W"\n')

_UV_LOCK_DIFF_WITH_BLANK_HUNK_LINE = ('diff --git a/uv.lock b/uv.lock\n'
                                      '--- a/uv.lock\n'
                                      '+++ b/uv.lock\n'
                                      '@@ -2,3 +2,3 @@\n'
                                      ' [options]\n'
                                      '\n'
                                      '-exclude-newer = "a"\n'
                                      '+exclude-newer = "b"\n')

_UV_LOCK_DIFF_BOGUS_HUNK = ('--- a/uv.lock\n'
                            '+++ b/uv.lock\n'
                            '@@ -1,1 +1,1 @@\n'
                            'bogus\n')

_UV_LOCK_DIFF_BAD_PLUS_LINE = ('--- a/uv.lock\n'
                               '+++ b/uv.lock\n'
                               '@@ -1,2 +1,2 @@\n'
                               '-exclude-newer = "a"\n'
                               '+version = "2"\n')


def test_uv_lock_diff_changes_only_exclude_newer_empty() -> None:
    assert uv_lock_diff_changes_only_exclude_newer('') is False


def test_uv_lock_diff_changes_only_exclude_newer_whitespace_only() -> None:
    assert uv_lock_diff_changes_only_exclude_newer('   \n  ') is False


def test_uv_lock_diff_changes_only_exclude_newer_valid() -> None:
    assert uv_lock_diff_changes_only_exclude_newer(_UV_LOCK_DIFF_OK) is True


def test_uv_lock_diff_changes_only_exclude_newer_blank_line_in_hunk() -> None:
    assert uv_lock_diff_changes_only_exclude_newer(_UV_LOCK_DIFF_WITH_BLANK_HUNK_LINE) is True


def test_uv_lock_diff_changes_only_exclude_newer_bogus_hunk_line() -> None:
    assert uv_lock_diff_changes_only_exclude_newer(_UV_LOCK_DIFF_BOGUS_HUNK) is False


def test_uv_lock_diff_changes_only_exclude_newer_non_matching_plus() -> None:
    assert uv_lock_diff_changes_only_exclude_newer(_UV_LOCK_DIFF_BAD_PLUS_LINE) is False


def test_uv_lock_diff_changes_only_exclude_newer_headers_only() -> None:
    assert uv_lock_diff_changes_only_exclude_newer('diff --git a/uv.lock b/uv.lock\n'
                                                   'index 111..222 100644\n'
                                                   '--- a/uv.lock\n'
                                                   '+++ b/uv.lock\n') is False


def _git_init_commit_uv_repo(tmp_path: Path, *, lock_text: str = 'committed-lock\n') -> None:
    git = which('git')
    assert git is not None
    subprocess.run([git, 'init'], check=True, cwd=tmp_path, capture_output=True)
    subprocess.run([git, 'config', 'user.email', 't@e.st'], check=True, cwd=tmp_path)
    subprocess.run([git, 'config', 'user.name', 't'], check=True, cwd=tmp_path)
    subprocess.run([git, 'config', 'commit.gpgsign', 'false'], check=True, cwd=tmp_path)
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "x"\nversion = "0"\n',
                                             encoding='utf-8')
    (tmp_path / 'uv.lock').write_text(lock_text, encoding='utf-8')
    subprocess.run([git, 'add', 'pyproject.toml', 'uv.lock'], check=True, cwd=tmp_path)
    subprocess.run([git, 'commit', '-m', 'init'], check=True, cwd=tmp_path, capture_output=True)


@pytest.mark.skipif(which('git') is None, reason='git not installed')
def test_uv_lock_diff_changes_only_exclude_newer_real_git_diff(tmp_path: Path) -> None:
    _git_init_commit_uv_repo(tmp_path, lock_text=_MINIMAL_UV_LOCK)
    drifted = _MINIMAL_UV_LOCK.replace(
        'exclude-newer = "2025-01-01T00:00:00Z"',
        'exclude-newer = "2030-01-01T00:00:00Z"',
    )
    (tmp_path / 'uv.lock').write_text(drifted, encoding='utf-8')
    git = which('git')
    assert git is not None
    diff = subprocess.run(
        [git, 'diff', '--no-color', '-a', 'HEAD', '--', 'uv.lock'],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert diff.returncode == 0
    assert uv_lock_diff_changes_only_exclude_newer(diff.stdout) is True


@pytest.mark.skipif(which('git') is None, reason='git not installed')
async def test_maybe_revert_uv_lock_restores_when_only_lock_differs(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _git_init_commit_uv_repo(tmp_path)
    (tmp_path / 'uv.lock').write_text('drifted-lock\n', encoding='utf-8')
    settings = cast('Any', _make_settings())
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    assert (tmp_path / 'uv.lock').read_text(encoding='utf-8') == 'committed-lock\n'


@pytest.mark.skipif(which('git') is None, reason='git not installed')
async def test_maybe_revert_uv_lock_skips_when_pyproject_also_differs(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _git_init_commit_uv_repo(tmp_path)
    (tmp_path / 'uv.lock').write_text('drifted-lock\n', encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "y"\nversion = "0"\n',
                                             encoding='utf-8')
    settings = cast('Any', _make_settings())
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    assert (tmp_path / 'uv.lock').read_text(encoding='utf-8') == 'drifted-lock\n'


@pytest.mark.skipif(which('git') is None, reason='git not installed')
async def test_maybe_revert_uv_lock_restores_when_only_options_differ_and_other_files_differ(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _git_init_commit_uv_repo(tmp_path, lock_text=_MINIMAL_UV_LOCK)
    drifted = _MINIMAL_UV_LOCK.replace(
        'exclude-newer = "2025-01-01T00:00:00Z"',
        'exclude-newer = "2030-01-01T00:00:00Z"',
    )
    (tmp_path / 'uv.lock').write_text(drifted, encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "y"\nversion = "0"\n',
                                             encoding='utf-8')
    settings = cast('Any', _make_settings())
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    assert (tmp_path / 'uv.lock').read_text(encoding='utf-8') == _MINIMAL_UV_LOCK


@pytest.mark.skipif(which('git') is None, reason='git not installed')
async def test_maybe_revert_uv_lock_skips_when_package_and_other_files_differ(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _git_init_commit_uv_repo(tmp_path, lock_text=_MINIMAL_UV_LOCK)
    drifted = _MINIMAL_UV_LOCK.replace('version = "1.0.0"', 'version = "2.0.0"')
    (tmp_path / 'uv.lock').write_text(drifted, encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "y"\nversion = "0"\n',
                                             encoding='utf-8')
    settings = cast('Any', _make_settings())
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    assert (tmp_path / 'uv.lock').read_text(encoding='utf-8') == drifted


@pytest.mark.skipif(which('git') is None, reason='git not installed')
async def test_maybe_revert_uv_lock_skips_when_only_span_differs_and_other_files_differ(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _git_init_commit_uv_repo(tmp_path, lock_text=_MINIMAL_UV_LOCK)
    drifted = _MINIMAL_UV_LOCK.replace('exclude-newer-span = "P1W"', 'exclude-newer-span = "P2W"')
    (tmp_path / 'uv.lock').write_text(drifted, encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "y"\nversion = "0"\n',
                                             encoding='utf-8')
    settings = cast('Any', _make_settings())
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    assert (tmp_path / 'uv.lock').read_text(encoding='utf-8') == drifted


@pytest.mark.skipif(which('git') is None, reason='git not installed')
async def test_maybe_revert_uv_lock_restores_despite_untracked_file(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _git_init_commit_uv_repo(tmp_path)
    (tmp_path / 'uv.lock').write_text('drifted-lock\n', encoding='utf-8')
    (tmp_path / 'noise.txt').write_text('x', encoding='utf-8')
    settings = cast('Any', _make_settings())
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    assert (tmp_path / 'uv.lock').read_text(encoding='utf-8') == 'committed-lock\n'


@pytest.mark.skipif(which('git') is None, reason='git not installed')
async def test_maybe_revert_uv_lock_skips_when_uv_lock_not_in_diff(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _git_init_commit_uv_repo(tmp_path)
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "z"\nversion = "0"\n',
                                             encoding='utf-8')
    settings = cast('Any', _make_settings())
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    assert (tmp_path / 'uv.lock').read_text(encoding='utf-8') == 'committed-lock\n'


@pytest.mark.skipif(which('git') is None, reason='git not installed')
async def test_maybe_revert_uv_lock_skips_for_poetry(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _git_init_commit_uv_repo(tmp_path)
    (tmp_path / 'uv.lock').write_text('drifted-lock\n', encoding='utf-8')
    settings = cast('Any', _make_settings(package_manager='poetry'))
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    assert (tmp_path / 'uv.lock').read_text(encoding='utf-8') == 'drifted-lock\n'


async def test_maybe_revert_uv_lock_skips_when_git_diff_fails(tmp_path: Path,
                                                              monkeypatch: pytest.MonkeyPatch,
                                                              mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.git').mkdir()
    (tmp_path / 'uv.lock').write_text('local\n', encoding='utf-8')
    settings = cast('Any', _make_settings())

    async def fake_exec(*args: object, **kwargs: object) -> _FakeAsyncSubprocess:
        await asyncio.sleep(0)
        return _FakeAsyncSubprocess(1, b'')

    mocker.patch('wiswa.utils.postprocess.asyncio.create_subprocess_exec', side_effect=fake_exec)
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    assert (tmp_path / 'uv.lock').read_text(encoding='utf-8') == 'local\n'


async def test_maybe_revert_uv_lock_skips_when_git_diff_uv_lock_fails(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.git').mkdir()
    (tmp_path / 'uv.lock').write_text('local\n', encoding='utf-8')
    settings = cast('Any', _make_settings())
    calls: list[tuple[object, ...]] = []

    async def fake_exec(*args: object, **kwargs: object) -> _FakeAsyncSubprocess:
        await asyncio.sleep(0)
        calls.append(tuple(args))
        n = len(calls)
        if n == 1:
            return _FakeAsyncSubprocess(0, b'uv.lock\npyproject.toml\n')
        return _FakeAsyncSubprocess(1, b'')

    mocker.patch('wiswa.utils.postprocess.asyncio.create_subprocess_exec', side_effect=fake_exec)
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    assert len(calls) == 2
    assert (tmp_path / 'uv.lock').read_text(encoding='utf-8') == 'local\n'


async def test_maybe_revert_uv_lock_restore_falls_back_to_checkout(tmp_path: Path,
                                                                   monkeypatch: pytest.MonkeyPatch,
                                                                   mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.git').mkdir()
    (tmp_path / 'uv.lock').write_text('local\n', encoding='utf-8')
    settings = cast('Any', _make_settings())
    recorded: list[tuple[object, ...]] = []

    async def fake_exec(*args: object, **kwargs: object) -> _FakeAsyncSubprocess:
        await asyncio.sleep(0)
        recorded.append(tuple(args))
        n = len(recorded)
        if n == 1:
            return _FakeAsyncSubprocess(0, b'uv.lock\n')
        if n == 2:
            return _FakeAsyncSubprocess(1, b'restore failed')
        if n == 3:
            return _FakeAsyncSubprocess(0, b'')
        return _FakeAsyncSubprocess(1, b'')

    mocker.patch('wiswa.utils.postprocess.asyncio.create_subprocess_exec', side_effect=fake_exec)
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    hooks = ('-c', f'core.hooksPath={os.devnull}')
    assert recorded[1][0] == 'git'
    assert tuple(recorded[1][1:3]) == hooks
    assert recorded[1][3:8] == ('restore', '--source=HEAD', '--staged', '--worktree', '--')
    assert recorded[1][8] == 'uv.lock'
    assert recorded[2][0] == 'git'
    assert tuple(recorded[2][1:3]) == hooks
    assert recorded[2][3:6] == ('checkout', 'HEAD', '--')
    assert recorded[2][6] == 'uv.lock'


async def test_maybe_revert_uv_lock_logs_when_restore_and_checkout_fail(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.git').mkdir()
    (tmp_path / 'uv.lock').write_text('local\n', encoding='utf-8')
    settings = cast('Any', _make_settings())
    calls: list[int] = []

    async def fake_exec(*args: object, **kwargs: object) -> _FakeAsyncSubprocess:
        await asyncio.sleep(0)
        calls.append(1)
        n = len(calls)
        if n == 1:
            return _FakeAsyncSubprocess(0, b'uv.lock\n')
        if n == 2:
            return _FakeAsyncSubprocess(1, b'restore failed')
        return _FakeAsyncSubprocess(1, b'both failed')

    mocker.patch('wiswa.utils.postprocess.asyncio.create_subprocess_exec', side_effect=fake_exec)
    caplog.set_level(logging.WARNING)
    await maybe_revert_uv_lock_if_only_lockfile_changed(settings)
    assert len(calls) == 3
    assert 'Could not restore uv.lock from HEAD' in caplog.text
