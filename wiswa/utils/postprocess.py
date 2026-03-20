"""Post-processing steps after project generation."""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from functools import cache
from pathlib import Path
from shlex import quote
from shutil import rmtree
from typing import TYPE_CHECKING, Any
from urllib.parse import quote as urllib_quote, urlencode
import json
import logging
import subprocess as sp

import tomlkit

if TYPE_CHECKING:
    from wiswa.typing import Settings

__all__ = ('post_process_steps',)

log = logging.getLogger(__name__)


def _subprocess_log_run(*args: Any, **kwargs: Any) -> sp.CompletedProcess[Any]:
    assert isinstance(args[0], Iterable)
    log.debug('Running command: %s', ' '.join(quote(x) for x in args[0]))
    return sp.run(*args, check=kwargs.pop('check', True), **kwargs)


def _post_process_steps_python(settings: Settings) -> None:
    is_uv = settings['package_manager'] == 'uv'
    if is_uv:
        Path('poetry.lock').unlink(missing_ok=True)
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
        if is_uv:
            pyproject_content.get('dependency-groups', {}).pop('docs', None)
        else:
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
        if is_uv:
            pyproject_content.get('dependency-groups', {}).pop('tests', None)
        else:
            del pyproject_content['tool']['poetry']['group']['tests']
        del pyproject_content['tool']['pytest']
        rmtree('tests', ignore_errors=True)
    run_cmd = 'uv run' if is_uv else 'poetry run'
    package_json_content = json.loads(Path('package.json').read_text(encoding='utf-8'))
    if not settings['want_yapf']:
        del pyproject_content['tool']['yapf']
        del pyproject_content['tool']['yapfignore']
        pyproject_content['tool']['ruff']['lint']['ignore'] = sorted(
            pyproject_content['tool']['ruff']['lint']['ignore'] + ['Q000', 'Q003'])
        package_json_content['scripts']['check-formatting'] = (
            f'prettier -c . && {run_cmd} ruff format --check . && markdownlint-cli2')
        package_json_content['scripts']['format'] = (
            f'prettier -w . && {run_cmd} ruff format . && markdownlint-cli2')
    Path('package.json').write_text(json.dumps(package_json_content, indent=2, sort_keys=True),
                                    encoding='utf-8')
    Path('pyproject.toml').write_text(tomlkit.dumps(pyproject_content), encoding='utf-8')
    if is_uv:
        _subprocess_log_run(('uv', 'lock'))
        groups = [
            g for g in ('docs' if settings['want_docs'] else '',
                        'tests' if settings['want_tests'] else '', 'dev') if g
        ]
        group_args = tuple(f'--group={g}' for g in groups)
        _subprocess_log_run(('uv', 'sync', *group_args))
        _subprocess_log_run(('uv', 'run', 'ruff', 'check', '--fix'), check=False)
    else:
        _subprocess_log_run(('poetry', 'lock'))
        with_arg = ','.join(x for x in ('docs' if settings['want_docs'] else '',
                                        'tests' if settings['want_tests'] else '', 'dev') if x)
        _subprocess_log_run(('poetry', 'update', *((f'--with={with_arg}',) if with_arg else ())))
        _subprocess_log_run(('poetry', 'install', '--all-groups', '--all-extras'))
        _subprocess_log_run(('poetry', 'run', 'ruff', 'check', '--fix'), check=False)


@cache
def _simple_icons_badge(anchor_text: str, logo: str, label: str, color: str, uri: str) -> str:
    return (f'[![{anchor_text}](https://img.shields.io/badge/{label}-{color}?logo={logo})]({uri})')


