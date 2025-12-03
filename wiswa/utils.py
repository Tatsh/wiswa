"""Utilities."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from functools import cache
from http import HTTPStatus
from pathlib import Path
from shlex import quote
from shutil import copyfile, rmtree
from typing import TYPE_CHECKING, Any, NamedTuple, cast
from urllib.parse import quote as urllib_quote, urlencode
import getpass
import json
import logging
import re
import subprocess as sp

from bs4 import BeautifulSoup as Soup
from packaging.version import InvalidVersion, Version, parse as parse_version
import _jsonnet  # noqa: PLC2701
import jinja2
import keyring
import platformdirs
import requests
import requests_cache
import tomlkit

from .constants import PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI
from .extensions import ToPythonExtension

if TYPE_CHECKING:
    from .typing import Settings

__all__ = ('copy_static_files', 'create_py_typed_files', 'download_yarn_plugins',
           'evaluate_jsonnet_file', 'evaluate_jsonnet_project', 'evaluate_merged_settings',
           'get_latest_yarn_version', 'post_process_steps', 'write_templated_files')

log = logging.getLogger(__name__)


def cached_session() -> requests_cache.CachedSession:
    """Get a cached requests session."""
    return requests_cache.CachedSession(platformdirs.user_cache_path() / 'wiswa/http',
                                        backend='filesystem',
                                        cache_control=True,
                                        expire_after=timedelta(minutes=30))


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
        pyproject_content['tool']['ruff']['lint']['ignore'] = sorted(
            pyproject_content['tool']['ruff']['lint']['ignore'] + ['Q000', 'Q003'])
        package_json_content['scripts']['check-formatting'] = (
            "yarn prettier -c . && poetry run ruff format "
            "--check . && yarn markdownlint-cli2 '**/*.md'"
            " '#node_modules'")
        package_json_content['scripts']['format'] = (
            "yarn prettier -w . && poetry run ruff format . "
            "&& yarn markdownlint-cli2 '**/*.md' '#node_modules'")
    Path('package.json').write_text(json.dumps(package_json_content, indent=2, sort_keys=True),
                                    encoding='utf-8')
    # tomlkit will strip empty sections.
    Path('pyproject.toml').write_text(tomlkit.dumps(pyproject_content), encoding='utf-8')
    subprocess_log_run(('poetry', 'lock'))
    with_arg = ','.join(x for x in ('docs' if settings['want_docs'] else '',
                                    'tests' if settings['want_tests'] else '', 'dev') if x)
    subprocess_log_run(('poetry', 'update', *((f'--with={with_arg}',) if with_arg else ())))
    subprocess_log_run(('poetry', 'install', '--all-groups', '--all-extras'))
    subprocess_log_run(('poetry', 'run', 'ruff', 'check', '--fix'), check=False)


def simple_icons_badge(anchor_text: str, logo: str, label: str, color: str, uri: str) -> str:
    """Generate a Simple Icons badge."""
    return (f'[![{anchor_text}](https://img.shields.io/badge/{label}-{color}?logo={logo})]({uri})')


def _check_readme_badges(settings: Settings) -> None:  # noqa: C901, PLR0912
    """Check and correct README.md badges if file existed before template processing."""
    log.debug('Checking README.md badges.')
    if not settings['_readme_existed']:
        log.debug('README.md did not exist before templating; skipping badge check.')
        return
    readme = Path('README.md')
    if not readme.exists():
        log.debug('README.md was removed; skipping badge check.')
        return
    content = readme.read_text(encoding='utf-8')
    lines = content.split('\n')
    expected: list[str] = []
    social_expected: list[str] = []
    if settings['project_type'] == 'python' and not settings['private']:
        expected.extend(
            (f"[![Python versions](https://img.shields.io/pypi/pyversions/"
             f"{settings['pypi_project_name']}.svg?color=blue&logo=python&logoColor=white)]"
             "(https://www.python.org/)",
             f"[![PyPI - Version](https://img.shields.io/pypi/v/{settings['project_name']})]"
             f"(https://pypi.org/project/{settings['pypi_project_name']}/)"))
    elif settings['project_type'] == 'lua':
        expected.append(simple_icons_badge('Lua', 'lua', 'Lua', '2C2D72', 'https://www.lua.org/'))
    elif settings['project_type'] == 'c':
        expected.append(
            simple_icons_badge('C', 'c', 'C', '00599C',
                               'https://en.wikipedia.org/wiki/C_(programming_language)'))
    elif settings['project_type'] == 'c++':
        expected.append(simple_icons_badge('C++', 'c%2B%2B', 'C++', '00599C', 'https://isocpp.org'))
    elif settings['project_type'] == 'xcode':
        expected.append(
            simple_icons_badge('Xcode', 'xcode', 'Xcode', '007ACC',
                               'https://developer.apple.com/xcode/'))
    if settings['using_github']:
        expected.extend(
            (f"[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/"
             f"{settings['github']['username']}/{settings['project_name']})]"
             f"({settings['repository_uri']}/tags)",
             f"[![License](https://img.shields.io/github/license/{settings['github']['username']}/"
             f"{settings['project_name']})]({settings['repository_uri']}/blob/"
             f"{settings['default_branch']}/LICENSE.txt)",
             f"[![GitHub commits since latest release (by SemVer including pre-releases)]"
             f"(https://img.shields.io/github/commits-since/{settings['github']['username']}/"
             f"{settings['project_name']}/v{settings['version']}/{settings['default_branch']})]"
             f"({settings['repository_uri']}/compare/v{settings['version']}"
             f"...{settings['default_branch']})"))
        if settings['want_codeql']:
            expected.append(
                f"[![CodeQL]({settings['repository_uri']}/actions/workflows/codeql.yml/badge.svg)]"
                f"({settings['repository_uri']}/actions/workflows/codeql.yml)")
        expected.append(f"[![QA]({settings['repository_uri']}/actions/workflows/qa.yml/badge.svg)]"
                        f"({settings['repository_uri']}/actions/workflows/qa.yml)")
        if settings['want_tests']:
            expected.extend(
                (f"[![Tests]({settings['repository_uri']}/actions/workflows/tests.yml/badge.svg)]"
                 f"({settings['repository_uri']}/actions/workflows/tests.yml)",
                 f"[![Coverage Status](https://coveralls.io/repos/github/"
                 f"{settings['github']['username']}/{settings['project_name']}/badge.svg?"
                 f"branch=master)](https://coveralls.io/github/{settings['github']['username']}/"
                 f"{settings['project_name']}?branch={settings['default_branch']})"))
        expected.append(
            simple_icons_badge('Dependabot', 'dependabot', 'Dependabot-enabled', 'blue',
                               'https://github.com/dependabot'))
    if settings['want_docs']:
        if settings['project_type'] == 'python' and not settings['private']:
            expected.append(
                f"[![Documentation Status](https://readthedocs.org/projects/{settings['project_name']}"
                f"/badge/?version=latest)]({settings['documentation_uri']}/?badge=latest)")
        elif settings['using_github']:
            expected.append(f'[![GitHub Pages](https://github.com/{settings["github"]["username"]}/'
                            f'{settings["project_name"]}/badge/pages)]'
                            f'(https://{settings["github"]["username"]}.github.io/'
                            f'{settings["project_name"]}/)')
    if settings['project_type'] == 'python':
        if settings['using_django']:
            expected.append(
                simple_icons_badge('Django', 'django', 'Django', '092E20',
                                   'https://djangoproject.com'))
        expected.extend((
            '[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)',
            simple_icons_badge('pre-commit', 'pre-commit', 'pre--commit-enabled', 'brightgreen',
                               'https://pre-commit.com/'),
            simple_icons_badge('Poetry', 'poetry', 'Poetry', '242d3e', 'https://python-poetry.org'),
        ))
        name_mapping = {'sqlalchemy': 'SQLAlchemy', 'pydantic': 'Pydantic', 'jinja': 'Jinja'}
        expected.extend(
            simple_icons_badge(name_mapping.get(package, package), package,
                               name_mapping.get(package, package), 'black',
                               f'https://pypi.org/project/{package}/')
            for package in ('numpy', 'jinja', 'pandas', 'pydantic', 'scrapy', 'sqlalchemy')
            if package in settings['pyproject']['tool']['poetry']['dependencies'])
        if not settings['stubs_only'] and settings['want_tests']:
            expected.extend((simple_icons_badge('pydocstyle', 'pydocstyle', 'pydocstyle-enabled',
                                                'AD4CD3', 'https://www.pydocstyle.org/'),
                             simple_icons_badge('pytest', 'pytest', 'pytest-enabled', 'CFB97D',
                                                'https://docs.pytest.org')))
        expected.append(
            '[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com'
            '/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)')
        if not settings['private']:
            expected.append(
                f"[![Downloads](https://static.pepy.tech/badge/{settings['project_name']}/month)]"
                f"(https://pepy.tech/project/{settings['project_name']})")
    if Path('Dockerfile').exists():
        expected.append(
            simple_icons_badge('Docker', 'docker', 'Docker', 'black', 'https://www.docker.com/'))
    if settings['using_github']:
        expected.append(
            f"[![Stargazers](https://img.shields.io/github/stars/{settings['github']['username']}/"
            f"{settings['project_name']}?logo=github&style=flat)]"
            f"(https://github.com/{settings['github']['username']}/{settings['project_name']}/"
            "stargazers)")
    if ((settings['project_type'] == 'c' or settings['project_type'] == 'c++')
            and Path('CMakeLists.txt').exists()):
        expected.append(
            simple_icons_badge('CMake', 'cmake', 'CMake', '6E6E6E', 'https://cmake.org/'))
    if settings['project_type'] == 'typescript':
        expected.extend(
            sorted((*(simple_icons_badge(dep, dep.replace('-', ''), dep, 'black',
                                         f'https://www.npmjs.com/package/{dep}')
                      for dep in ('bootstrap', 'react', 'sass', 'semantic-ui-react', 'sass',
                                  'tailwindcss')
                      if dep in settings['package_json'].get('dependencies', {})),
                    *(simple_icons_badge(dev_dep, dev_dep.replace('-', ''), dev_dep, 'black',
                                         f'https://www.npmjs.com/package/{dev_dep}')
                      for dev_dep in ('eslint', 'jest')
                      if dev_dep in settings['package_json']['devDependencies']),
                    simple_icons_badge('TypeScript', 'typescript', 'TypeScript', 'black',
                                       'https://www.typescriptlang.org/'),
                    simple_icons_badge('Yarn', 'yarn', 'Yarn', '4c335c', 'https://yarnpkg.com/'),
                    *((simple_icons_badge('Next.js', 'nextdotjs', 'Next.js', '000000',
                                          'https://nextjs.org/'),)
                      if 'next' in settings['package_json'].get('dependencies', {}) else ()))))
    expected.append(
        simple_icons_badge('Prettier', 'prettier', 'Prettier-enabled', 'black',
                           'https://prettier.io/'))
    keywords_to_args = {
        'dotnet': ('.NET', 'dotnet', '.NET', '512BD4', 'https://dotnet.microsoft.com/'),
        'ffmpeg': ('FFmpeg', 'ffmpeg', 'FFmpeg', 'orange', 'https://ffmpeg.org/'),
        'kde': ('KDE Plasma', 'kdeplasma', 'KDE Plasma', 'blue', 'https://kde.org/'),
        'qt': ('Qt', 'qt', 'Qt', '41cd52', 'https://www.qt.io/'),
        'swift': ('Swift', 'swift', 'Swift', 'F05138', 'https://swift.org/'),
    }
    for keyword, args in keywords_to_args.items():
        if keyword in settings['keywords']:
            social_expected.append(simple_icons_badge(*args))
    if settings['social']['bsky']:
        outer_params = urlencode(
            {
                'style': 'social',
                'logo': 'bluesky',
                'label': f'Follow @{settings["social"]["bsky"]}',
            },
            errors='strict')
        url = urllib_quote('https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile/?',
                           safe='',
                           errors='strict') + urlencode({
                               'actor': 'did:plc:uq42idtvuccnmtl57nsucz72',
                               'query': '$.followersCount'
                           })
        social_expected.append(
            f'[![@{settings["social"]["bsky"]}]'
            f'(https://img.shields.io/badge/dynamic/json?url={url}&{outer_params})]'
            f'(https://bsky.app/profile/{settings["social"]["bsky"]}.bsky.social)')
    if username := settings['social']['buymeacoffee']:
        social_expected.append(
            simple_icons_badge('Buy Me A Coffee', 'buymeacoffee',
                               f'Buy%20Me%20a%20Coffee-{username}', 'black',
                               f'https://buymeacoffee.com/{username}'))
    if ((text := settings['social']['calendly']['text'])
            and (uri := settings['social']['calendly']['uri'])):
        social_expected.append(simple_icons_badge('Calendly', 'calendly', text, '00a2ff', uri))
    if username := settings['social']['cashapp']:
        social_expected.append(
            simple_icons_badge('Cash App', 'cashapp', f'Cash%20App-{username}', '00C244',
                               f'https://cash.app/{username}'))
    if libera_irc := settings['social']['libera_irc']:
        social_expected.append(
            simple_icons_badge('Libera.Chat', 'liberadotchat', f'Libera.Chat-{libera_irc}', 'black',
                               f'irc://irc.libera.chat/{libera_irc}'))
    if ((mastodon_id := settings['social']['mastodon']['id'])
            and (domain := settings['social']['mastodon']['domain'])):
        social_expected.append(
            f"[![Mastodon Follow](https://img.shields.io/mastodon/follow/{mastodon_id}?"
            f"domain={domain}&style=social)](https://{domain}/@{settings['github']['username']})")
    if username := settings['social']['patreon']:
        social_expected.append(
            simple_icons_badge('Patreon', 'patreon', f'Patreon-{username}', 'F96854',
                               f'https://www.patreon.com/{username}'))
    if settings['social']['slashdot']:
        social_expected.append(
            simple_icons_badge('Slashdot', 'slashdot', settings['social']['slashdot'], '066665',
                               f'https://slashdot.org/~{settings["social"]["slashdot"]}'))
    if ((uri := settings['social']['youtube']['uri'])
            and (text := settings['social']['youtube']['text'])):
        social_expected.append(simple_icons_badge('YouTube', 'youtube', text, 'FF0000', uri))
    social_expected.extend(settings['social']['custom_badges'])
    # Find badge section (after title, before description).
    start_idx = next((i for i, line in enumerate(lines) if line.startswith('#')), 0) + 1
    while start_idx < len(lines) and not lines[start_idx].strip():
        start_idx += 1
    end_idx = start_idx
    while end_idx < len(lines) and (lines[end_idx].startswith('[![') or
                                    lines[end_idx].startswith('![') or not lines[end_idx].strip()):
        end_idx += 1
    readme.write_text('\n'.join(
        (*lines[:start_idx], '', *expected, '', *social_expected, '', *lines[end_idx:])),
                      encoding='utf-8')
    log.debug('Updated README.md badges.')


def post_process_steps(settings: Settings) -> None:
    """Run post-processing steps."""
    match settings['project_type']:
        case 'python':
            post_process_steps_python(settings)
        case _:
            log.warning('No post-processing steps for project type `%s`.', settings['project_type'])
    _check_readme_badges(settings)
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
    return output_file.exists() and len(output_file.read_text(encoding='utf-8').strip()) != 0


def copy_static_files_python(settings: Settings, module_path: Path) -> None:
    """Copy static files to the current directory."""
    def copy_file(filename: str) -> None:
        static_path = module_path / 'static' / filename
        # Validate and sanitize primary_module to prevent path traversal
        primary_module = Path(settings['primary_module']).name
        output_file = Path(primary_module) / filename
        if non_empty_file_exists(output_file):
            log.debug('Skipping `%s`.', output_file)
            return
        output_file.parent.mkdir(parents=True, exist_ok=True)
        copyfile(static_path, output_file)
        log.debug('Wrote `%s`.', output_file)

    if settings['stubs_only']:
        return
    if settings['want_main'] and not settings['has_multiple_entry_points']:
        copy_file('__main__.py')
        copy_file('main.py')


def copy_static_files(settings: Settings, module_path: Path) -> None:
    """Copy static files to the current directory."""
    Path('.github/instructions').mkdir(parents=True, exist_ok=True)
    for name in ('json-yaml', 'markdown', 'toml-ini'):
        copyfile(module_path / 'static/.github/instructions' / f'{name}.instructions.md',
                 f'.github/instructions/{name}.instructions.md')
    match settings['project_type']:
        case 'c++':
            copyfile(module_path / 'static/.github/instructions/cpp.instructions.md',
                     '.github/instructions/cpp.instructions.md')
        case 'python':
            if not settings['stubs_only']:
                copyfile(module_path / 'static/.github/instructions/python.instructions.md',
                         '.github/instructions/python.instructions.md')
                copyfile(module_path / 'static/.github/instructions/python-tests.instructions.md',
                         '.github/instructions/python-tests.instructions.md')
            copy_static_files_python(settings, module_path)
        case _:
            log.warning('No static files to copy for project type `%s`.', settings['project_type'])


def download_yarn_plugins() -> None:
    """Download Yarn plugins."""
    r = cached_session().get(PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI, timeout=15)
    r.raise_for_status()
    plugins_dir = Path('.yarn/plugins')
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / 'plugin-prettier-after-all-installed.cjs').write_text(f'{r.text.strip()}\n',
                                                                         encoding='utf-8')


class _TemplateEnvTuple(NamedTuple):
    env: jinja2.Environment
    templates_dir: Path
    resolve_template: Callable[[Path], jinja2.Template]
    write_file: Callable[..., None]


def _template_env(module_path: Path, settings: Settings) -> _TemplateEnvTuple:
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

    return _TemplateEnvTuple(env, templates_dir, resolve_template, write_file)


def write_templated_files_c_cpp(templates_dir: Path, resolve_template: Callable[[Path],
                                                                                jinja2.Template],
                                write_file: Callable[..., object]) -> None:
    write_file(resolve_template(templates_dir / 'CMakeLists.txt.j2'), 'CMakeLists.txt')
    write_file(resolve_template(templates_dir / 'src/CMakeLists.txt.j2'), 'src/CMakeLists.txt')


def write_templated_files_cpp(settings: Settings, templates_dir: Path,
                              resolve_template: Callable[[Path], jinja2.Template],
                              write_file: Callable[..., object]) -> None:
    if settings['want_main'] and not settings['has_multiple_entry_points']:
        write_file(resolve_template(templates_dir / 'src/main.cpp.j2'), 'src/main.cpp')


def write_templated_files_c(settings: Settings, templates_dir: Path,
                            resolve_template: Callable[[Path], jinja2.Template],
                            write_file: Callable[..., object]) -> None:
    if settings['want_main'] and not settings['has_multiple_entry_points']:
        write_file(resolve_template(templates_dir / 'src/main.c.j2'), 'src/main.c')


def write_template_files_lua(templates_dir: Path, resolve_template: Callable[[Path],
                                                                             jinja2.Template],
                             write_file: Callable[..., object]) -> None:
    write_file(resolve_template(templates_dir / '.busted.j2'), '.busted')
    write_file(resolve_template(templates_dir / '.luacov.j2'), '.luacov')


def write_templated_files_python(settings: Settings, templates_dir: Path,
                                 resolve_template: Callable[[Path], jinja2.Template],
                                 write_file: Callable[..., object]) -> None:
    if not settings['stubs_only']:
        write_file(resolve_template(templates_dir / '_module_/__init__.py.j2'),
                   f'{settings["primary_module"]}/__init__.py')
    if settings['want_tests']:
        write_file(resolve_template(templates_dir / 'tests/conftest.py.j2'), 'tests/conftest.py')
        if settings['want_main'] and not settings['has_multiple_entry_points']:
            write_file(resolve_template(templates_dir / 'tests/test_main.py.j2'),
                       'tests/test_main.py')
    if settings['want_docs']:
        for file_path in (templates_dir / 'docs/conf.py.j2', templates_dir / 'docs/index.rst.j2'):
            write_file(resolve_template(file_path),
                       file_path.relative_to(templates_dir).with_suffix(''))
    if ((settings['want_main'] or settings['has_multiple_entry_points'])
            and settings['using_github']):
        write_file(resolve_template(templates_dir / '.github/workflows/pyinstaller.yml.j2'),
                   '.github/workflows/pyinstaller.yml',
                   overwrite=True)
        write_file(resolve_template(templates_dir / '.github/workflows/appimage.yml.j2'),
                   '.github/workflows/appimage.yml',
                   overwrite=True)


def write_templated_files_typescript(settings: Settings, templates_dir: Path,
                                     resolve_template: Callable[[Path], jinja2.Template],
                                     write_file: Callable[..., object]) -> None:
    """Write templated files for TypeScript projects."""
    if not settings['stubs_only']:
        write_file(resolve_template(templates_dir / 'src/index.ts.j2'), 'src/index.ts')
    if settings['want_tests'] and not settings['stubs_only']:
        write_file(resolve_template(templates_dir / 'jest.config.ts.j2'), 'jest.config.ts')
    write_file(resolve_template(templates_dir / 'eslint.config.mjs.j2'),
               'eslint.config.mjs',
               overwrite=True)


def write_templated_files(module_path: Path, settings: Settings) -> None:
    """Write templated files."""
    _, templates_dir, resolve_template, write_file = _template_env(module_path, settings)
    Path('.github/copilot-instructions.md').unlink(missing_ok=True)
    write_file(resolve_template(templates_dir / '.github/instructions/general.instructions.md.j2'),
               '.github/instructions/general.instructions.md')
    common_templates = (('CODEOWNERS.j2', True), ('CONTRIBUTING.md.j2', False),
                        ('LICENSE.txt.j2', not settings['private']), ('SECURITY.md.j2', True),
                        ('CHANGELOG.md.j2', False), ('README.md.j2', False))
    for template_name, overwrite in common_templates:
        template_path = templates_dir / template_name
        output_path = Path(template_name).with_suffix('')
        write_file(resolve_template(template_path), output_path, overwrite=overwrite)
    match settings['project_type']:
        case 'python':
            write_templated_files_python(settings, templates_dir, resolve_template, write_file)
        case 'c++':
            write_templated_files_c_cpp(templates_dir, resolve_template, write_file)
            write_templated_files_cpp(settings, templates_dir, resolve_template, write_file)
        case 'c':
            write_templated_files_c_cpp(templates_dir, resolve_template, write_file)
            write_templated_files_c(settings, templates_dir, resolve_template, write_file)
        case 'lua':
            write_template_files_lua(templates_dir, resolve_template, write_file)
        case 'typescript':
            write_templated_files_typescript(settings, templates_dir, resolve_template, write_file)
        case _:
            log.warning('No templated files to write for project type `%s`.',
                        settings['project_type'])


@cache
def get_latest_yarn_version() -> str:  # pragma: no cover
    """Get the latest Yarn version."""
    r = cached_session().get('https://repo.yarnpkg.com/tags', timeout=15)
    r.raise_for_status()
    return cast('str', r.json()['latest']['stable'])


@cache
def get_npm_latest_package_version(package: str) -> str:  # pragma: no cover
    """Get the latest version of an NPM package."""
    r = cached_session().get(f'https://registry.npmjs.org/{package}/latest', timeout=15)
    r.raise_for_status()
    return cast('str', r.json()['version'])


PYPI_YANKED_RELEASES = {
    'sphinx-8.3.0',
}


@cache
def get_pypi_latest_package_version(package: str) -> str:  # pragma: no cover
    """
    Get the latest version of a PyPI package.

    Raises
    ------
    ValueError
        If no versions are found.
    """
    r = cached_session().get(f'https://pypi.org/rss/project/{package}/releases.xml', timeout=15)
    r.raise_for_status()
    root = Soup(r.content, 'xml')
    versions = [x.text for x in root.select('item > title')]
    if not versions:
        msg = f'No versions found for package `{package}`.'
        raise ValueError(msg)

    def parse_version_safe(v: str) -> Version | None:
        try:
            return parse_version(v)
        except InvalidVersion:
            return None

    return str(
        max(w for w in (parse_version_safe(v) for v in versions) if w and not w.is_prerelease
            and not w.is_devrelease and f'{package}-{w}' not in PYPI_YANKED_RELEASES))


@cache
def get_github_release_latest_tag(owner: str,
                                  repo: str,
                                  *,
                                  actions: bool = False,
                                  skip_releases: bool = False,
                                  allow_suffixes: bool = True) -> str:
    """
    Get the latest release tag from a GitHub repository.

    Raises
    ------
    ValueError
        If no tags are found.
    """
    version: str | None = None
    session = cached_session()
    if (not skip_releases
            and (r := session.get(f'https://api.github.com/repos/{owner}/{repo}/releases/latest',
                                  timeout=15)).ok):
        version = r.json()['tag_name']
    if (not version and
        (r := session.get(f'https://api.github.com/repos/{owner}/{repo}/tags', timeout=15)).ok
            and (tags := [x['name'] for x in r.json() if 'name' in x])):
        if actions or (owner == 'google' and repo == 'yapf'):
            version = next(
                x for x in tags
                if x.startswith('v') and (re.search(r'\d$', x) if not allow_suffixes else True))
        else:
            version = tags[0]
    if not version:
        msg = f'Could not get latest tag for {owner}/{repo}.'
        raise ValueError(msg)
    if actions:
        return version.split('.')[0]
    return version


NATIVE_CALLBACKS: dict[str, tuple[tuple[str, ...], Callable[..., object]]] = {
    'githubLatestActionTag': (('owner', 'repo'), lambda owner, repo: get_github_release_latest_tag(
        owner, repo, actions=True, skip_releases=True, allow_suffixes=False)),
    'githubLatestReleaseTag': (('owner', 'repo'), get_github_release_latest_tag),
    'githubLatestTag': (
        ('owner', 'repo'),
        lambda owner, repo: get_github_release_latest_tag(owner, repo, skip_releases=True)),
    'isodate': ((), lambda: datetime.now(tz=timezone.utc).isoformat()[:10]),
    'latestNpmPackageVersion': (('package',), get_npm_latest_package_version),
    'latestPypiPackageVersion': (('package',), get_pypi_latest_package_version),
    'latestYarnVersion': ((), get_latest_yarn_version),
    'year': ((), lambda: datetime.now(tz=timezone.utc).year),
}


def evaluate_jsonnet_file(jpathdir: list[str], file: Path, merged_settings: str) -> str:
    """Evaluate a Jsonnet file with the given settings."""
    return _jsonnet.evaluate_file(str(file),
                                  jpathdir=jpathdir,
                                  native_callbacks=NATIVE_CALLBACKS,
                                  tla_codes={'settings': merged_settings})


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


def evaluate_merged_settings(jpathdir: list[str],
                             lib_path: Path,
                             settings: str,
                             *,
                             user_defaults: bool = False) -> tuple[str, Settings]:
    """
    Evaluate the merged settings using Jsonnet.

    Raises
    ------
    FileNotFoundError
        If the ``user_defaults`` option is given but no user defaults file exists.
    """
    user_defaults_jsonnet = platformdirs.user_config_path('wiswa') / 'defaults.jsonnet'
    if user_defaults and not user_defaults_jsonnet.exists():
        msg = ('The user_defaults=True option was given, but no defaults.jsonnet file exists in'
               f' the user preferences directory (path: {user_defaults_jsonnet}).')
        raise FileNotFoundError(msg)
    s = _jsonnet.evaluate_snippet(
        '',
        'function(defaults, user_defaults, settings) defaults + user_defaults + settings',
        jpathdir=jpathdir,
        native_callbacks=NATIVE_CALLBACKS,
        tla_codes={
            'defaults': (lib_path.resolve(strict=True) / 'defaults.libjsonnet').read_text(),
            'settings': settings,
            'user_defaults': user_defaults_jsonnet.read_text() if user_defaults else '{}',
        })
    return s, (json.loads(s) | {'_readme_existed': Path('README.md').exists()})


def download_yarn(version: str) -> None:
    r = cached_session().get(f'https://repo.yarnpkg.com/{version}/packages/yarnpkg-cli/bin/yarn.js',
                             timeout=15)
    r.raise_for_status()
    releases_dir = Path('.yarn/releases')
    rmtree(releases_dir, ignore_errors=True)
    releases_dir.mkdir(parents=True, exist_ok=True)
    target = releases_dir / f'yarn-{version}.cjs'
    target.write_text(f'{r.text.strip()}\n', encoding='utf-8')
    target.chmod(0o755)


def _get_repo_config(settings: Settings) -> dict[str, Any]:
    return {
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
    }


def _setup_github_session() -> tuple[requests_cache.CachedSession, str] | None:
    """Set up GitHub API session with authentication."""
    token = keyring.get_password('tmu-github-api', getpass.getuser())
    if not token:
        log.warning('No GitHub token.')
        return None

    session = cached_session()
    session.headers.update({
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28'
    })
    return session, 'https://api.github.com'


def _configure_github_repo(session: requests_cache.CachedSession, host: str, repo_name: str,
                           settings: Settings) -> None:
    """Configure basic repository settings."""
    session.patch(f'{host}/repos/{repo_name}', json=_get_repo_config(settings)).raise_for_status()
    session.put(f'{host}/repos/{repo_name}/topics',
                json={
                    'names': [x.replace(' ', '-') for x in settings['keywords']]
                }).raise_for_status()

    # Enable security features
    for endpoint in [
            'automated-security-fixes', 'private-vulnerability-reporting', 'vulnerability-alerts'
    ]:
        session.put(f'{host}/repos/{repo_name}/{endpoint}').raise_for_status()


def setup_github_project(settings: Settings) -> None:
    if not settings['using_github']:
        log.debug('Not running GitHub setup.')
        return

    session_data = _setup_github_session()
    if not session_data:
        return

    session, host = session_data
    suffix = settings['repository_uri'].split('/')[-1]
    repo_name = f"{settings['repository_uri'].split('/')[-2]}/{suffix}"

    try:
        _configure_github_repo(session, host, repo_name, settings)
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
    except requests.HTTPError as e:
        log.warning('Caught error updating repo: %s.', e.response.text)
