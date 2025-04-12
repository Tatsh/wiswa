"""Utilities."""
from __future__ import annotations

from collections.abc import Iterable
from http import HTTPStatus
from pathlib import Path
from shlex import quote
from shutil import copyfile, rmtree
from typing import Any, cast
import getpass
import json
import logging
import subprocess as sp

from github import Auth, Github
import _jsonnet  # type: ignore[import-not-found] # noqa: PLC2701
import jinja2
import keyring
import requests

from .constants import PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI, STATIC_MODULE_FILES
from .extensions import ToPythonExtension

__all__ = ('copy_static_files', 'create_py_typed_files', 'download_yarn_plugins',
           'evaluate_jsonnet_project', 'evaluate_merged_settings', 'post_process_steps',
           'write_templated_files')

log = logging.getLogger(__name__)


def subprocess_log_run(*args: Any, **kwargs: Any) -> sp.CompletedProcess[Any]:
    """Run a subprocess and log its output."""
    assert isinstance(args[0], Iterable)
    log.debug('Running command: %s', ' '.join(quote(x) for x in args[0]))
    return sp.run(*args, check=kwargs.pop('check', True), **kwargs)


def post_process_steps(settings: dict[str, Any]) -> None:
    """Run post-processing steps."""
    if not settings['want_tests']:
        rmtree('tests', ignore_errors=True)
        Path('.github/workflows/tests.yml').unlink(missing_ok=True)
        if (not settings['vscode']['launch']
                or (len(settings['vscode']['launch']['configurations']) == 1
                    and settings['vscode']['launch']['configurations'][0]['name'] == 'Run tests')):
            Path('.vscode/launch.json').unlink(missing_ok=True)
    if not settings['want_docs']:
        rmtree('docs', ignore_errors=True)
        Path('.readthedocs.yaml').unlink(missing_ok=True)
    if settings['stubs_only']:
        Path('.github/workflows/codeql.yml').unlink(missing_ok=True)
    subprocess_log_run(('poetry', 'lock'), check=True)
    with_arg = ','.join(
        ('docs' if settings['want_docs'] else '', 'tests' if settings['want_tests'] else ''))
    subprocess_log_run(('poetry', 'update', *((f'--with={with_arg}',) if with_arg != ',' else ())),
                       check=True)
    subprocess_log_run(('poetry', 'install', '--all-groups'), check=True)
    subprocess_log_run(('yarn',))
    subprocess_log_run(('yarn', 'format'))
    subprocess_log_run(('poetry', 'run', 'ruff', 'check', '--fix'), check=False)


def create_py_typed_files(settings: dict[str, Any]) -> None:
    """Create ``py.typed`` files for all packages."""
    for path in (Path(x['include']) for x in settings['pyproject']['tool']['poetry']['packages']):
        path.mkdir(parents=True, exist_ok=True)
        target = path / 'py.typed'
        target.touch()
        log.debug('Touched `%s`.', target)


def copy_static_files(merged_settings_loaded: dict[str, Any], module_path: Path) -> None:
    """Copy static files to the current directory."""
    for filename in STATIC_MODULE_FILES:
        if merged_settings_loaded['stubs_only'] and filename.endswith('.py'):
            log.debug('Skipping `%s`.', filename)
            continue
        static_path = module_path / 'static' / filename
        output_file = Path(f'{merged_settings_loaded["primary_module"]}/{filename}')
        if ((output_file.exists() and len(output_file.read_text().strip()) != 0)
                or str(output_file) in merged_settings_loaded['skip']):
            log.debug('Skipping `%s`.', output_file)
            continue
        output_file.parent.mkdir(parents=True, exist_ok=True)
        copyfile(static_path, output_file)
        log.debug('Wrote `%s`.', output_file)


def download_yarn_plugins() -> None:
    """Download Yarn plugins."""
    r = requests.get(PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI, timeout=15)
    r.raise_for_status()
    plugins_dir = Path('.yarn/plugins')
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / 'plugin-prettier-after-all-installed.cjs').write_text(f'{r.text.strip()}\n',
                                                                         encoding='utf-8')


