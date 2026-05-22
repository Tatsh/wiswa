"""Tests for Jinja2 templating."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlparse
import importlib.resources
import logging
import re
import shutil

from wiswa.tool.utils.postprocess import resolve_changelog_boilerplate_urls
from wiswa.tool.utils.templating import write_templated_files
import pytest
import wiswa.tool

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

_HTTPS_URL_RE = re.compile(r'https?://[^\s\)\]>\'\"]+', re.IGNORECASE)


def _https_urls_in_text(text: str) -> list[str]:
    return [m.group(0).rstrip('.,;') for m in _HTTPS_URL_RE.finditer(text)]


def _urls_include_hostname(text: str, hostname: str) -> bool:
    want = hostname.lower()
    for u in _https_urls_in_text(text):
        h = urlparse(u).hostname
        if h is not None and h.lower() == want:
            return True
    return False


def _urls_include_docs_astral_uv(text: str) -> bool:
    for u in _https_urls_in_text(text):
        p = urlparse(u)
        if p.hostname == 'docs.astral.sh' and (p.path or '').startswith('/uv'):
            return True
    return False


def _social_networks() -> dict[str, Any]:
    return {
        'bsky': '',
        'mastodon': {
            'id': '',
            'domain': ''
        },
        'custom_badges': [],
        'youtube': {
            'text': '',
            'uri': ''
        },
        'patreon': '',
        'cashapp': '',
        'slashdot': '',
        'calendly': {
            'text': '',
            'uri': ''
        },
        'buymeacoffee': '',
        'libera_irc': ''
    }


def _vscode_defaults() -> dict[str, Any]:
    return {'extensions': [], 'launch': None}


def _export_requirements_defaults() -> dict[str, Any]:
    return {
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
        'with_hashes': True
    }


def _pyinstaller_defaults() -> dict[str, Any]:
    return {
        'extra_args': [],
        'macos_exclusions': [],
        'windows_exclusions': [],
        'include_only': [],
        'collect_data': [],
        'collect_submodules': [],
        'copy_metadata': [],
        'hidden_imports': ['colorlog'],
        'test_commands': [],
        'uv_sync_args': [],
        'vcpkg': {
            'enabled': False,
            'targets': {}
        }
    }


def _appimage_defaults() -> dict[str, Any]:
    return {
        'exclusions': [],
        'include_only': [],
        'icons': {},
        'categories': ['Utility'],
        'python_version': '3.13',
        'terminal': True,
        'test_commands': [],
        'uv_sync_args': [],
        'requirements_filter': ''
    }


def _github_defaults() -> dict[str, Any]:
    return {
        'immutable_releases': True,
        'username': 'test',
        'secret_vars': {
            'windows': {
                'signing_certificate': 'WINDOWS_SIGNING_CERTIFICATE',
                'signing_password': 'WINDOWS_SIGNING_PASSWORD',
                'timestamp_url': 'WINDOWS_TIMESTAMP_URL'
            },
            'apple': {
                'signing_certificate': 'APPLE_SIGNING_CERTIFICATE',
                'signing_password': 'APPLE_SIGNING_PASSWORD',
                'signing_identity': 'APPLE_SIGNING_IDENTITY',
                'apple_id': 'APPLE_ID',
                'app_specific_password': 'APPLE_APP_SPECIFIC_PASSWORD',
                'team_id': 'APPLE_TEAM_ID'
            }
        },
        'workflows': {
            'appimage': {
                'apt_packages': []
            },
            'codeql': {
                'apt_packages': []
            },
            'publish_npm_any': {
                'node_version': '24',
                'runs_on': 'ubuntu-latest',
                'registry_url': 'https://registry.npmjs.org/'
            },
            'publish_pypi_any': {
                'python_version': '3.13',
                'runs_on': 'ubuntu-latest'
            },
            'publish_winget': {
                'identifier': 'test.testproject',
                'max_versions_to_keep': 3
            },
            'qa': {
                'allow_pyright_failure': False,
                'allow_ty_failure': False,
                'apt_packages': []
            },
            'tests': {
                'apt_packages': []
            },
            'release_gate_workflows': []
        }
    }


def _cmake_defaults() -> dict[str, Any]:
    return {
        'shared_deps': [],
        'googletest_version': '1.17.0',
        'uses_ecm': False,
        'uses_qt': False,
        'want_feature_summary': True,
        'want_cpack': True
    }


def _eslint_defaults() -> list[dict[str, Any]]:
    return [{
        'rules': {
            '@typescript-eslint/no-unused-vars': [
                'error', {
                    'argsIgnorePattern': '^_',
                    'caughtErrorsIgnorePattern': '^_',
                    'destructuredArrayIgnorePattern': '^_',
                    'varsIgnorePattern': '^_'
                }
            ]
        }
    }]


def _docs_conf_defaults() -> dict[str, Any]:
    return {
        'environment_variables': {},
        'extensions': [
            'sphinx.ext.autodoc', 'sphinx.ext.intersphinx', 'sphinx.ext.napoleon',
            'sphinx_datatables', 'sphinx_immaterial', 'sphinxcontrib.autodoc_pydantic',
            'sphinxcontrib.jquery'
        ],
        'django': {
            'monkeypatch': True,
            'settings_module': 'settings',
            'settings': {
                'DATABASES': {
                    'default': {
                        'ENGINE': 'django.db.backends.sqlite3',
                        'NAME': ':memory:'
                    }
                },
                'INSTALLED_APPS': [
                    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
                    'django.contrib.sessions', 'django.contrib.messages',
                    'django.contrib.staticfiles'
                ],
                'PATH_PREFIX': ''
            }
        },
        'config': {
            'datatables_class': 'sphinx-datatable',
            'datatables_options': {
                'paging': False
            },
            'datatables_version': '1.13.4',
            'intersphinx_mapping': {
                'python': ['https://docs.python.org/3', None]
            },
            'html_theme': 'sphinx_immaterial',
            'html_theme_options': {
                'features': [
                    'announce.dismiss', 'content.action.edit', 'content.action.view',
                    'content.code.copy', 'content.tabs.link', 'content.tooltips',
                    'navigation.expand', 'navigation.footer', 'navigation.sections',
                    'navigation.top', 'search.share', 'search.suggest', 'toc.follow', 'toc.sticky'
                ],
                'font': False,
                'icon': {
                    'edit': 'material/file-edit-outline',
                    'repo': 'fontawesome/brands/github'
                },
                'globaltoc_collapse': True,
                'palette': [{
                    'media': '(prefers-color-scheme)',
                    'toggle': {
                        'icon': 'material/brightness-auto',
                        'name': 'Switch to light mode'
                    }
                }, {
                    'media': '(prefers-color-scheme: light)',
                    'scheme': 'default',
                    'primary': 'teal',
                    'accent': 'light-blue',
                    'toggle': {
                        'icon': 'material/lightbulb',
                        'name': 'Switch to dark mode'
                    }
                }, {
                    'media': '(prefers-color-scheme: dark)',
                    'scheme': 'slate',
                    'primary': 'black',
                    'accent': 'blue',
                    'toggle': {
                        'icon': 'material/lightbulb-outline',
                        'name': 'Switch to system preference'
                    }
                }],
                'toc_title_is_page_title': True,
                'edit_uri': '/tree/master/docs',
                'repo_name': 'testdir',
                'repo_url': 'https://github.com/test/testproject',
                'site_url': 'https://example.com/docs'
            }
        }
    }


def _stub_github_api_session() -> MagicMock:
    session = MagicMock()

    def _get(url: str, *_args: Any, **_kwargs: Any) -> MagicMock:
        response = MagicMock()
        response.ok = True
        response.status_code = 200
        if '/releases/latest' in url:
            response.json = MagicMock(return_value={'tag_name': 'v4.1.2'})
        elif '/tags' in url:
            response.json = MagicMock(return_value=[{'name': 'v4.1.2'}])
        else:
            response.json = MagicMock(return_value={})
        return response

    def _head(*_args: Any, **_kwargs: Any) -> MagicMock:
        response = MagicMock()
        response.ok = True
        response.status_code = 200
        return response

    session.get = AsyncMock(side_effect=_get)
    session.head = AsyncMock(side_effect=_head)
    return session


def _make_settings(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        'default_branch': 'master',
        'description': 'A test project.',
        'documentation_uri': 'https://example.com/docs',
        'github': _github_defaults(),
        'gitlab': {},
        'github_username': 'test',
        'github_project_name': 'testproject',
        'has_multiple_entry_points': False,
        'homepage': 'https://example.com',
        'keywords': [],
        'mastodon_id': None,
        'modules': ['mymod'],
        'package_json': {
            'dependencies': {},
            'devDependencies': {}
        },
        'primary_module': 'mymod',
        'primary_module_qualified': 'mymod',
        'private': False,
        'project_name': 'testproject',
        'project_type': 'python',
        'pypi_project_name': 'testproject',
        'python_deps': {
            'main': {}
        },
        'pyproject': {
            'project': {
                'dependencies': []
            }
        },
        'repository_uri': 'https://github.com/test/testproject',
        'social': _social_networks(),
        'stubs_only': False,
        'supported_platforms': 'all',
        'supported_python_versions': ['3.12'],
        'using_django': False,
        'using_github': False,
        'using_gitlab': False,
        'vscode': _vscode_defaults(),
        'want_ai': False,
        'uses_user_defaults': False,
        'want_appimage': False,
        'want_pyinstaller': False,
        'want_codeql': False,
        'want_gpg': False,
        'claude_settings_local': {},
        'custom_project_badges': [],
        'export_requirements': _export_requirements_defaults(),
        'want_docs': False,
        'want_main': False,
        'want_man': False,
        'package_manager': 'uv',
        'regenerate_yarn_lock': False,
        'want_tests': False,
        'want_yapf': False,
        'version': '0.0.1',
        'yarn_version': '4',
        '_readme_existed': False,
        '_has_established_pytest_modules': False,
        'codeowners': {},
        'using_readthedocs': False,
        'security_addendum': '',
        'security_policy_supported_versions': {},
        'directory_name': 'testdir',
        'full_name': 'Test Author',
        'email': 'test@example.com',
        'year': '2024',
        'license': 'MIT',
        'license_name': 'MIT',
        'cmake': _cmake_defaults(),
        'cxx_standard': 23,
        'eslint': _eslint_defaults(),
        'pyinstaller': _pyinstaller_defaults(),
        'appimage': _appimage_defaults(),
        'docs_conf': _docs_conf_defaults(),
        'using_drf': False
    }
    merged = base | overrides
    branch = str(merged['default_branch'])
    repo_url = str(merged['repository_uri'])
    doc_uri = str(merged['documentation_uri'])
    dir_name = str(merged['directory_name'])
    dc = dict(merged['docs_conf'])
    cfg = dict(dc['config'])
    hto = dict(cfg['html_theme_options'])
    hto['edit_uri'] = f'/tree/{branch}/docs'
    hto['repo_name'] = dir_name
    hto['repo_url'] = repo_url
    hto['site_url'] = doc_uri
    cfg['html_theme_options'] = hto
    dc['config'] = cfg
    merged['docs_conf'] = dc
    return merged


def _copy_wiswa_package(tmp_path: Path) -> Path:
    src = Path(wiswa.tool.__file__).resolve().parent
    dst = tmp_path / 'wiswa_pkg'
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


async def _run_write(monkeypatch: pytest.MonkeyPatch, scratch: Path, module_path: Path,
                     settings: dict[str, Any]) -> Path:
    out = scratch / 'proj'
    out.mkdir(parents=True)
    monkeypatch.chdir(out)
    session = None
    if settings.get('using_github'):
        session = _stub_github_api_session()
    await write_templated_files(module_path, cast('Any', settings), session=session)
    return out


async def test_write_templated_files_claude_agents_wanted(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    out = await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=True))
    assert (out / '.claude/rules/general.md').exists()
    assert (out / '.claude/rules/markdown.md').exists()
    assert (out / '.claude/rules/python.md').exists()
    markdown_rule = (out / '.claude/rules/markdown.md').read_text(encoding='utf-8')
    assert 'GitHub Pages' not in markdown_rule
    assert (out / '.claude/agents/regen.md').exists()
    assert (out / '.claude/skills/ci/SKILL.md').exists()
    assert (out / 'CLAUDE.md').exists()
    assert (out / 'AGENTS.md').exists()


async def test_write_templated_files_markdown_rule_includes_github_pages_when_using_github(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    out = await _run_write(monkeypatch, tmp_path, module_path,
                           _make_settings(want_ai=True, using_github=True))
    markdown_rule = (out / '.claude/rules/markdown.md').read_text(encoding='utf-8')
    assert 'GitHub Pages' in markdown_rule
    assert 'Jekyll' in markdown_rule


async def test_write_templated_files_claude_skills_non_dir_entry(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    stray = module_path / 'templates/claude/skills/stray-file.txt'
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text('not a directory', encoding='utf-8')
    out = await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=True))
    assert (out / '.claude/skills/ci/SKILL.md').exists()
    assert not (out / '.claude/skills/stray-file.txt').exists()


async def test_write_templated_files_cleanup_unlinks_when_ai_disabled(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / 'proj'
    out.mkdir()
    monkeypatch.chdir(out)
    settings_on = _make_settings(want_ai=True)
    settings_off = _make_settings(want_ai=False)
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        await write_templated_files(module_path, cast('Any', settings_on))
        assert (out / 'AGENTS.md').exists()
        assert (out / '.claude/agents/regen.md').exists()
        await write_templated_files(module_path, cast('Any', settings_off))
    assert not (out / 'AGENTS.md').exists()
    assert not (out / 'CLAUDE.md').exists()
    assert not (out / '.claude/agents/regen.md').exists()
    assert not (out / '.claude/skills/ci/SKILL.md').exists()


async def test_write_templated_files_claude_agents_not_wanted(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    out = await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=False))
    assert not (out / 'CLAUDE.md').exists()
    assert not (out / 'AGENTS.md').exists()
    assert not (out / '.claude/agents/regen.md').exists()


async def test_write_templated_files_claude_no_agents_dir(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    shutil.rmtree(module_path / 'templates/claude/agents')
    out = await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=True))
    assert (out / 'CLAUDE.md').exists()
    assert (out / 'AGENTS.md').exists()
    assert not (out / '.claude/agents').exists()


@pytest.mark.parametrize('project_type', ['c++', 'c', 'lua', 'typescript'])
async def test_write_templated_files_dispatches_project_types(
        project_type: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        settings = _make_settings(project_type=project_type)
        out = await _run_write(monkeypatch, tmp_path, module_path, settings)
        match project_type:
            case 'c++':
                assert (out / 'CMakeLists.txt').exists()
                assert (out / 'src/CMakeLists.txt').exists()
            case 'c':
                assert (out / 'CMakeLists.txt').exists()
                assert (out / 'src/CMakeLists.txt').exists()
            case 'lua':
                assert (out / '.busted').exists()
                assert (out / '.luacov').exists()
            case 'typescript':
                assert (out / 'eslint.config.mjs').exists()


async def test_write_templated_files_unknown_type_warns(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch,
                                                        caplog: pytest.LogCaptureFixture) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        settings = _make_settings(project_type='generic')
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger='wiswa.tool.utils.templating'):
            await _run_write(monkeypatch, tmp_path, module_path, settings)
    assert any('No templated files to write' in rec.message for rec in caplog.records)


async def test_write_templated_files_contributing_overwrite_uv_with_poetry(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = tmp_path / 'proj'
        out.mkdir()
        monkeypatch.chdir(out)
        before = 'Install with Poetry\n'
        (out / 'CONTRIBUTING.md').write_text(before, encoding='utf-8')
        settings = _make_settings(package_manager='uv', want_ai=False)
        await write_templated_files(module_path, cast('Any', settings))
        after = (out / 'CONTRIBUTING.md').read_text(encoding='utf-8')
        assert after != before
        assert 'testproject' in after


async def test_write_templated_files_contributing_no_overwrite_matching(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = tmp_path / 'proj'
        out.mkdir()
        monkeypatch.chdir(out)
        text = 'Use uv to manage deps\n'
        (out / 'CONTRIBUTING.md').write_text(text, encoding='utf-8')
        settings = _make_settings(package_manager='uv', want_ai=False)
        await write_templated_files(module_path, cast('Any', settings))
        assert (out / 'CONTRIBUTING.md').read_text(encoding='utf-8') == text


async def test_write_templated_files_python_want_docs(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(want_docs=True, want_tests=False, want_ai=False))
    assert (out / 'docs/conf.py').exists()
    assert (out / 'docs/index.rst').exists()
    assert (out / 'docs/badges.rst').exists()


async def test_write_templated_files_python_private_badges_rst_omits_public_registries(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(want_docs=True,
                           want_tests=True,
                           want_ai=False,
                           private=True,
                           using_github=True))
    text = (out / 'docs/badges.rst').read_text(encoding='utf-8')
    lower = text.lower()
    assert 'pypi.org/project' not in lower
    assert 'pepy.tech' not in lower
    assert 'readthedocs.org' not in lower
    assert 'coveralls.io' not in lower
    after_only = text.split('.. only:: html', maxsplit=1)[1]
    assert after_only.startswith('\n\n   ')
    assert not after_only.startswith('\n\n\n')
    assert _urls_include_docs_astral_uv(lower)


async def test_write_templated_files_docs_badges_rst_includes_poetry_when_not_uv(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(want_docs=True,
                           want_tests=False,
                           want_ai=False,
                           package_manager='poetry'))
    text = (out / 'docs/badges.rst').read_text(encoding='utf-8').lower()
    assert _urls_include_hostname(text, 'python-poetry.org')
    assert not _urls_include_docs_astral_uv(text)


async def test_write_templated_files_docs_badges_rst_regenerated_when_stale(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(want_docs=True, want_tests=False, want_ai=False))
    badges = out / 'docs/badges.rst'
    badges.write_text('.. STALE-BADGES-MARKER\n', encoding='utf-8')
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        monkeypatch.chdir(out)
        await write_templated_files(
            module_path, cast('Any', _make_settings(want_docs=True, want_tests=False,
                                                    want_ai=False)))
    text = badges.read_text(encoding='utf-8')
    assert 'STALE-BADGES-MARKER' not in text
    assert '.. only:: html' in text


async def test_write_templated_files_python_no_docs(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(want_docs=False, want_tests=False, want_ai=False))
    assert not (out / 'docs').exists()


async def test_write_templated_files_python_want_tests_and_main(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(want_appimage=True,
                           want_pyinstaller=True,
                           want_tests=True,
                           want_main=True,
                           want_ai=False,
                           using_github=True,
                           supported_platforms='all'))
    assert (out / 'tests/conftest.py').exists()
    assert (out / 'tests/test_main.py').exists()
    assert (out / '.github/workflows/pyinstaller.yml').exists()
    assert (out / '.github/workflows/appimage.yml').exists()


async def test_write_templated_files_python_skips_test_main_when_established_tests(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(want_appimage=True,
                           want_pyinstaller=True,
                           want_tests=True,
                           want_main=True,
                           want_ai=False,
                           using_github=True,
                           supported_platforms='all',
                           _has_established_pytest_modules=True))
    assert (out / 'tests/conftest.py').exists()
    assert not (out / 'tests/test_main.py').exists()
    assert (out / '.github/workflows/pyinstaller.yml').exists()
    assert (out / '.github/workflows/appimage.yml').exists()


async def test_write_templated_files_python_stubs_only(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(stubs_only=True, want_tests=False, want_ai=False))
    assert not (out / 'mymod/__init__.py').exists()


async def test_write_templated_files_python_implicit_namespace_writes_qualified_init(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(primary_module='vendor',
                           primary_module_qualified='vendor.product.service',
                           want_tests=False,
                           want_ai=False))
    assert not (out / 'vendor/__init__.py').exists()
    assert (out / 'vendor/product/service/__init__.py').exists()


async def test_write_templated_files_python_namespace_workflow_paths_use_slashes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(primary_module='vendor',
                           primary_module_qualified='vendor.product.service',
                           modules=['vendor.product.service'],
                           want_appimage=True,
                           want_pyinstaller=True,
                           want_main=True,
                           want_tests=False,
                           want_ai=False,
                           using_github=True,
                           supported_platforms='all'))
    pyinstaller_yml = (out / '.github/workflows/pyinstaller.yml').read_text(encoding='utf-8')
    appimage_yml = (out / '.github/workflows/appimage.yml').read_text(encoding='utf-8')
    assert "- 'vendor/product/service/**'" in pyinstaller_yml
    assert 'vendor.product.service/**' not in pyinstaller_yml
    assert "- 'vendor/product/service/**'" in appimage_yml
    assert 'vendor.product.service/**' not in appimage_yml


async def test_write_templated_files_python_windows_only(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(want_main=True,
                           want_pyinstaller=True,
                           want_ai=False,
                           using_github=True,
                           supported_platforms=['windows']))
    assert (out / '.github/workflows/pyinstaller.yml').exists()
    assert not (out / '.github/workflows/appimage.yml').exists()


async def test_write_templated_files_python_linux_only(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(want_appimage=True,
                           want_main=True,
                           want_ai=False,
                           using_github=True,
                           supported_platforms=['linux']))
    assert (out / '.github/workflows/appimage.yml').exists()
    assert not (out / '.github/workflows/pyinstaller.yml').exists()


async def test_write_templated_files_python_multiple_entry_points(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(want_appimage=True,
                           want_pyinstaller=True,
                           want_main=False,
                           has_multiple_entry_points=True,
                           want_ai=False,
                           using_github=True,
                           supported_platforms='all'))
    assert (out / '.github/workflows/pyinstaller.yml').exists()
    assert (out / '.github/workflows/appimage.yml').exists()


async def test_write_templated_files_python_want_main_no_appimage(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(want_appimage=False,
                           want_pyinstaller=True,
                           want_main=True,
                           want_ai=False,
                           using_github=True,
                           supported_platforms='all'))
    assert (out / '.github/workflows/pyinstaller.yml').exists()
    assert not (out / '.github/workflows/appimage.yml').exists()


async def test_write_templated_files_cpp_want_main_writes_files(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(project_type='c++', want_main=True, want_ai=False))
    assert (out / 'CMakeLists.txt').exists()
    assert (out / 'src/CMakeLists.txt').exists()
    assert (out / 'src/main.cpp').exists()


async def test_write_templated_files_cpp_no_main(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(project_type='c++', want_main=False, want_ai=False))
    assert (out / 'CMakeLists.txt').exists()
    assert not (out / 'src/main.cpp').exists()


async def test_write_templated_files_c_want_main_writes_files(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(project_type='c', want_main=True, want_ai=False))
    assert (out / 'CMakeLists.txt').exists()
    assert (out / 'src/CMakeLists.txt').exists()
    assert (out / 'src/main.c').exists()


async def test_write_templated_files_c_no_main(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(project_type='c', want_main=False, want_ai=False))
    assert not (out / 'src/main.c').exists()


async def test_write_templated_files_lua_writes_files(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(project_type='lua', want_ai=False))
    assert (out / '.busted').exists()
    assert (out / '.luacov').exists()


async def test_write_templated_files_ts_stubs_only(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(project_type='typescript',
                           stubs_only=True,
                           want_tests=False,
                           want_ai=False))
    assert not (out / 'src/index.ts').exists()


async def test_write_templated_files_ts_with_tests(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(
            monkeypatch, tmp_path, module_path,
            _make_settings(project_type='typescript',
                           stubs_only=False,
                           want_tests=True,
                           want_ai=False))
    assert (out / 'src/index.ts').exists()
    assert (out / 'vitest.config.ts').exists()
    assert (out / 'eslint.config.mjs').exists()


async def test_write_templated_files_contributing_overwrite_poetry_with_uv(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = tmp_path / 'proj'
        out.mkdir()
        monkeypatch.chdir(out)
        before = 'Use uv sync to install\n'
        (out / 'CONTRIBUTING.md').write_text(before, encoding='utf-8')
        settings = _make_settings(package_manager='poetry', want_ai=False)
        await write_templated_files(module_path, cast('Any', settings))
        after = (out / 'CONTRIBUTING.md').read_text(encoding='utf-8')
        assert after != before


async def test_write_templated_files_contributing_no_overwrite_no_match(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = tmp_path / 'proj'
        out.mkdir()
        monkeypatch.chdir(out)
        text = 'Some unrelated content\n'
        (out / 'CONTRIBUTING.md').write_text(text, encoding='utf-8')
        settings = _make_settings(package_manager='uv', want_ai=False)
        await write_templated_files(module_path, cast('Any', settings))
        assert (out / 'CONTRIBUTING.md').read_text(encoding='utf-8') == text


async def test_write_templated_files_real_env_integration(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(project_type='generic', want_ai=True))
    assert (out / 'LICENSE.txt').exists()
    assert (out / 'SECURITY.md').exists()
    assert (out / 'CHANGELOG.md').exists()
    body = (out / 'CHANGELOG.md').read_text(encoding='utf-8')
    keep_url, semver_url = await resolve_changelog_boilerplate_urls(None)
    assert keep_url in body
    assert semver_url in body


async def test_write_templated_files_changelog_urls_use_resolved_boilerplate(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    mocker.patch('wiswa.tool.utils.templating.resolve_changelog_boilerplate_urls',
                 new_callable=AsyncMock,
                 return_value=('https://keepachangelog.com/en/9.9.9/',
                               'https://semver.org/spec/v9.9.9.html'))
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = tmp_path / 'proj'
        out.mkdir()
        monkeypatch.chdir(out)
        await write_templated_files(
            module_path, cast('Any', _make_settings(project_type='generic', want_ai=False)))
    body = (out / 'CHANGELOG.md').read_text(encoding='utf-8')
    assert 'https://keepachangelog.com/en/9.9.9/' in body
    assert 'https://semver.org/spec/v9.9.9.html' in body


async def test_write_templated_files_claude_changelog_agent_uses_resolved_keep_a_changelog_url(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    mocker.patch('wiswa.tool.utils.templating.resolve_changelog_boilerplate_urls',
                 new_callable=AsyncMock,
                 return_value=('https://keepachangelog.com/en/1.1.0/',
                               'https://semver.org/spec/v2.0.0.html'))
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = tmp_path / 'proj'
        out.mkdir()
        monkeypatch.chdir(out)
        (out / '.claude').mkdir()
        (out / '.claude' / 'agents').mkdir()
        (out / '.claude' / 'agents' / 'changelog.md').write_text(
            'stale content with https://keepachangelog.com/en/1.1.1/\n', encoding='utf-8')
        await write_templated_files(
            module_path, cast('Any', _make_settings(project_type='generic', want_ai=True)))
    body = (out / '.claude' / 'agents' / 'changelog.md').read_text(encoding='utf-8')
    assert 'https://keepachangelog.com/en/1.1.0/' in body
    assert 'https://keepachangelog.com/en/1.1.1/' not in body


async def test_write_templated_files_real_env_skips_existing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / 'proj'
    out.mkdir()
    (out / 'README.md').write_text('existing readme content\n', encoding='utf-8')
    (out / 'CHANGELOG.md').write_text('existing changelog\n', encoding='utf-8')
    monkeypatch.chdir(out)
    gen_settings = _make_settings(project_type='generic', want_ai=True)
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        await write_templated_files(module_path, cast('Any', gen_settings))
    assert (out / 'README.md').read_text(encoding='utf-8') == 'existing readme content\n'
    assert (out / 'CHANGELOG.md').read_text(encoding='utf-8') == 'existing changelog\n'


async def test_write_templated_files_real_env_with_session(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    mock_session = _stub_github_api_session()
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = tmp_path / 'proj'
        out.mkdir()
        monkeypatch.chdir(out)
        await write_templated_files(module_path,
                                    cast('Any', _make_settings(project_type='generic',
                                                               want_ai=False)),
                                    session=mock_session)
    mock_session.assert_not_called()


async def test_write_templated_files_claude_agents_skip_python_only_for_non_python(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    out = await _run_write(monkeypatch, tmp_path, module_path,
                           _make_settings(project_type='c++', want_ai=True))
    assert not (out / '.claude/agents/python-expert.md').exists()
    assert not (out / '.claude/rules/python.md').exists()
    assert (out / '.claude/agents/qa-fixer.md').exists()


async def test_write_templated_files_claude_skips_python_rule_when_stubs_only(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    out = await _run_write(monkeypatch, tmp_path, module_path,
                           _make_settings(want_ai=True, stubs_only=True))
    assert not (out / '.claude/rules/python.md').exists()
    assert (out / '.claude/rules/general.md').exists()


async def test_write_templated_files_claude_agents_ci_agent_without_vcs(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ShellCheck agent template is empty when neither GitHub nor GitLab is enabled."""
    module_path = _copy_wiswa_package(tmp_path)
    out = await _run_write(monkeypatch, tmp_path, module_path,
                           _make_settings(want_ai=True, using_github=False, using_gitlab=False))
    assert not (out / '.claude/agents/workflow-shellcheck.md').exists()
    assert (out / '.claude/agents/qa-fixer.md').exists()