def _project_type_badges(settings: Settings) -> Iterator[str]:
    match settings['project_type']:
        case 'python' if not settings['private']:
            yield (f"[![Python versions](https://img.shields.io/pypi/pyversions/"
                   f"{settings['pypi_project_name']}.svg?color=blue&logo=python&logoColor=white)]"
                   "(https://www.python.org/)")
            yield (f"[![PyPI - Version](https://img.shields.io/pypi/v/{settings['project_name']})]"
                   f"(https://pypi.org/project/{settings['pypi_project_name']}/)")
        case 'c':
            yield _simple_icons_badge('C', 'c', 'C', '00599C',
                                      'https://en.wikipedia.org/wiki/C_(programming_language)')
        case 'c++':
            yield _simple_icons_badge('C++', 'c%2B%2B', 'C++', '00599C', 'https://isocpp.org')
        case 'lua':
            yield _simple_icons_badge('Lua', 'lua', 'Lua', '2C2D72', 'https://www.lua.org/')
        case 'xcode':
            yield _simple_icons_badge('Xcode', 'xcode', 'Xcode', '007ACC',
                                      'https://developer.apple.com/xcode/')


def _github_badges(settings: Settings) -> Iterator[str]:
    if not settings['using_github']:
        return
    gh = settings['github']['username']
    name = settings['project_name']
    repo_uri = settings['repository_uri']
    branch = settings['default_branch']
    yield (f'[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/{gh}/{name})]'
           f'({repo_uri}/tags)')
    yield (f'[![License](https://img.shields.io/github/license/{gh}/{name})]'
           f'({repo_uri}/blob/{branch}/LICENSE.txt)')
    yield (f"[![GitHub commits since latest release (by SemVer including pre-releases)]"
           f"(https://img.shields.io/github/commits-since/{gh}/{name}"
           f"/v{settings['version']}/{branch})]"
           f"({repo_uri}/compare/v{settings['version']}...{branch})")
    if settings['want_codeql']:
        yield (f'[![CodeQL]({repo_uri}/actions/workflows/codeql.yml/badge.svg)]'
               f'({repo_uri}/actions/workflows/codeql.yml)')
    yield (f'[![QA]({repo_uri}/actions/workflows/qa.yml/badge.svg)]'
           f'({repo_uri}/actions/workflows/qa.yml)')
    if settings['want_tests']:
        yield (f'[![Tests]({repo_uri}/actions/workflows/tests.yml/badge.svg)]'
               f'({repo_uri}/actions/workflows/tests.yml)')
        yield (f'[![Coverage Status](https://coveralls.io/repos/github/{gh}/{name}/badge.svg?'
               f'branch=master)](https://coveralls.io/github/{gh}/{name}?branch={branch})')
    yield _simple_icons_badge('Dependabot', 'dependabot', 'Dependabot-enabled', 'blue',
                              'https://github.com/dependabot')


def _docs_badges(settings: Settings) -> Iterator[str]:
    if not settings['want_docs']:
        return
    if settings['project_type'] == 'python' and not settings['private']:
        yield (
            f"[![Documentation Status](https://readthedocs.org/projects/{settings['project_name']}"
            f"/badge/?version=latest)]({settings['documentation_uri']}/?badge=latest)")
    elif settings['using_github']:
        gh = settings['github']['username']
        name = settings['project_name']
        yield (f'[![GitHub Pages](https://github.com/{gh}/{name}/badge/pages)]'
               f'(https://{gh}.github.io/{name}/)')


def _get_main_dependency_names(settings: Settings) -> set[str]:
    names = set(settings['python_deps']['main'])
    if settings['package_manager'] == 'uv':
        names |= {
            dep.split('>')[0].split('<')[0].split('=')[0].split('!')[0].split('[')[0].strip()
            for dep in settings['pyproject']['project'].get('dependencies', ())
        }
    return names


