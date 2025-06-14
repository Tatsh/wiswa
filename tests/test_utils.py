from __future__ import annotations

from contextlib import chdir
from pathlib import Path
from typing import TYPE_CHECKING, Any
import json

from wiswa import utils
import pytest
import requests

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize(
    ('content', 'expected'),
    [
        ('', False),
        ('   ', False),
        ('foo', True),
        ('\nbar\n', True),
    ],
)
def test_non_empty_file_exists(tmp_path: Path, content: str,
                               expected: bool) -> None:  # noqa: FBT001
    file_path = tmp_path / 'file.txt'
    if content:
        file_path.write_text(content)
    else:
        file_path.touch()
    assert utils.non_empty_file_exists(file_path) is expected


def test_copy_static_files_skips_when_stubs_only(mocker: MockerFixture, tmp_path: Path) -> None:
    settings = {'stubs_only': True, 'primary_module': 'foo', 'want_main': False}
    module_path = tmp_path
    copyfile = mocker.patch('wiswa.utils.copyfile')
    utils.copy_static_files(settings, module_path)
    copyfile.assert_not_called()


def test_copy_static_files_copies_files(mocker: MockerFixture, tmp_path: Path) -> None:
    settings = {'stubs_only': False, 'primary_module': 'foo', 'want_main': True}
    module_path = tmp_path
    static_dir = module_path / 'static'
    static_dir.mkdir(parents=True)
    (static_dir / 'utils.py').write_text('x')
    (static_dir / '__main__.py').write_text('y')
    (static_dir / 'main.py').write_text('z')
    mocker.patch('wiswa.utils.non_empty_file_exists', return_value=False)
    copyfile = mocker.patch('wiswa.utils.copyfile')
    utils.copy_static_files(settings, module_path)
    assert copyfile.call_count == 3


def test_create_py_typed_files_creates_files(tmp_path: Path, mocker: MockerFixture) -> None:
    settings = {
        'pyproject': {
            'tool': {
                'poetry': {
                    'packages': [{
                        'include': str(tmp_path / 'foo')
                    }, {
                        'include': str(tmp_path / 'bar')
                    }]
                }
            }
        }
    }
    logger = mocker.patch('wiswa.utils.log')
    utils.create_py_typed_files(settings)
    assert (tmp_path / 'foo' / 'py.typed').exists()
    assert (tmp_path / 'bar' / 'py.typed').exists()
    assert logger.debug.call_count == 2


def test_subprocess_log_run_logs_and_runs(mocker: MockerFixture) -> None:
    mock_run = mocker.patch('wiswa.utils.sp.run')
    logger = mocker.patch('wiswa.utils.log')
    utils.subprocess_log_run(['echo', 'hi'])
    logger.debug.assert_called()
    mock_run.assert_called()