async def test_write_templated_files_python_want_tests_no_main(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(want_tests=True, want_main=False, want_ai=False))
    assert (out / 'tests/conftest.py').exists()
    assert not (out / 'tests/test_main.py').exists()


async def test_write_templated_files_non_mit_skips_license(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(license='GPL-3.0', want_ai=False))
    assert not (out / 'LICENSE.txt').exists()


async def test_write_templated_files_mit_writes_license(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    with importlib.resources.as_file(importlib.resources.files('wiswa.tool')) as module_path:
        out = await _run_write(monkeypatch, tmp_path, module_path,
                               _make_settings(license='MIT', want_ai=False))
    assert (out / 'LICENSE.txt').exists()


async def test_write_cleanup_skips_missing_agents_template(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    (module_path / 'templates/AGENTS.md.j2').unlink()
    await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=False))


async def test_write_cleanup_when_claude_rules_directory_absent(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    shutil.rmtree(module_path / 'templates/claude/rules')
    await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=False))


async def test_write_cleanup_cpp_skips_python_only_agent_templates(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / 'proj'
    out.mkdir()
    monkeypatch.chdir(out)
    module_path = _copy_wiswa_package(tmp_path)
    settings_on = _make_settings(want_ai=True, project_type='c++')
    settings_off = _make_settings(want_ai=False, project_type='c++')
    await write_templated_files(module_path, cast('Any', settings_on))
    await write_templated_files(module_path, cast('Any', settings_off))


async def test_write_claude_outputs_when_rules_directory_absent(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    shutil.rmtree(module_path / 'templates/claude/rules')
    out = await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=True))
    assert (out / '.claude/agents/regen.md').exists()