def _python_tool_badges(settings: Settings) -> Iterator[str]:
    if settings['project_type'] != 'python':
        return
    if settings['using_django']:
        yield _simple_icons_badge('Django', 'django', 'Django', '092E20',
                                  'https://djangoproject.com')
    yield '[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)'
    yield _simple_icons_badge('pre-commit', 'pre-commit', 'pre--commit-enabled', 'brightgreen',
                              'https://pre-commit.com/')
    if settings['package_manager'] == 'uv':
        yield _simple_icons_badge('uv', 'astral', 'uv', '261230', 'https://docs.astral.sh/uv/')
    else:
        yield _simple_icons_badge('Poetry', 'poetry', 'Poetry', '242d3e',
                                  'https://python-poetry.org')
    dep_names = _get_main_dependency_names(settings)
    name_mapping = {'jinja': 'Jinja', 'pydantic': 'Pydantic', 'sqlalchemy': 'SQLAlchemy'}
    yield from (_simple_icons_badge(name_mapping.get(package, package), package,
                                    name_mapping.get(package, package), 'black',
                                    f'https://pypi.org/project/{package}/')
                for package in ('numpy', 'jinja', 'pandas', 'pydantic', 'scrapy', 'sqlalchemy')
                if package in dep_names)
    if not settings['stubs_only'] and settings['want_tests']:
        yield _simple_icons_badge('pydocstyle', 'pydocstyle', 'pydocstyle-enabled', 'AD4CD3',
                                  'https://www.pydocstyle.org/')
        yield _simple_icons_badge('pytest', 'pytest', 'pytest-enabled', 'CFB97D',
                                  'https://docs.pytest.org')
    yield ('[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com'
           '/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)')
    if not settings['private']:
        yield (f"[![Downloads](https://static.pepy.tech/badge/{settings['project_name']}/month)]"
               f"(https://pepy.tech/project/{settings['project_name']})")


def _typescript_badges(settings: Settings) -> list[str]:
    if settings['project_type'] != 'typescript':
        return []
    return sorted(
        (*(_simple_icons_badge(dep, dep.replace('-', ''), dep, 'black',
                               f'https://www.npmjs.com/package/{dep}')
           for dep in ('bootstrap', 'react', 'sass', 'semantic-ui-react', 'sass', 'tailwindcss')
           if dep in settings['package_json'].get('dependencies', {})),
         *(_simple_icons_badge(dev_dep, dev_dep.replace('-', ''), dev_dep, 'black',
                               f'https://www.npmjs.com/package/{dev_dep}')
           for dev_dep in ('eslint', 'jest')
           if dev_dep in settings['package_json']['devDependencies']),
         _simple_icons_badge('TypeScript', 'typescript', 'TypeScript', 'black',
                             'https://www.typescriptlang.org/'),
         _simple_icons_badge('Yarn', 'yarn', 'Yarn', '4c335c', 'https://yarnpkg.com/'),
         *((_simple_icons_badge('Next.js', 'nextdotjs', 'Next.js', '000000', 'https://nextjs.org/'),
            ) if 'next' in settings['package_json'].get('dependencies', {}) else ())))


def _misc_badges(settings: Settings) -> Iterator[str]:
    if Path('Dockerfile').exists():
        yield _simple_icons_badge('Docker', 'docker', 'Docker', 'black', 'https://www.docker.com/')
    if settings['using_github']:
        gh = settings['github']['username']
        name = settings['project_name']
        yield (f'[![Stargazers](https://img.shields.io/github/stars/{gh}/{name}'
               f'?logo=github&style=flat)](https://github.com/{gh}/{name}/stargazers)')
    if (settings['project_type'] in {'c', 'c++'} and Path('CMakeLists.txt').exists()):
        yield _simple_icons_badge('CMake', 'cmake', 'CMake', '6E6E6E', 'https://cmake.org/')
    yield _simple_icons_badge('Prettier', 'prettier', 'Prettier-enabled', 'black',
                              'https://prettier.io/')