def test_download_yarn_plugins_writes_file(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_response = mocker.Mock()
    mock_response.text = 'plugin code'
    mock_response.raise_for_status = lambda: None
    mocker.patch('wiswa.utils.requests.get', return_value=mock_response)
    mocker.patch('wiswa.utils.PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI', 'http://example.com')
    plugins_dir = tmp_path / '.yarn' / 'plugins'
    mocker.patch('wiswa.utils.Path',
                 side_effect=lambda x=None: plugins_dir if x == '.yarn/plugins' else Path(x))
    utils.download_yarn_plugins()
    file_path = plugins_dir / 'plugin-prettier-after-all-installed.cjs'
    assert file_path.exists()
    assert file_path.read_text().strip() == 'plugin code'


def test_evaluate_merged_settings_reads_and_merges(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch('wiswa.utils._jsonnet.evaluate_snippet', return_value='{"foo": "bar"}')
    lib_path = tmp_path
    defaults = tmp_path / 'defaults.libjsonnet'
    file = tmp_path / 'settings.jsonnet'
    defaults.write_text('{}')
    file.write_text('{}')
    s, d = utils.evaluate_merged_settings([], lib_path, file)
    assert s == '{"foo": "bar"}'
    assert d == {'foo': 'bar'}


def test_download_yarn_writes_file(mocker: MockerFixture, tmp_path: Path) -> None:
    mock_response = mocker.Mock()
    mock_response.text = 'yarn code'
    mock_response.raise_for_status = lambda: None
    mocker.patch('wiswa.utils.requests.get', return_value=mock_response)
    mocker.patch('wiswa.utils.rmtree')
    mocker.patch('wiswa.utils.Path',
                 side_effect=lambda x=None: tmp_path / '.yarn' / 'releases'
                 if x == '.yarn/releases' else Path(x))
    utils.download_yarn('v1.2.3')
    file_path = tmp_path / '.yarn' / 'releases' / 'yarn-v1.2.3.cjs'
    assert file_path.exists()
    assert file_path.read_text().strip() == 'yarn code'


def test_post_process_steps_removes_tests_when_want_tests_false(mocker: MockerFixture,
                                                                tmp_path: Path) -> None:
    settings = {
        'want_tests': False,
        'want_docs': True,
        'want_codeql': True,
        'want_man': False,
        'want_yapf': True,
        'vscode': {
            'launch': {
                'configurations': [{
                    'name': 'Run tests'
                }]
            }
        },
        'primary_module': 'foo'
    }
    (tmp_path / 'tests').mkdir()
    (tmp_path / '.github').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.github' / 'workflows').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.github' / 'workflows' / 'tests.yml').touch()
    (tmp_path / '.vscode').mkdir()
    (tmp_path / '.vscode' / 'launch.json').touch()
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.poetry.group.tests]\n[tool.coverage]\n[tool.pytest]\n[tool.poetry.group.docs]\n')
    (tmp_path / 'package.json').write_text('{}')
    rmtree = mocker.spy(utils, 'rmtree')
    mocker.patch('wiswa.utils.Path', side_effect=lambda x=None: tmp_path / x if x else tmp_path)
    mocker.patch('wiswa.utils.subprocess_log_run')
    mocker.patch(
        'wiswa.utils.tomlkit.loads',
        side_effect=lambda _: mocker.Mock(unwrap=lambda: {
            'tool': {
                'poetry': {
                    'group': {
                        'tests': {},
                        'docs': {}
                    }
                },
                'coverage': {},
                'pytest': {}
            }
        }))
    mocker.patch('wiswa.utils.tomlkit.dumps', return_value='[tool.poetry]\n')
    mocker.patch('wiswa.utils.json.loads', return_value={})
    mocker.patch('wiswa.utils.json.dumps', return_value='{}')
    mocker.patch('wiswa.utils.PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI', 'http://example.com')
    with chdir(tmp_path):
        utils.post_process_steps(settings)
    rmtree.assert_any_call('tests', ignore_errors=True)
    assert (tmp_path / 'tests').exists() is False
    assert (tmp_path / '.github' / 'workflows' / 'tests.yml').exists() is False
    assert (tmp_path / '.vscode' / 'launch.json').exists() is False


def test_post_process_steps_removes_docs_when_want_docs_false(mocker: MockerFixture,
                                                              tmp_path: Path) -> None:
    settings = {
        'want_tests': True,
        'want_docs': False,
        'want_codeql': True,
        'want_man': False,
        'want_yapf': True,
        'vscode': {
            'launch': {
                'configurations': [{
                    'name': 'Run tests'
                }]
            }
        },
        'primary_module': 'foo'
    }
    (tmp_path / 'docs').mkdir()
    (tmp_path / '.readthedocs.yaml').touch()
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.poetry.group.docs]\n[tool.poetry.group.tests]\n[tool.coverage]\n[tool.pytest]\n')
    (tmp_path / 'package.json').write_text('{}')
    rmtree = mocker.spy(utils, 'rmtree')
    mocker.patch('wiswa.utils.Path', side_effect=lambda x=None: tmp_path / x if x else tmp_path)
    mocker.patch('wiswa.utils.subprocess_log_run')
    mocker.patch(
        'wiswa.utils.tomlkit.loads',
        side_effect=lambda _: mocker.Mock(unwrap=lambda: {
            'tool': {
                'poetry': {
                    'group': {
                        'tests': {},
                        'docs': {}
                    }
                },
                'coverage': {},
                'pytest': {}
            }
        }))
    mocker.patch('wiswa.utils.tomlkit.dumps', return_value='[tool.poetry]\n')
    mocker.patch('wiswa.utils.json.loads', return_value={})
    mocker.patch('wiswa.utils.json.dumps', return_value='{}')
    mocker.patch('wiswa.utils.PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI', 'http://example.com')
    with chdir(tmp_path):
        utils.post_process_steps(settings)
    rmtree.assert_any_call('docs', ignore_errors=True)
    assert (tmp_path / 'docs').exists() is False
    assert (tmp_path / '.readthedocs.yaml').exists() is False


