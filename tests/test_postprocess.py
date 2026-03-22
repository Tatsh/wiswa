"""Tests for post-processing utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock

from wiswa.utils.postprocess import post_process_steps

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture
    import pytest


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
        'using_django': False,
        'project_name': 'myproject',
        'pypi_project_name': 'myproject',
        'primary_module': 'mymod',
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
        'vscode': {
            'launch': None,
        },
        '_readme_existed': False,
    }
    return base | overrides


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
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b'', b''))
    mock_proc.returncode = 0
    mocker.patch('wiswa.utils.postprocess.asyncio.create_subprocess_exec', return_value=mock_proc)
    return mock_proc


async def test_post_process_steps_python_uv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                            mocker: MockerFixture) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_python_project(tmp_path)
    (tmp_path / 'poetry.lock').write_text('lock')
    _mock_subprocess(mocker)
    settings = cast('Any', _make_settings())
    await post_process_steps(settings)
    assert not (tmp_path / 'poetry.lock').exists()


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