async def test_write_claude_skills_non_j2_inside_skill_directory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    (module_path / 'templates/claude/skills/ci/notes.txt').write_text('extra', encoding='utf-8')
    out = await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=True))
    assert (out / '.claude/skills/ci/SKILL.md').exists()
    assert not (out / '.claude/skills/ci/notes.txt').exists()


async def test_cleanup_when_claude_agents_template_dir_absent(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    shutil.rmtree(module_path / 'templates/claude/agents')
    await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=False))


async def test_cleanup_when_claude_skills_template_dir_absent(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    shutil.rmtree(module_path / 'templates/claude/skills')
    await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=False))


async def test_cleanup_skips_non_j2_in_agents_template_dir(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    (module_path / 'templates/claude/agents/notes.txt').write_text('not rendered', encoding='utf-8')
    out = tmp_path / 'proj'
    out.mkdir()
    monkeypatch.chdir(out)
    settings_on = _make_settings(want_ai=True)
    settings_off = _make_settings(want_ai=False)
    await write_templated_files(module_path, cast('Any', settings_on))
    await write_templated_files(module_path, cast('Any', settings_off))


async def test_cleanup_skills_ignores_non_j2_beside_templates(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    (module_path / 'templates/claude/skills/ci/notes.txt').write_text('extra', encoding='utf-8')
    out = tmp_path / 'proj'
    out.mkdir()
    monkeypatch.chdir(out)
    settings_on = _make_settings(want_ai=True)
    settings_off = _make_settings(want_ai=False)
    await write_templated_files(module_path, cast('Any', settings_on))
    await write_templated_files(module_path, cast('Any', settings_off))
    assert not (out / '.claude/skills/ci/SKILL.md').exists()


async def test_write_claude_skips_non_j2_in_agents_template_dir(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    (module_path / 'templates/claude/agents/notes.txt').write_text('stray', encoding='utf-8')
    out = await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=True))
    assert (out / '.claude/agents/regen.md').exists()
    assert not (out / '.claude/agents/notes.txt').exists()


async def test_write_claude_when_skills_template_dir_absent(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = _copy_wiswa_package(tmp_path)
    shutil.rmtree(module_path / 'templates/claude/skills')
    out = await _run_write(monkeypatch, tmp_path, module_path, _make_settings(want_ai=True))
    assert (out / '.claude/agents/regen.md').exists()
    assert (out / 'CLAUDE.md').exists()
    assert not (out / '.claude/skills').exists()