def test_post_process_steps_removes_codeql_when_want_codeql_false(mocker: MockerFixture,
                                                                  tmp_path: Path) -> None:
    settings = {
        'want_tests': True,
        'want_docs': True,
        'want_codeql': False,
        'want_man': False,
        'want_yapf': True,
        'vscode': {
            'launch': {
                'configurations': [{
                    'name': 'Run tests'
                }]
            }
        },
        'primary_module': 'foo'
    }
    (tmp_path / '.github' / 'workflows').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.github' / 'workflows' / 'codeql.yml').touch()
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.poetry.group.docs]\n[tool.poetry.group.tests]\n[tool.coverage]\n[tool.pytest]\n')
    (tmp_path / 'package.json').write_text('{}')
    mocker.patch('wiswa.utils.Path', side_effect=lambda x=None: tmp_path / x if x else tmp_path)
    mocker.patch('wiswa.utils.subprocess_log_run')
    mocker.patch(
        'wiswa.utils.tomlkit.loads',
        side_effect=lambda _: mocker.Mock(unwrap=lambda: {
            'tool': {
                'poetry': {
                    'group': {
                        'tests': {},
                        'docs': {}
                    }
                },
                'coverage': {},
                'pytest': {}
            }
        }))
    mocker.patch('wiswa.utils.tomlkit.dumps', return_value='[tool.poetry]\n')
    mocker.patch('wiswa.utils.json.loads', return_value={})
    mocker.patch('wiswa.utils.json.dumps', return_value='{}')
    mocker.patch('wiswa.utils.PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI', 'http://example.com')
    with chdir(tmp_path):
        utils.post_process_steps(settings)
    assert (tmp_path / '.github' / 'workflows' / 'codeql.yml').exists() is False


