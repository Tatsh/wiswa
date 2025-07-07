"""Utilities."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from functools import cache
from http import HTTPStatus
from pathlib import Path
from shlex import quote
from shutil import copyfile, rmtree
from typing import TYPE_CHECKING, Any, cast
import getpass
import json
import logging
import logging.config
import subprocess as sp

import _jsonnet  # type: ignore[import-not-found] # noqa: PLC2701
import jinja2
import keyring
import requests
import tomlkit

from .constants import PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI
from .extensions import ToPythonExtension

if TYPE_CHECKING:
    from .typing import ProjectType, Settings

__all__ = ('copy_static_files', 'create_py_typed_files', 'download_yarn_plugins',
           'evaluate_jsonnet_file', 'evaluate_jsonnet_project', 'evaluate_merged_settings',
           'get_latest_yarn_version', 'post_process_steps', 'setup_logging',
           'write_templated_files')

log = logging.getLogger(__name__)


def subprocess_log_run(*args: Any, **kwargs: Any) -> sp.CompletedProcess[Any]:
    """Run a subprocess and log its output."""
    assert isinstance(args[0], Iterable)
    log.debug('Running command: %s', ' '.join(quote(x) for x in args[0]))
    return sp.run(*args, check=kwargs.pop('check', True), **kwargs)


def post_process_steps_python(settings: Settings) -> None:
    if not settings['want_tests']:
        rmtree('tests', ignore_errors=True)
        Path('.github/workflows/tests.yml').unlink(missing_ok=True)
        if (not settings['vscode']['launch']
                or (len(settings['vscode']['launch']['configurations']) == 1
                    and settings['vscode']['launch']['configurations'][0]['name'] == 'Run tests')):
            Path('.vscode/launch.json').unlink(missing_ok=True)
    pyproject_content = tomlkit.loads(Path('pyproject.toml').read_text(encoding='utf-8')).unwrap()
    if not settings['want_docs']:
        rmtree('docs', ignore_errors=True)
        Path('.readthedocs.yaml').unlink(missing_ok=True)
        del pyproject_content['tool']['poetry']['group']['docs']
    if not settings['want_codeql']:
        Path('.github/workflows/codeql.yml').unlink(missing_ok=True)
    if settings['want_man']:
        log.debug('Adding man pages to Commitizen version_files.')
        if (man := Path('man')).exists():
            pyproject_content['tool']['commitizen']['version_files'] = sorted({
                *pyproject_content['tool']['commitizen']['version_files'],
                *(str(x) for x in man.glob('*.1'))
            })
        else:
            module = settings['primary_module']
            pyproject_content['tool']['commitizen']['version_files'] = sorted(
                {*pyproject_content['tool']['commitizen']['version_files'], f'man/{module}.1'})
    if not settings['want_tests']:
        del pyproject_content['tool']['coverage']
        del pyproject_content['tool']['poetry']['group']['tests']
        del pyproject_content['tool']['pytest']
        rmtree('tests', ignore_errors=True)
    package_json_content = json.loads(Path('package.json').read_text(encoding='utf-8'))
    if not settings['want_yapf']:
        del pyproject_content['tool']['yapf']
        del pyproject_content['tool']['yapfignore']
        package_json_content['check-formatting'] = ("yarn prettier -c . && poetry run ruff format "
                                                    "--check . && yarn markdownlint-cli2 '**/*.md'"
                                                    " '#node_modules'")
        package_json_content['format'] = ("yarn prettier -w . && poetry run ruff format . "
                                          "&& yarn markdownlint-cli2 '**/*.md' '#node_modules'")
    Path('package.json').write_text(json.dumps(package_json_content, indent=2, sort_keys=True),
                                    encoding='utf-8')
    # tomlkit will strip empty sections.
    Path('pyproject.toml').write_text(tomlkit.dumps(pyproject_content), encoding='utf-8')
    subprocess_log_run(('poetry', 'lock'))
    with_arg = ','.join(('docs' if settings['want_docs'] else '',
                         'tests' if settings['want_tests'] else '', 'dev')).lstrip(',').rstrip(',')
    subprocess_log_run(('poetry', 'update', *((f'--with={with_arg}',) if with_arg != ',' else ())))
    subprocess_log_run(('poetry', 'install', '--all-groups'))
    subprocess_log_run(('poetry', 'run', 'ruff', 'check', '--fix'), check=False)


def post_process_steps(settings: Settings) -> None:
    """Run post-processing steps."""
    match settings['project_type']:
        case 'python':
            post_process_steps_python(settings)
        case _:
            log.warning('No post-processing steps for project type `%s`.', settings['project_type'])
    package_json = Path('package.json')
    package_json.write_text(json.dumps(json.loads(package_json.read_text(encoding='utf-8')),
                                       indent=2,
                                       sort_keys=True),
                            encoding='utf-8')
    subprocess_log_run(('yarn',))
    subprocess_log_run(('yarn', 'format'), check=False)


def create_py_typed_files(settings: Settings) -> None:
    """Create ``py.typed`` files for all packages."""
    for path in (Path(x['include']) for x in settings['pyproject']['tool']['poetry']['packages']):
        path.mkdir(parents=True, exist_ok=True)
        target = path / 'py.typed'
        target.touch()
        log.debug('Touched `%s`.', target)


def non_empty_file_exists(output_file: Path) -> bool:
    """Check if a file exists and is not empty."""
    return output_file.exists() and len(output_file.read_text().strip()) != 0


def copy_static_files_python(settings: Settings, module_path: Path) -> None:
    """Copy static files to the current directory."""
    def copy_file(filename: str) -> None:
        static_path = module_path / 'static' / filename
        output_file = Path(f'{settings["primary_module"]}/{filename}')
        if non_empty_file_exists(output_file):
            log.debug('Skipping `%s`.', output_file)
            return
        output_file.parent.mkdir(parents=True, exist_ok=True)
        copyfile(static_path, output_file)
        log.debug('Wrote `%s`.', output_file)

    if settings['project_type'] == 'python':
        if settings['stubs_only']:
            return
        copy_file('utils.py')
        if settings['want_main']:
            copy_file('__main__.py')
            copy_file('main.py')


def copy_static_files(settings: Settings,
                      module_path: Path,
                      project_type: ProjectType = 'python') -> None:
    """Copy static files to the current directory."""
    match project_type:
        case 'python':
            copy_static_files_python(settings, module_path)
        case _:
            log.warning('No static files to copy for project type `%s`.', project_type)


def download_yarn_plugins() -> None:
    """Download Yarn plugins."""
    r = requests.get(PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI, timeout=15)
    r.raise_for_status()
    plugins_dir = Path('.yarn/plugins')
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / 'plugin-prettier-after-all-installed.cjs').write_text(f'{r.text.strip()}\n',
                                                                         encoding='utf-8')


def _template_env(
    module_path: Path, settings: Settings
) -> tuple[jinja2.Environment, Path, Callable[[Path], jinja2.Template], Callable[..., None]]:
    env = jinja2.Environment(autoescape=jinja2.select_autoescape(),
                             extensions=(ToPythonExtension,),
                             loader=jinja2.PackageLoader(__package__),
                             lstrip_blocks=True,
                             trim_blocks=True,
                             undefined=jinja2.StrictUndefined)
    templates_dir = module_path / 'templates'

    def resolve_template(file_path: Path) -> jinja2.Template:
        return env.get_template(str(file_path.relative_to(templates_dir)))

    def write_file(template: jinja2.Template,
                   output_file: Path | str,
                   *,
                   overwrite: bool = False) -> None:
        output_file = Path(output_file)
        if not overwrite and non_empty_file_exists(output_file):
            log.debug('Skipping template `%s`.', output_file)
            return
        output_file.parent.mkdir(parents=True, exist_ok=True)
        content = template.render({'settings': settings})
        output_file.write_text(f'{content.strip()}\n')
        log.debug('Wrote `%s`.', output_file)

    return env, templates_dir, resolve_template, write_file


def write_templated_files_c_cpp(settings: Settings, templates_dir: Path,
                                resolve_template: Callable[[Path], jinja2.Template],
                                write_file: Callable[..., object]) -> None:
    write_file(resolve_template(templates_dir / 'CMakeLists.txt.j2'), 'CMakeLists.txt')
    write_file(resolve_template(templates_dir / 'src/CMakeLists.txt.j2'), 'src/CMakeLists.txt')
    if settings['want_docs']:
        write_file(resolve_template(templates_dir / 'Doxyfile.in.j2'),
                   'Doxyfile.in',
                   overwrite=True)


def write_templated_files_cpp(settings: Settings, templates_dir: Path,
                              resolve_template: Callable[[Path], jinja2.Template],
                              write_file: Callable[..., object]) -> None:
    if settings['want_main']:
        write_file(resolve_template(templates_dir / 'src/main.cpp.j2'), 'src/main.cpp')


def write_templated_files_c(settings: Settings, templates_dir: Path,
                            resolve_template: Callable[[Path], jinja2.Template],
                            write_file: Callable[..., object]) -> None:
    if settings['want_main']:
        write_file(resolve_template(templates_dir / 'src/main.c.j2'), 'src/main.c')


def write_template_files_lua(templates_dir: Path, resolve_template: Callable[[Path],
                                                                             jinja2.Template],
                             write_file: Callable[..., object]) -> None:
    write_file(resolve_template(templates_dir / '.busted.j2'), '.busted')
    write_file(resolve_template(templates_dir / '.luacov.j2'), '.luacov')


def write_templated_files_python(settings: Settings, templates_dir: Path,
                                 resolve_template: Callable[[Path], jinja2.Template],
                                 write_file: Callable[..., object]) -> None:
    if settings['want_tests']:
        write_file(resolve_template(templates_dir / 'tests/conftest.py.j2'), 'tests/conftest.py')
        write_file(resolve_template(templates_dir / 'tests/test_utils.py.j2'),
                   'tests/test_utils.py')
        if settings['want_main']:
            write_file(resolve_template(templates_dir / 'tests/test_main.py.j2'),
                       'tests/test_main.py')
    if settings['want_docs']:
        for file_path in (templates_dir / 'docs/conf.py.j2', templates_dir / 'docs/index.rst.j2'):
            write_file(resolve_template(file_path),
                       file_path.relative_to(templates_dir).with_suffix(''))


def write_templated_files_typescript(templates_dir: Path,
                                     resolve_template: Callable[[Path], jinja2.Template],
                                     write_file: Callable[..., object]) -> None:
    """Write templated files for TypeScript projects."""
    write_file(resolve_template(templates_dir / 'src/index.ts.j2'), 'src/index.ts')
    write_file(resolve_template(templates_dir / 'eslint.config.mjs.j2'),
               'eslint.config.mjs',
               overwrite=True)


def write_templated_files(module_path: Path, settings: Settings) -> None:
    """Write templated files."""
    _, templates_dir, resolve_template, write_file = _template_env(module_path, settings)
    write_file(resolve_template(templates_dir / '.github/copilot-instructions.md.j2'),
               '.github/copilot-instructions.md')
    for file_path, overwrite in (('CODEOWNERS.j2', True), ('CONTRIBUTING.md.j2', False),
                                 ('LICENSE.txt.j2', True), ('SECURITY.md.j2', True),
                                 ('CHANGELOG.md.j2', False), (templates_dir / 'README.md.j2',
                                                              False)):
        write_file(resolve_template(templates_dir / file_path),
                   (templates_dir / file_path).relative_to(templates_dir).with_suffix(''),
                   overwrite=overwrite)
    match settings['project_type']:
        case 'python':
            write_templated_files_python(settings, templates_dir, resolve_template, write_file)
        case 'c++':
            write_templated_files_c_cpp(settings, templates_dir, resolve_template, write_file)
            write_templated_files_cpp(settings, templates_dir, resolve_template, write_file)
        case 'c':
            write_templated_files_c_cpp(settings, templates_dir, resolve_template, write_file)
            write_templated_files_c(settings, templates_dir, resolve_template, write_file)
        case 'lua':
            write_template_files_lua(templates_dir, resolve_template, write_file)
        case 'typescript':
            write_templated_files_typescript(templates_dir, resolve_template, write_file)
        case _:
            log.warning('No templated files to write for project type `%s`.',
                        settings['project_type'])


@cache
def get_latest_yarn_version() -> str:  # pragma: no cover
    """Get the latest Yarn version."""
    r = requests.get('https://repo.yarnpkg.com/tags', timeout=15)
    r.raise_for_status()
    return cast('str', r.json()['latest']['stable'])


NATIVE_CALLBACKS = {
    'latestYarnVersion': ((), get_latest_yarn_version),
    'isodate': ((), lambda: datetime.now(tz=timezone.utc).isoformat()[:10]),
    'year': ((), lambda: datetime.now(tz=timezone.utc).year),
}


def evaluate_jsonnet_file(jpathdir: list[str], file: Path, merged_settings: str) -> str:
    """Evaluate a Jsonnet file with the given settings."""
    return cast(
        'str',
        _jsonnet.evaluate_file(str(file),
                               jpathdir=jpathdir,
                               native_callbacks=NATIVE_CALLBACKS,
                               tla_codes={'settings': merged_settings}))


def evaluate_jsonnet_project(lib_path: Path,
                             jpathdir: list[str],
                             merged_settings: str,
                             file: Path | None = None,
                             output_dir: Path | None = None) -> None:
    """Evaluate ``project.jsonnet`` to output generated files."""
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir or Path()
    filename: str
    for filename, content in json.loads(
            evaluate_jsonnet_file(jpathdir, file or (lib_path / 'project.jsonnet'),
                                  merged_settings)).items():
        output_file = output_dir / filename
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(f'{content.strip()}\n')
        log.debug('Wrote `%s`.', output_file)


def evaluate_merged_settings(jpathdir: list[str], lib_path: Path,
                             settings: str) -> tuple[str, Settings]:
    """Evaluate the merged settings using Jsonnet."""
    s = cast(
        'str',
        _jsonnet.evaluate_snippet('',
                                  'function(defaults, settings) defaults + settings',
                                  jpathdir=jpathdir,
                                  native_callbacks=NATIVE_CALLBACKS,
                                  tla_codes={
                                      'defaults': (lib_path / 'defaults.libjsonnet').read_text(),
                                      'settings': settings
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


def setup_github_project(settings: Settings) -> None:
    if not settings['using_github']:
        log.debug('Not running GitHub setup.')
        return
    owner, project = settings['repository_uri'].split('/')[-2:]
    if not (token := keyring.get_password('tmu-github-api', getpass.getuser())):
        log.warning('No GitHub token.')
        return
    log.debug('Got a token.')
    repo_name = f'{owner}/{project}'
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


def setup_logging(*,
                  debug: bool = False,
                  force_color: bool = False,
                  no_color: bool = False) -> None:  # pragma: no cover
    """Set up logging configuration."""
    logging.config.dictConfig({
        'disable_existing_loggers': True,
        'root': {
            'level': 'DEBUG' if debug else 'INFO',
            'handlers': ['console'],
        },
        'formatters': {
            'default': {
                '()': 'colorlog.ColoredFormatter',
                'force_color': force_color,
                'format': (
                    '%(light_cyan)s%(asctime)s%(reset)s | %(log_color)s%(levelname)-8s%(reset)s | '
                    '%(light_green)s%(name)s%(reset)s:%(light_red)s%(funcName)s%(reset)s:'
                    '%(blue)s%(lineno)d%(reset)s - %(message)s'),
                'no_color': no_color,
            }
        },
        'handlers': {
            'console': {
                'class': 'colorlog.StreamHandler',
                'formatter': 'default',
            }
        },
        'loggers': {
            'urllib3': {
                'level': 'DEBUG' if debug else 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'wiswa': {
                'level': 'DEBUG' if debug else 'INFO',
                'handlers': ['console'],
                'propagate': False,
            }
        },
        'version': 1
    })