def write_templated_files(module_path: Path, merged_settings_loaded: dict[str, Any]) -> None:
    """Write templated files."""
    env = jinja2.Environment(autoescape=jinja2.select_autoescape(),
                             extensions=(ToPythonExtension,),
                             loader=jinja2.PackageLoader(__package__, 'templates'),
                             lstrip_blocks=True,
                             trim_blocks=True,
                             undefined=jinja2.StrictUndefined)
    templates_dir = module_path / 'templates'
    to_skip = merged_settings_loaded['skip']
    for file_path in templates_dir.rglob('*.j2'):
        if merged_settings_loaded['stubs_only'] and file_path.name.endswith('.py.j2'):
            log.debug('Skipping template `%s`.', file_path)
            continue
        if (file_path.name in {'__main__.py.j2', 'main.py.j2', 'test_main.py.j2'}
                and not merged_settings_loaded['want_main']):
            log.debug('Skipping template `%s`.', file_path)
            continue
        template_path = file_path.relative_to(templates_dir)
        template = env.get_template(str(template_path))
        output_file = orig_output_file = template_path.with_suffix('')
        try:
            if output_file.parts[-2] == '_module_':
                output_file = Path(merged_settings_loaded['primary_module']) / output_file.name
        except IndexError:
            pass
        if ((output_file.exists() and len(output_file.read_text().strip()) != 0)
                and (str(output_file) in to_skip or str(orig_output_file) in to_skip)):
            log.debug('Skipping template `%s`.', output_file)
            continue
        output_file.parent.mkdir(parents=True, exist_ok=True)
        content = template.render({'settings': merged_settings_loaded})
        output_file.write_text(f'{content.strip()}\n')
        log.debug('Wrote `%s`.', output_file)


def evaluate_jsonnet_project(lib_path: Path, jpathdir: list[str], merged_settings: str) -> None:
    """Evaluate ``project.jsonnet`` to output generated files."""
    for filename, content in json.loads(
            _jsonnet.evaluate_file(str(lib_path / 'project.jsonnet'),
                                   jpathdir=jpathdir,
                                   tla_codes={'settings': merged_settings})).items():
        output_file = Path(filename)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(f'{content.strip()}\n')
        log.debug('Wrote `%s`.', output_file)


def evaluate_merged_settings(jpathdir: list[str], lib_path: Path,
                             file: Path) -> tuple[str, dict[str, Any]]:
    """Evaluate the merged settings using Jsonnet."""
    s = cast(
        'str',
        _jsonnet.evaluate_snippet('',
                                  'function(defaults, settings) defaults + settings',
                                  jpathdir=jpathdir,
                                  tla_codes={
                                      'defaults': (lib_path / 'defaults.libjsonnet').read_text(),
                                      'settings': file.read_text()
                                  }))
    return s, json.loads(s)


def download_yarn(version: str) -> None:
    r = requests.get(f'https://repo.yarnpkg.com/{version}/packages/yarnpkg-cli/bin/yarn.js',
                     timeout=15)
    r.raise_for_status()
    releases_dir = Path('.yarn/releases')
    rmtree(releases_dir, ignore_errors=True)
    releases_dir.mkdir(parents=True, exist_ok=True)
    target = releases_dir / f'yarn-{version}.cjs'
    target.write_text(f'{r.text.strip()}\n', encoding='utf-8')
    target.chmod(0o755)