@pytest.mark.parametrize('man_exists', [True, False])
def test_post_process_steps_want_man_adds_version_files(mocker: MockerFixture, tmp_path: Path,
                                                        man_exists: bool) -> None:  # noqa: FBT001
    settings = {
        'want_tests': True,
        'want_docs': True,
        'want_codeql': True,
        'want_man': True,
        'want_yapf': True,
        'vscode': {
            'launch': {
                'configurations': [{
                    'name': 'Run tests'
                }]
            }
        },
        'primary_module': 'foo'
    }
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.poetry.group.docs]\n[tool.poetry.group.tests]\n[tool.coverage]\n[tool.pytest]\n')
    (tmp_path / 'package.json').write_text('{}')
    # Prepare .github/workflows directory to avoid errors
    (tmp_path / '.github' / 'workflows').mkdir(parents=True, exist_ok=True)
    # Prepare man directory and files if needed
    if man_exists:
        man_dir = tmp_path / 'man'
        man_dir.mkdir()
        (man_dir / 'foo.1').write_text('man page')
        (man_dir / 'bar.1').write_text('man page')
    # Patch Path to use tmp_path as root
    mocker.patch('wiswa.utils.Path', side_effect=lambda x=None: tmp_path / x if x else tmp_path)
    mocker.patch('wiswa.utils.subprocess_log_run')
    # Patch tomlkit.loads to return a mock with unwrap returning a dict with version_files
    version_files = ['foo/__init__.py']
    pyproject_dict = {
        'tool': {
            'poetry': {
                'group': {
                    'tests': {},
                    'docs': {}
                }
            },
            'coverage': {},
            'pytest': {},
            'commitizen': {
                'version_files': version_files.copy()
            }
        }
    }
    mocker.patch('wiswa.utils.tomlkit.loads',
                 side_effect=lambda _: mocker.Mock(unwrap=lambda: pyproject_dict))
    mocker.patch('wiswa.utils.tomlkit.dumps', return_value='[tool.poetry]\n')
    mocker.patch('wiswa.utils.json.loads', return_value={})
    mocker.patch('wiswa.utils.json.dumps', return_value='{}')
    mocker.patch('wiswa.utils.PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI', 'http://example.com')
    with chdir(tmp_path):
        utils.post_process_steps(settings)
    # Check that version_files was updated correctly
    if man_exists:
        expected_files = sorted(
            set(version_files + [str(p) for p in (tmp_path / 'man').glob('*.1')]))
        actual_files = sorted(pyproject_dict['tool']['commitizen']['version_files'])
        assert actual_files == expected_files
    else:
        expected_files = sorted({*version_files, f'man/{settings["primary_module"]}.1'})
        actual_files = sorted(pyproject_dict['tool']['commitizen']['version_files'])
        assert actual_files == expected_files


def test_post_process_steps_removes_yapf_when_want_yapf_false(mocker: MockerFixture,
                                                              tmp_path: Path) -> None:
    settings = {
        'want_tests': True,
        'want_docs': True,
        'want_codeql': True,
        'want_man': False,
        'want_yapf': False,
        'vscode': {
            'launch': {
                'configurations': [{
                    'name': 'Run tests'
                }]
            }
        },
        'primary_module': 'foo'
    }
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.poetry.group.docs]\n[tool.poetry.group.tests]\n[tool.coverage]\n[tool.pytest]\n'
        '[tool.yapf]\n[tool.yapfignore]\n')
    (tmp_path / 'package.json').write_text('{}')
    mocker.patch('wiswa.utils.Path', side_effect=lambda x=None: tmp_path / x if x else tmp_path)
    mocker.patch('wiswa.utils.subprocess_log_run')
    pyproject_dict: dict[str, Any] = {
        'tool': {
            'poetry': {
                'group': {
                    'tests': {},
                    'docs': {}
                }
            },
            'coverage': {},
            'pytest': {},
            'yapf': {},
            'yapfignore': {},
        }
    }
    package_json_dict: dict[str, Any] = {}
    mocker.patch('wiswa.utils.tomlkit.loads',
                 side_effect=lambda _: mocker.Mock(unwrap=lambda: pyproject_dict))
    mocker.patch('wiswa.utils.tomlkit.dumps', return_value='[tool.poetry]\n')
    mocker.patch('wiswa.utils.json.loads', return_value=package_json_dict)
    mocker.patch('wiswa.utils.json.dumps', return_value='{}')
    mocker.patch('wiswa.utils.PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI', 'http://example.com')
    with chdir(tmp_path):
        utils.post_process_steps(settings)
    assert 'yapf' not in pyproject_dict['tool']
    assert 'yapfignore' not in pyproject_dict['tool']
    assert 'check-formatting' in package_json_dict
    assert 'format' in package_json_dict