def _social_badges(settings: Settings) -> Iterator[str]:
    keywords_to_args: dict[str, tuple[str, str, str, str, str]] = {
        'dotnet': ('.NET', 'dotnet', '.NET', '512BD4', 'https://dotnet.microsoft.com/'),
        'ffmpeg': ('FFmpeg', 'ffmpeg', 'FFmpeg', 'orange', 'https://ffmpeg.org/'),
        'kde': ('KDE Plasma', 'kdeplasma', 'KDE Plasma', 'blue', 'https://kde.org/'),
        'qt': ('Qt', 'qt', 'Qt', '41cd52', 'https://www.qt.io/'),
        'swift': ('Swift', 'swift', 'Swift', 'F05138', 'https://swift.org/'),
    }
    for keyword, args in keywords_to_args.items():
        if keyword in settings['keywords']:
            yield _simple_icons_badge(*args)
    social = settings['social']
    if bsky := social.get('bsky'):
        outer_params = urlencode({
            'label': f'Follow @{bsky}',
            'logo': 'bluesky',
            'style': 'social'
        },
                                 errors='strict')
        url = urllib_quote('https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile/?',
                           safe='',
                           errors='strict') + urlencode({
                               'actor': 'did:plc:uq42idtvuccnmtl57nsucz72',
                               'query': '$.followersCount'
                           })
        yield (f'[![@{bsky}]'
               f'(https://img.shields.io/badge/dynamic/json?url={url}&{outer_params})]'
               f'(https://bsky.app/profile/{bsky}.bsky.social)')
    if username := social.get('buymeacoffee'):
        yield _simple_icons_badge('Buy Me A Coffee', 'buymeacoffee',
                                  f'Buy%20Me%20a%20Coffee-{username}', 'black',
                                  f'https://buymeacoffee.com/{username}')
    if ((text := social.get('calendly', {}).get('text'))
            and (uri := social.get('calendly', {}).get('uri'))):
        yield _simple_icons_badge('Calendly', 'calendly', text, '00a2ff', uri)
    if username := social.get('cashapp'):
        yield _simple_icons_badge('Cash App', 'cashapp', f'Cash%20App-{username}', '00C244',
                                  f'https://cash.app/{username}')
    if libera_irc := social.get('libera_irc'):
        yield _simple_icons_badge('Libera.Chat', 'liberadotchat', f'Libera.Chat-{libera_irc}',
                                  'black', f'irc://irc.libera.chat/{libera_irc}')
    if ((mastodon_id := social.get('mastodon', {}).get('id'))
            and (domain := social.get('mastodon', {}).get('domain'))):
        yield (
            f"[![Mastodon Follow](https://img.shields.io/mastodon/follow/{mastodon_id}?"
            f"domain={domain}&style=social)](https://{domain}/@{settings['github']['username']})")
    if username := social.get('patreon'):
        yield _simple_icons_badge('Patreon', 'patreon', f'Patreon-{username}', 'F96854',
                                  f'https://www.patreon.com/{username}')
    if social.get('slashdot'):
        yield _simple_icons_badge('Slashdot', 'slashdot', social['slashdot'], '066665',
                                  f'https://slashdot.org/~{social["slashdot"]}')
    if ((uri := social.get('youtube', {}).get('uri'))
            and (text := social.get('youtube', {}).get('text'))):
        yield _simple_icons_badge('YouTube', 'youtube', text, 'FF0000', uri)
    yield from social.get('custom_badges', [])


def _replace_badge_section(readme: Path, lines: Sequence[str], expected: Sequence[str],
                           social_expected: Sequence[str]) -> None:
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


def _check_readme_badges(settings: Settings) -> None:
    log.debug('Checking README.md badges.')
    if not settings['_readme_existed']:
        log.debug('README.md did not exist before templating; skipping badge check.')
        return
    readme = Path('README.md')
    if not readme.exists():
        log.debug('README.md was removed; skipping badge check.')
        return
    _replace_badge_section(
        readme,
        readme.read_text(encoding='utf-8').split('\n'),
        (*_project_type_badges(settings), *_github_badges(settings), *_docs_badges(settings),
         *_python_tool_badges(settings), *_misc_badges(settings), *_typescript_badges(settings)),
        list(_social_badges(settings)))
    log.debug('Updated README.md badges.')


def post_process_steps(settings: Settings) -> None:
    """
    Run post-processing steps after project generation.

    Parameters
    ----------
    settings : Settings
        Project settings.
    """
    match settings['project_type']:
        case 'python':
            _post_process_steps_python(settings)
        case _:
            log.warning('No post-processing steps for project type `%s`.', settings['project_type'])
    _check_readme_badges(settings)
    package_json = Path('package.json')
    package_json.write_text(json.dumps(json.loads(package_json.read_text(encoding='utf-8')),
                                       indent=2,
                                       sort_keys=True),
                            encoding='utf-8')
    _subprocess_log_run(('yarn',))
    _subprocess_log_run(('yarn', 'format'), check=False)