def setup_github_project(settings: dict[str, Any]) -> None:
    if not settings['using_github']:
        return
    owner, project = settings['repository_uri'].split('/')[-2:]
    if not (token := keyring.get_password('tmu-github-api', getpass.getuser())):
        log.warning('No Github token.')
        return
    repo_name = f'{owner}/{project}'
    Github(auth=Auth.Token(token))
    session = requests.Session()
    host = 'https://api.github.com'
    session.headers.update({
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28'
    })
    # The API cannot set the following settings as of 2024-04-12:
    # Moderation options - Code review limits - Limit to users explicitly granted read or higher
    # Repo sections - Include in the home page
    # Actions - General - Permissions
    #                   - Artifact and log retention
    #                   - Approval for running fork pull request workflows from contributors
    #                   - Workflow permissions -
    #                                          - Allow GitHub Actions to create and approve pull
    #                                            requests
    # Code security - Automatic dependency submission
    #               - Dependabot Alerts - Rules - Presets
    #                                   - Grouped security updates
    #                                   - Dependabot on Actions runners
    #               - Code Scanning - Tools - Copilot Autofix
    #                                       - Copilot Autofix for third party tools
    #                               - Protection Rules - Security alert severity level
    #                                                  - Standard alert severity level
    try:
        session.patch(f'{host}/repos/{repo_name}',
                      json={
                          'allow_auto_merge': False,
                          'allow_merge_commit': False,
                          'allow_rebase_merge': True,
                          'allow_squash_merge': True,
                          'allow_update_branch': True,
                          'archived': False,
                          'delete_branch_on_merge': True,
                          'dependabot_on_actions_enabled': True,
                          'dependency_graph_autosubmit_action_enabled': True,
                          'dependency_graph_autosubmit_action_use_labeled_runners': False,
                          'description': settings['description'],
                          'enable_max_pushes_checkbox': False,
                          'enable_repository_funding_links': True,
                          'has_discussions': False,
                          'has_downloads': True,
                          'has_issues': True,
                          'has_pages': True,
                          'has_projects': False,
                          'has_wiki': False,
                          'homepage': settings['homepage'],
                          'include_lfs_objects': False,
                          'security_and_analysis': {
                              'dependabot_security_updates': {
                                  'status': 'enabled'
                              },
                              'secret_scanning': {
                                  'status': 'enabled'
                              },
                              'secret_scanning_non_provider_patterns': {
                                  'status': 'disabled'
                              },
                              'secret_scanning_push_protection': {
                                  'status': 'enabled'
                              },
                              'secret_scanning_validity_checks': {
                                  'status': 'disabled'
                              }
                          },
                          'squash_merge_commit_message': 'COMMIT_MESSAGES',
                          'squash_merge_commit_title': 'COMMIT_OR_PR_TITLE',
                          'use_squash_pr_title_as_default': False,
                          'vulnerability_updates_grouping_enabled': True,
                          'web_commit_signoff_required': True
                      }).raise_for_status()
        session.put(f'{host}/repos/{repo_name}/topics',
                    json={
                        'names': [x.replace(' ', '-') for x in settings['keywords']]
                    }).raise_for_status()
        session.put(f'{host}/repos/{repo_name}/automated-security-fixes').raise_for_status()
        session.put(f'{host}/repos/{repo_name}/private-vulnerability-reporting').raise_for_status()
        session.put(f'{host}/repos/{repo_name}/vulnerability-alerts').raise_for_status()
        r = session.get(f'{host}/repos/{repo_name}/rulesets')
        r.raise_for_status()
        rulesets = r.json()
        names = [x['name'] for x in rulesets]
        if 'Protect version tags' not in names:
            session.post(f'{host}/repos/{repo_name}/rulesets',
                         json={
                             'name':
                                 'Protect version tags',
                             'target':
                                 'tag',
                             'bypass_actors': [{
                                 'actor_id': 5,
                                 'actor_type': 'RepositoryRole',
                                 'bypass_mode': 'always'
                             }],
                             'conditions': {
                                 'ref_name': {
                                     'exclude': [],
                                     'include': ['refs/tags/v*']
                                 }
                             },
                             'enforcement':
                                 'active',
                             'rules': [{
                                 'type': 'deletion'
                             }, {
                                 'type': 'non_fast_forward'
                             }, {
                                 'type': 'required_linear_history'
                             }, {
                                 'type': 'creation'
                             }, {
                                 'type': 'update'
                             }, {
                                 'type': 'required_signatures'
                             }],
                         }).raise_for_status()
        if 'Protect default branch' not in names:
            session.post(f'{host}/repos/{repo_name}/rulesets',
                         json={
                             'name':
                                 'Protect default branch',
                             'target':
                                 'branch',
                             'bypass_actors': [{
                                 'actor_id': 5,
                                 'actor_type': 'RepositoryRole',
                                 'bypass_mode': 'always'
                             }],
                             'conditions': {
                                 'ref_name': {
                                     'exclude': [],
                                     'include': ['~DEFAULT_BRANCH']
                                 }
                             },
                             'enforcement':
                                 'active',
                             'rules': [{
                                 'type': 'deletion'
                             }, {
                                 'type': 'non_fast_forward'
                             }, {
                                 'parameters': {
                                     'allowed_merge_methods': ['squash', 'rebase'],
                                     'automatic_copilot_code_review_enabled': False,
                                     'dismiss_stale_reviews_on_push': True,
                                     'require_code_owner_review': True,
                                     'require_last_push_approval': True,
                                     'required_approving_review_count': 1,
                                     'required_review_thread_resolution': True
                                 },
                                 'type': 'pull_request'
                             }],
                         }).raise_for_status()
        if session.get(f'{host}/repos/{repo_name}/pages').status_code != HTTPStatus.OK:
            session.post(f'{host}/repos/{repo_name}/pages',
                         json={
                             'source': {
                                 'branch': settings['default_branch'],
                                 'path': '/'
                             }
                         }).raise_for_status()
    except requests.exceptions.HTTPError as e:
        log.warning('Caught error updating repo: %s.', e.response.text)