def test_write_templated_files_writes_test_files(mocker: MockerFixture, tmp_path: Path) -> None:
    settings = {
        'want_tests': True,
        'want_main': True,
        'want_docs': False,
    }
    module_path = tmp_path
    templates_dir = module_path / 'templates'
    (templates_dir / 'tests').mkdir(parents=True)
    (templates_dir / 'tests/conftest.py.j2').touch()
    (templates_dir / 'tests/test_utils.py.j2').touch()
    (templates_dir / 'tests/test_main.py.j2').touch()
    env_mock = mocker.Mock()
    template_mock = mocker.Mock()
    template_mock.render.return_value = 'file content'
    env_mock.get_template.return_value = template_mock
    mocker.patch('wiswa.utils.jinja2.Environment', return_value=env_mock)
    mocker.patch('wiswa.utils.jinja2.PackageLoader')
    mocker.patch('wiswa.utils.ToPythonExtension')
    mocker.patch('wiswa.utils.non_empty_file_exists', return_value=False)
    utils.write_templated_files(module_path, settings)
    # Should attempt to render and write all three test files
    assert template_mock.render.call_count >= 3


def test_write_templated_files_writes_docs_files(mocker: MockerFixture, tmp_path: Path) -> None:
    settings = {
        'want_tests': False,
        'want_main': False,
        'want_docs': True,
    }
    module_path = tmp_path
    templates_dir = module_path / 'templates'
    (templates_dir / 'docs').mkdir(parents=True)
    (templates_dir / 'docs/conf.py.j2').touch()
    (templates_dir / 'docs/index.rst.j2').touch()
    (templates_dir / 'CHANGELOG.md.j2').touch()
    (templates_dir / 'README.md.j2').touch()
    env_mock = mocker.Mock()
    template_mock = mocker.Mock()
    template_mock.render.return_value = 'doc content'
    env_mock.get_template.return_value = template_mock
    mocker.patch('wiswa.utils.jinja2.Environment', return_value=env_mock)
    mocker.patch('wiswa.utils.jinja2.PackageLoader')
    mocker.patch('wiswa.utils.ToPythonExtension')
    mocker.patch('wiswa.utils.non_empty_file_exists', return_value=False)
    utils.write_templated_files(module_path, settings)
    # Should render and write docs files
    assert template_mock.render.call_count >= 4


def test_evaluate_jsonnet_project_creates_files(mocker: MockerFixture, tmp_path: Path) -> None:
    # Prepare mock for _jsonnet.evaluate_file
    output_dict = {
        str(tmp_path / 'file1.txt'): 'content1',
        str(tmp_path / 'dir/file2.txt'): 'content2'
    }
    mocker.patch('wiswa.utils._jsonnet.evaluate_file', return_value=json.dumps(output_dict))
    logger = mocker.patch('wiswa.utils.log')
    lib_path = tmp_path
    merged_settings = '{}'
    utils.evaluate_jsonnet_project(lib_path, [], merged_settings)
    file1 = tmp_path / 'file1.txt'
    file2 = tmp_path / 'dir' / 'file2.txt'
    assert file1.exists()
    assert file2.exists()
    assert file1.read_text().strip() == 'content1'
    assert file2.read_text().strip() == 'content2'
    assert logger.debug.call_count == 2


def test_evaluate_jsonnet_project_strips_and_newlines(mocker: MockerFixture,
                                                      tmp_path: Path) -> None:
    # Output with extra whitespace
    output_dict = {str(tmp_path / 'foo.txt'): '  foo content  \n\n'}
    mocker.patch('wiswa.utils._jsonnet.evaluate_file', return_value=json.dumps(output_dict))
    logger = mocker.patch('wiswa.utils.log')
    utils.evaluate_jsonnet_project(tmp_path, [], '{}')
    file_path = tmp_path / 'foo.txt'
    assert file_path.exists()
    # Should be stripped and end with a single newline
    assert file_path.read_text() == 'foo content\n'
    logger.debug.assert_called_with('Wrote `%s`.', file_path)


def test_evaluate_jsonnet_project_handles_empty_output(mocker: MockerFixture,
                                                       tmp_path: Path) -> None:
    mocker.patch('wiswa.utils._jsonnet.evaluate_file', return_value=json.dumps({}))
    logger = mocker.patch('wiswa.utils.log')
    utils.evaluate_jsonnet_project(tmp_path, [], '{}')
    # No files should be created
    assert not any(tmp_path.iterdir())
    logger.debug.assert_not_called()


def make_settings(**overrides: Any) -> dict[str, Any]:
    settings = {
        'using_github': True,
        'repository_uri': 'https://github.com/owner/project',
        'description': 'Test repo',
        'homepage': 'https://example.com',
        'keywords': ['foo', 'bar baz'],
        'default_branch': 'main',
    }
    return settings | overrides


def test_setup_github_project_not_using_github(mocker: MockerFixture) -> None:
    settings = make_settings(using_github=False)
    logger = mocker.patch('wiswa.utils.log')
    utils.setup_github_project(settings)
    logger.debug.assert_called_with('Not running Github setup.')


def test_setup_github_project_no_token(mocker: MockerFixture) -> None:
    settings = make_settings()
    mocker.patch('wiswa.utils.keyring.get_password', return_value=None)
    logger = mocker.patch('wiswa.utils.log')
    utils.setup_github_project(settings)
    logger.warning.assert_called_with('No Github token.')


def test_setup_github_project_successful_patch_and_puts(mocker: MockerFixture) -> None:
    settings = make_settings()
    mocker.patch('wiswa.utils.keyring.get_password', return_value='token')
    session_mock = mocker.Mock()
    patch = session_mock.patch
    put = session_mock.put
    get = session_mock.get
    post = session_mock.post
    patch.return_value.raise_for_status = lambda: None
    put.return_value.raise_for_status = lambda: None
    post.return_value.raise_for_status = lambda: None
    get.side_effect = [
        mocker.Mock(status_code=200, json=lambda: [{
            'name': 'Other ruleset'
        }]),  # rulesets
        mocker.Mock(status_code=200),  # pages
    ]
    mocker.patch('wiswa.utils.requests.Session', return_value=session_mock)
    utils.setup_github_project(settings)
    assert patch.called
    assert put.call_count >= 3
    assert get.call_count >= 2


def test_setup_github_project_adds_rulesets_and_pages(mocker: MockerFixture) -> None:
    settings = make_settings()
    mocker.patch('wiswa.utils.keyring.get_password', return_value='token')
    session_mock = mocker.Mock()
    patch = session_mock.patch
    put = session_mock.put
    get = session_mock.get
    post = session_mock.post
    patch.return_value.raise_for_status = lambda: None
    put.return_value.raise_for_status = lambda: None
    post.return_value.raise_for_status = lambda: None
    # Simulate no rulesets and no pages
    get.side_effect = [
        mocker.Mock(status_code=200, json=list),  # rulesets
        mocker.Mock(status_code=404),  # pages
    ]
    mocker.patch('wiswa.utils.requests.Session', return_value=session_mock)
    utils.setup_github_project(settings)
    # Should add both rulesets and pages
    assert post.call_count >= 3
    post_calls = [call.args[0] for call in post.call_args_list]
    assert any('/rulesets' in url for url in post_calls)
    assert any('/pages' in url for url in post_calls)


def test_setup_github_project_handles_http_error(mocker: MockerFixture) -> None:
    settings = make_settings()
    mocker.patch('wiswa.utils.keyring.get_password', return_value='token')
    session_mock = mocker.Mock()
    error = requests.HTTPError(response=mocker.MagicMock(text='fail'))
    session_mock.patch.side_effect = error
    mocker.patch('wiswa.utils.requests.Session', return_value=session_mock)
    logger = mocker.patch('wiswa.utils.log')
    utils.setup_github_project(settings)
    logger.warning.assert_called_with('Caught error updating repo: %s.', 'fail')


@pytest.mark.parametrize(
    'ruleset_names',
    [
        (['Other ruleset', 'Protect version tags']),  # Only 'Protect default branch' missing
        ([]),  # Both missing, but we only care about 'Protect default branch'
    ],
)
def test_setup_github_project_adds_protect_default_branch_ruleset(mocker: MockerFixture,
                                                                  ruleset_names: list[str]) -> None:
    settings = {
        'using_github': True,
        'repository_uri': 'https://github.com/owner/project',
        'description': 'desc',
        'homepage': 'https://example.com',
        'keywords': ['foo'],
        'default_branch': 'main',
    }
    mocker.patch('wiswa.utils.keyring.get_password', return_value='token')
    session_mock = mocker.Mock()
    patch = session_mock.patch
    put = session_mock.put
    get = session_mock.get
    post = session_mock.post
    patch.return_value.raise_for_status = lambda: None
    put.return_value.raise_for_status = lambda: None
    post.return_value.raise_for_status = lambda: None
    # First get returns rulesets, second get returns pages (simulate exists)
    get.side_effect = [
        mocker.Mock(status_code=200, json=lambda: [{
            'name': n
        } for n in ruleset_names]),
        mocker.Mock(status_code=200),
    ]
    mocker.patch('wiswa.utils.requests.Session', return_value=session_mock)
    utils.setup_github_project(settings)
    # Should call post to add 'Protect default branch'
    post_urls = [call.args[0] for call in post.call_args_list]
    assert any('/rulesets' in url for url in post_urls)
    # Should include a ruleset with name 'Protect default branch'
    found = False
    for call in post.call_args_list:
        if '/rulesets' in call.args[0]:
            json_arg = call.kwargs.get('json', {})
            if json_arg.get('name') == 'Protect default branch':
                found = True
    assert found


def test_post_process_steps_removes_tests_and_vscode_launch_when_want_tests_false_and_vscode_launch(
        mocker: MockerFixture, tmp_path: Path) -> None:
    settings = {
        'want_tests': False,
        'want_docs': True,
        'want_codeql': True,
        'want_man': False,
        'want_yapf': True,
        'vscode': {
            'launch': {
                'configurations': [{
                    'name': 'Run tests'
                }, {
                    'name': 'Other config'
                }]
            }
        },
        'primary_module': 'foo'
    }
    (tmp_path / 'tests').mkdir()
    (tmp_path / '.github').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.github' / 'workflows').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.github' / 'workflows' / 'tests.yml').touch()
    (tmp_path / '.vscode').mkdir()
    (tmp_path / '.vscode' / 'launch.json').touch()
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.poetry.group.tests]\n[tool.coverage]\n[tool.pytest]\n[tool.poetry.group.docs]\n')
    (tmp_path / 'package.json').write_text('{}')
    rmtree = mocker.spy(utils, 'rmtree')
    mocker.patch('wiswa.utils.Path', side_effect=lambda x=None: tmp_path / x if x else tmp_path)
    mocker.patch('wiswa.utils.subprocess_log_run')
    mocker.patch(
        'wiswa.utils.tomlkit.loads',
        side_effect=lambda _: mocker.Mock(unwrap=lambda: {
            'tool': {
                'poetry': {
                    'group': {
                        'tests': {},
                        'docs': {}
                    }
                },
                'coverage': {},
                'pytest': {}
            }
        }))
    mocker.patch('wiswa.utils.tomlkit.dumps', return_value='[tool.poetry]\n')
    mocker.patch('wiswa.utils.json.loads', return_value={})
    mocker.patch('wiswa.utils.json.dumps', return_value='{}')
    mocker.patch('wiswa.utils.PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI', 'http://example.com')
    with chdir(tmp_path):
        utils.post_process_steps(settings)
    rmtree.assert_any_call('tests', ignore_errors=True)
    assert not (tmp_path / 'tests').exists()
    assert not (tmp_path / '.github' / 'workflows' / 'tests.yml').exists()
    # launch.json should still exist because there is more than one configuration
    assert (tmp_path / '.vscode' / 'launch.json').exists()


def test_copy_static_files_skips_existing_files(mocker: MockerFixture, tmp_path: Path) -> None:
    settings = {'stubs_only': False, 'primary_module': 'foo', 'want_main': True}
    module_path = tmp_path
    static_dir = module_path / 'static'
    static_dir.mkdir(parents=True)
    (static_dir / 'utils.py').write_text('x')
    (static_dir / '__main__.py').write_text('y')
    (static_dir / 'main.py').write_text('z')
    # Simulate that all output files already exist and are non-empty
    mocker.patch('wiswa.utils.non_empty_file_exists', return_value=True)
    copyfile = mocker.patch('wiswa.utils.copyfile')
    logger = mocker.patch('wiswa.utils.log')
    utils.copy_static_files(settings, module_path)
    # No files should be copied
    copyfile.assert_not_called()
    # Should log skipping for each file
    assert logger.debug.call_count >= 1
    calls = [call.args[0] for call in logger.debug.call_args_list]
    assert any('Skipping' in msg for msg in calls)


def test_copy_static_files_want_main_false(mocker: MockerFixture, tmp_path: Path) -> None:
    settings = {'stubs_only': False, 'primary_module': 'foo', 'want_main': False}
    module_path = tmp_path
    static_dir = module_path / 'static'
    static_dir.mkdir(parents=True)
    (static_dir / 'utils.py').write_text('x')
    mocker.patch('wiswa.utils.non_empty_file_exists', return_value=False)
    copyfile = mocker.patch('wiswa.utils.copyfile')
    utils.copy_static_files(settings, module_path)
    assert copyfile.call_count == 1
    args, _ = copyfile.call_args
    assert static_dir / 'utils.py' in args


def test_write_templated_files_skips_when_file_exists(mocker: MockerFixture,
                                                      tmp_path: Path) -> None:
    settings = {
        'want_tests': True,
        'want_main': False,
        'want_docs': False,
    }
    module_path = tmp_path
    templates_dir = module_path / 'templates'
    (templates_dir / 'tests').mkdir(parents=True)
    (templates_dir / 'tests/conftest.py.j2').touch()
    env_mock = mocker.Mock()
    template_mock = mocker.Mock()
    template_mock.render.return_value = 'should not be written'
    env_mock.get_template.return_value = template_mock
    mocker.patch('wiswa.utils.jinja2.Environment', return_value=env_mock)
    mocker.patch('wiswa.utils.jinja2.PackageLoader')
    mocker.patch('wiswa.utils.ToPythonExtension')
    mocker.patch('wiswa.utils.non_empty_file_exists', return_value=True)
    logger = mocker.patch('wiswa.utils.log')
    utils.write_templated_files(module_path, settings)
    logger.debug.assert_any_call('Skipping template `%s`.', Path('tests/conftest.py'))


def test_setup_github_project_does_not_add_protect_default_branch_if_exists(
        mocker: MockerFixture) -> None:
    settings = {
        'using_github': True,
        'repository_uri': 'https://github.com/owner/project',
        'description': 'desc',
        'homepage': 'https://example.com',
        'keywords': ['foo'],
        'default_branch': 'main',
    }
    mocker.patch('wiswa.utils.keyring.get_password', return_value='token')
    session_mock = mocker.Mock()
    patch = session_mock.patch
    put = session_mock.put
    get = session_mock.get
    post = session_mock.post
    patch.return_value.raise_for_status = lambda: None
    put.return_value.raise_for_status = lambda: None
    post.return_value.raise_for_status = lambda: None
    # First get returns rulesets including 'Protect default branch', second get returns pages
    get.side_effect = [
        mocker.Mock(status_code=200,
                    json=lambda: [
                        {
                            'name': 'Other ruleset'
                        },
                        {
                            'name': 'Protect default branch'
                        },
                    ]),
        mocker.Mock(status_code=200),
    ]
    mocker.patch('wiswa.utils.requests.Session', return_value=session_mock)
    utils.setup_github_project(settings)
    # Should not call post to add 'Protect default branch'
    post_urls = [call.args[0] for call in post.call_args_list]
    assert not any(
        '/rulesets' in url and call.kwargs.get('json', {}).get('name') == 'Protect default branch'
        for url, call in zip(post_urls, post.call_args_list, strict=False))
