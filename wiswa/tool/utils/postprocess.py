"""Post-process a generated project (lock files, tooling, README badges, Yarn)."""
from __future__ import annotations

from functools import cache, partial
from pathlib import Path
from shlex import quote
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import quote as urllib_quote, urlencode
import asyncio
import json
import logging
import os
import re
import shutil
import tempfile

from anyio.to_thread import run_sync
from niquests import AsyncSession
import anyio
import niquests
import tomlkit

from .github import get_github_pages_build_type
from .versions import get_github_release_latest_tag

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable, Iterator, Sequence

    from wiswa.tool.typing import ExportRequirements, Settings

__all__ = ('apply_python_pyproject_manifest_edits', 'maybe_revert_uv_lock_if_only_lockfile_changed',
           'post_process_steps', 'resolve_changelog_boilerplate_urls',
           'uv_lock_diff_changes_only_exclude_newer')

log = logging.getLogger(__name__)

_README_GENERATED_START = '<!-- WISWA-GENERATED-README:START -->'
_README_GENERATED_STOP = '<!-- WISWA-GENERATED-README:STOP -->'

_GIT_CONFIG_NO_HOOKS = ('-c', f'core.hooksPath={os.devnull}')

_FORMAT_DEFAULT_FILENAMES = {'cyclonedx1.5': 'cyclonedx.json', 'pylock.toml': 'pylock.toml'}
_LEGACY_WISWA_AI_PATHS = ('.claude/settings.local.json.dist', '.cursor/permissions.json.dist',
                          '.cursor/rules/general.mdc', '.cursor/rules/json-yaml.mdc',
                          '.cursor/rules/markdown.mdc', '.cursor/rules/toml-ini.mdc',
                          '.cursor/rules/cpp.mdc', '.cursor/rules/python.mdc',
                          '.cursor/rules/python-tests.mdc', '.github/copilot-instructions.md',
                          '.github/instructions/general.instructions.md',
                          '.github/instructions/json-yaml.instructions.md',
                          '.github/instructions/markdown.instructions.md',
                          '.github/instructions/toml-ini.instructions.md',
                          '.github/instructions/cpp.instructions.md',
                          '.github/instructions/python.instructions.md',
                          '.github/instructions/python-tests.instructions.md')

# Fallbacks for the standard CHANGELOG.md boilerplate when GitHub resolution is unavailable.
# Keep a Changelog publishes its website independently of its GitHub release tags, so the latest
# release tag may not yet be reachable on keepachangelog.com.
_CHANGELOG_KEEP_A_CHANGELOG_FALLBACK_URL = 'https://keepachangelog.com/en/1.1.0/'
_CHANGELOG_SEMVER_SPEC_FALLBACK_URL = 'https://semver.org/spec/v2.0.0.html'
_RE_CHANGELOG_KEEP_A_CHANGELOG = re.compile(r'https://keepachangelog\.com/en/\d+\.\d+\.\d+/')
_RE_CHANGELOG_SEMVER_SPEC = re.compile(r'https://semver\.org/spec/v\d+\.\d+\.\d+\.html')
_RE_DEPLOY_PAGES = re.compile(r'uses:\s*actions/deploy-pages')

_GITHUB_TAG_RESOLUTION_EXC_TYPES = (KeyError, OSError, TypeError, ValueError,
                                    niquests.JSONDecodeError, niquests.RequestException)


@cache
def _keep_a_changelog_documentation_url(release_tag: str) -> str:
    without_v = release_tag.strip().removeprefix('v')
    return f'https://keepachangelog.com/en/{without_v}/'


@cache
def _semver_spec_documentation_url(release_tag: str) -> str:
    tag = release_tag.strip()
    if not tag.startswith('v'):
        tag = f'v{tag}'
    return f'https://semver.org/spec/{tag}.html'


async def _is_url_reachable(session: AsyncSession, url: str) -> bool:
    try:
        resp = await session.head(url, timeout=10, allow_redirects=True)
    except niquests.RequestException as exc:
        log.warning('HEAD `%s` failed (%s); treating as unreachable.', url, exc)
        return False
    return bool(resp.ok)


async def _resolve_keep_a_changelog_url(session: AsyncSession | None) -> str:
    if session is None:
        return _CHANGELOG_KEEP_A_CHANGELOG_FALLBACK_URL
    try:
        tag = await get_github_release_latest_tag(session, 'olivierlacan', 'keep-a-changelog')
    except _GITHUB_TAG_RESOLUTION_EXC_TYPES as exc:
        log.warning('Keep a Changelog version from GitHub failed (%s); using fallback URL.', exc)
        return _CHANGELOG_KEEP_A_CHANGELOG_FALLBACK_URL
    candidate = _keep_a_changelog_documentation_url(tag)
    if await _is_url_reachable(session, candidate):
        return candidate
    log.warning('Keep a Changelog URL `%s` is not reachable; using fallback URL `%s`.', candidate,
                _CHANGELOG_KEEP_A_CHANGELOG_FALLBACK_URL)
    return _CHANGELOG_KEEP_A_CHANGELOG_FALLBACK_URL


async def _resolve_semver_spec_url(session: AsyncSession | None) -> str:
    if session is None:
        return _CHANGELOG_SEMVER_SPEC_FALLBACK_URL
    try:
        tag = await get_github_release_latest_tag(session, 'semver', 'semver')
    except _GITHUB_TAG_RESOLUTION_EXC_TYPES as exc:
        log.warning('SemVer spec tag from GitHub failed (%s); using fallback URL.', exc)
        return _CHANGELOG_SEMVER_SPEC_FALLBACK_URL
    return _semver_spec_documentation_url(tag)


async def resolve_changelog_boilerplate_urls(session: AsyncSession | None) -> tuple[str, str]:
    """
    Resolve Keep a Changelog and SemVer documentation URLs for generated boilerplate.

    Uses the same GitHub tag resolution as :func:`post_process_steps` (with fallbacks
    when ``session`` is ``None`` or the API fails).

    Parameters
    ----------
    session : AsyncSession | None
        HTTP session for GitHub API calls, or ``None`` to use fallback URLs.

    Returns
    -------
    tuple[str, str]
        Keep a Changelog documentation URL and SemVer specification URL.
    """
    keep = await _resolve_keep_a_changelog_url(session)
    semver = await _resolve_semver_spec_url(session)
    return keep, semver


def _normalise_changelog_reference_urls(content: str, keep_a_changelog_url: str,
                                        semver_spec_url: str) -> str:
    step1 = _RE_CHANGELOG_KEEP_A_CHANGELOG.sub(keep_a_changelog_url, content)
    return _RE_CHANGELOG_SEMVER_SPEC.sub(semver_spec_url, step1)


async def _refresh_changelog_reference_urls(session: AsyncSession | None) -> None:
    changelog = anyio.Path('CHANGELOG.md')
    if not await changelog.is_file():
        return
    keep_url = await _resolve_keep_a_changelog_url(session)
    semver_url = await _resolve_semver_spec_url(session)
    text = await changelog.read_text(encoding='utf-8')
    updated = _normalise_changelog_reference_urls(text, keep_url, semver_url)
    if updated == text:
        return
    await changelog.write_text(updated, encoding='utf-8')
    log.debug('Updated CHANGELOG.md Keep a Changelog and Semantic Versioning links.')


async def _remove_legacy_wiswa_ai_files() -> None:
    """Delete Cursor/Copilot instruction files emitted by older Wiswa releases."""
    for relative in _LEGACY_WISWA_AI_PATHS:
        path = anyio.Path(relative)
        if await path.is_file():
            await path.unlink()
            log.debug('Removed legacy Wiswa AI file `%s`.', relative)


async def _create_wiswa_ci_cache_dirs(settings: Settings) -> None:
    """
    Create ``.wiswa-ci/cache`` subdirectories for tool caches when ``want_ai`` is enabled.

    Tools launched from Claude Code subprocesses use environment variables (``UV_CACHE_DIR``,
    ``YARN_CACHE_FOLDER``, ``MYPY_CACHE_DIR``, ``RUFF_CACHE_DIR``) set in
    ``.claude/settings.json`` to redirect their caches into this tree so writes land inside the
    repo (sandbox-writable and gitignored) rather than ``~/.cache``. Pre-creating the
    directories keeps tools that refuse to auto-create their cache parent from failing on first
    run.

    Parameters
    ----------
    settings : Settings
        Project settings.
    """
    if not settings['want_ai']:
        return
    for subdir in ('mypy', 'ruff', 'uv', 'yarn'):
        await anyio.Path(f'.wiswa-ci/cache/{subdir}').mkdir(parents=True, exist_ok=True)
    log.debug('Created `.wiswa-ci/cache` subdirectories.')


async def _subprocess_log_run(
        cmd: Iterable[str],
        on_command: Callable[[str], None] | None = None,
        **kwargs: Any) -> tuple[asyncio.subprocess.Process, bytes | None, bytes | None]:
    cmd_str = ' '.join(quote(x) for x in cmd)
    log.debug('Running command: `%s`', cmd_str)
    if on_command is not None:
        on_command(cmd_str)
    check = kwargs.pop('check', True)
    proc = await asyncio.create_subprocess_exec(*cmd, **kwargs)
    stdout, stderr = await proc.communicate()
    if check and proc.returncode != 0:
        msg = f'Command `{cmd_str}` returned non-zero exit status {proc.returncode}.'
        raise RuntimeError(msg)
    return proc, stdout, stderr


def _clang_format_file_paths(clang_format_args: str) -> list[str]:
    root = Path()
    seen: set[str] = set()
    out: list[str] = []
    for token in clang_format_args.split():
        matches = sorted(str(p) for p in root.glob(token))
        if matches:
            for p in matches:
                if p not in seen:
                    seen.add(p)
                    out.append(p)
        elif token not in seen:
            seen.add(token)
            out.append(token)
    return out


async def _run_prettier_then_markdownlint_fix(*, debug: bool,
                                              on_command: Callable[[str], None] | None,
                                              env: dict[str, str]) -> None:
    """
    Run Prettier, then markdownlint-cli2 with a temporary config overlay.

    Prettier uses ``--log-level silent`` when not in debug mode. Markdownlint uses a temporary
    config derived from ``package.json`` with ``showFound`` and ``noProgress`` adjusted for
    post-processing output.
    """
    await _subprocess_log_run(('yarn', 'prettier', '--write', '--ignore-unknown',
                               *(('--log-level', 'silent') if not debug else ()), '.'),
                              env=env,
                              on_command=on_command,
                              stderr=asyncio.subprocess.PIPE,
                              stdout=asyncio.subprocess.PIPE,
                              check=False)
    with tempfile.NamedTemporaryFile(mode='w',
                                     encoding='utf-8',
                                     prefix='wiswa-markdownlint-',
                                     suffix='.json',
                                     delete=False) as tmp:
        pkg = json.loads(await anyio.Path('package.json').read_text(encoding='utf-8'))
        json.dump(
            {
                'markdownlint-cli2':
                    dict(pkg.get('markdownlint-cli2', {})) | {
                        'showFound': False,
                        'noProgress': False
                    }
            },
            tmp,
            indent=2)
        tmp.write('\n')
        tmp.flush()
    await _subprocess_log_run(('yarn', 'markdownlint-cli2', '--config', tmp.name, '--configPointer',
                               '/markdownlint-cli2', '--fix'),
                              env=env,
                              on_command=on_command,
                              stderr=asyncio.subprocess.PIPE,
                              stdout=asyncio.subprocess.PIPE,
                              check=False)
    await anyio.Path(tmp.name).unlink()


async def _run_postprocess_language_formatters(settings: Settings, *, debug: bool,
                                               on_command: Callable[[str], None] | None,
                                               env: dict[str, str]) -> None:
    """Run YAPF or Ruff (Python), or clang-format (C/C++), after Prettier and markdownlint."""
    match settings['project_type']:
        case 'python':
            is_uv = settings['package_manager'] == 'uv'
            quiet_uv_poetry: tuple[str, ...] = () if debug else ('--quiet',)
            run_cmd: tuple[str, ...] = (('uv', *quiet_uv_poetry, 'run') if is_uv else
                                        ('poetry', *quiet_uv_poetry, 'run'))
            if settings['want_yapf']:
                await _subprocess_log_run(
                    (*run_cmd, 'yapf', '--in-place', '--parallel', '--recursive', '.'),
                    env=env,
                    on_command=on_command,
                    stderr=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    check=False)
            else:
                await _subprocess_log_run((*run_cmd, 'ruff', 'format', *(() if debug else
                                                                         ('--quiet',)), '.'),
                                          env=env,
                                          on_command=on_command,
                                          stderr=asyncio.subprocess.PIPE,
                                          stdout=asyncio.subprocess.PIPE,
                                          check=False)
        case 'c' | 'c++':
            if paths := _clang_format_file_paths(
                    str(settings.get('clang_format_args', 'src/*.cpp src/*.h'))):
                await _subprocess_log_run(('clang-format', *(('--verbose',) if debug else
                                                             ()), '--in-place', *paths),
                                          env=env,
                                          on_command=on_command,
                                          stderr=asyncio.subprocess.PIPE,
                                          stdout=asyncio.subprocess.PIPE,
                                          check=False)


def _resolve_output_filename(er: ExportRequirements) -> str:
    if explicit := er.get('output_filename', ''):
        return explicit
    return _FORMAT_DEFAULT_FILENAMES.get(er.get('format', 'requirements.txt'), 'requirements.txt')


_UV_EXPORT_PRE_OUTPUT_BOOL_FLAGS: tuple[tuple[str, str, bool],
                                        ...] = (('all_packages', '--all-packages',
                                                 False), ('all_extras', '--all-extras',
                                                          False), ('no_dev', '--no-dev', False),
                                                ('only_dev', '--only-dev', False),
                                                ('no_default_groups', '--no-default-groups',
                                                 False), ('all_groups', '--all-groups', False),
                                                ('no_annotate', '--no-annotate',
                                                 False), ('no_header', '--no-header', False),
                                                ('no_editable', '--no-editable', False))
"""
Boolean keys mapped to ``uv export`` flags emitted before ``--output-file``.

:meta hide-value:
"""

_UV_EXPORT_POST_OUTPUT_BOOL_FLAGS: tuple[tuple[str, str, bool],
                                         ...] = (('no_emit_project', '--no-emit-project', True),
                                                 ('no_emit_workspace', '--no-emit-workspace',
                                                  False), ('no_emit_local', '--no-emit-local',
                                                           False), ('locked', '--locked', False),
                                                 ('frozen', '--frozen', False))
"""
Boolean keys mapped to ``uv export`` flags emitted after ``--output-file``.

:meta hide-value:
"""

_UV_EXPORT_PRE_OUTPUT_LIST_FLAGS: tuple[tuple[str, str],
                                        ...] = (('package', '--package'), ('prune', '--prune'),
                                                ('extra', '--extra'), ('no_extra', '--no-extra'),
                                                ('group', '--group'), ('no_group', '--no-group'),
                                                ('only_group', '--only-group'))
"""
Sequence keys mapped to ``uv export`` flags emitted before ``--output-file``.

:meta hide-value:
"""


def _build_uv_export_args(settings: Settings, quiet_arg: tuple[str, ...] = ()) -> tuple[str, ...]:
    er = settings['export_requirements']
    args: list[str] = ['uv', *quiet_arg, 'export']
    if er.get('format', 'requirements.txt') != 'requirements.txt':
        args.extend(('--format', er['format']))
    for key, flag, default in _UV_EXPORT_PRE_OUTPUT_BOOL_FLAGS:
        if er.get(key, default):
            args.append(flag)
    for key, flag in _UV_EXPORT_PRE_OUTPUT_LIST_FLAGS:
        for val in cast('Sequence[str]', er.get(key, [])):
            args.extend((flag, val))
    if er.get('no_hashes', False) or not er.get('with_hashes', True):
        args.append('--no-hashes')
    args.extend(('--output-file', _resolve_output_filename(er)))
    for key, flag, default in _UV_EXPORT_POST_OUTPUT_BOOL_FLAGS:
        if er.get(key, default):
            args.append(flag)
    for val in er.get('no_emit_package', []):
        args.extend(('--no-emit-package', val))
    if script := er.get('script', ''):
        args.extend(('--script', script))
    return tuple(args)


def _build_poetry_export_args(
    settings: Settings, quiet_arg: tuple[str, ...] = ()) -> tuple[str, ...]:
    er = settings['export_requirements']
    args: list[str] = ['poetry', *quiet_arg, 'export']
    if er.get('all_extras', False):
        args.append('--all-extras')
    else:
        args.extend(f'--extras={extra}' for extra in er.get('extra', []))
    args.extend(('--format', er.get('format', 'requirements.txt')))
    args.extend(('--output', _resolve_output_filename(er)))
    group_list: list[str] = []
    if not er.get('no_dev', False):
        group_list.append('dev')
    if er.get('all_groups', False):
        if settings['want_docs']:
            group_list.append('docs')
        if settings['want_tests']:
            group_list.append('tests')
    else:
        group_list.extend(er.get('group', []))
    if group_list:
        args.append(f"--with={','.join(group_list)}")
    if er.get('only_dev', False):
        args.append('--only=dev')
    args.extend(f'--only={og}' for og in er.get('only_group', []))
    args.extend(f'--without={ng}' for ng in er.get('no_group', []))
    if er.get('no_hashes', False) or not er.get('with_hashes', True):
        args.append('--without-hashes')
    return tuple(args)


def _prune_empty_nested_dicts(node: dict[str, Any]) -> None:
    keys_to_remove: list[str] = []
    for key, value in list(node.items()):
        if isinstance(value, dict):
            _prune_empty_nested_dicts(value)
            if not value:
                keys_to_remove.append(key)
    for key in keys_to_remove:
        del node[key]


async def apply_python_pyproject_manifest_edits(settings: Settings) -> None:
    """
    Apply the same ``pyproject.toml`` and ``package.json`` script edits as full post-processing.

    Runs when post-processing is skipped so manifests stay consistent (no empty ``[tool]``
    placeholders, dependency groups match flags, format scripts omit YAPF when disabled, etc.).

    Parameters
    ----------
    settings : Settings
        Merged project settings (must match the generated tree on disk).
    """
    pyproject_content = tomlkit.loads(
        await anyio.Path('pyproject.toml').read_text(encoding='utf-8')).unwrap()
    is_uv = settings['package_manager'] == 'uv'
    if not settings['want_docs']:
        if is_uv:
            pyproject_content.get('dependency-groups', {}).pop('docs', None)
        else:
            del pyproject_content['tool']['poetry']['group']['docs']
    if settings['want_man']:
        log.debug('Adding man pages to Commitizen version_files.')
        man = anyio.Path('man')
        if await man.exists():
            man_pages = [str(x) async for x in man.glob('*.1')]
            pyproject_content['tool']['commitizen']['version_files'] = sorted(
                {*pyproject_content['tool']['commitizen']['version_files'], *man_pages})
        else:
            module_tail = settings['primary_module_qualified'].split('.')[-1]
            pyproject_content['tool']['commitizen']['version_files'] = sorted(
                {*pyproject_content['tool']['commitizen']['version_files'], f'man/{module_tail}.1'})
    if not settings['want_tests']:
        del pyproject_content['tool']['coverage']
        if is_uv:
            pyproject_content.get('dependency-groups', {}).pop('tests', None)
        else:
            del pyproject_content['tool']['poetry']['group']['tests']
        del pyproject_content['tool']['pytest']
    run_cmd = 'uv run' if is_uv else 'poetry run'
    package_json_content = json.loads(await anyio.Path('package.json').read_text(encoding='utf-8'))
    for script_name in ('gen-docs', 'gen-manpage'):
        script_command = package_json_content['scripts'].get(script_name)
        if (isinstance(script_command, str) and 'sphinx-build' in script_command
                and '--fail-on-warning' not in script_command):
            package_json_content['scripts'][script_name] = script_command.replace(
                'sphinx-build ', 'sphinx-build --fail-on-warning ', 1)
    ml_check = 'yarn markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2'
    ml_fix = f'{ml_check} --fix'
    prettier_w = 'yarn prettier --write --ignore-unknown .'
    prettier_c = 'yarn prettier --check --ignore-unknown .'
    if not settings['want_yapf']:
        del pyproject_content['tool']['yapf']
        del pyproject_content['tool']['yapfignore']
        pyproject_content['tool']['ruff']['lint']['ignore'] = sorted(
            pyproject_content['tool']['ruff']['lint']['ignore'] + ['Q000', 'Q003'])
        package_json_content['scripts']['check-formatting'] = (
            f'{prettier_c} && {ml_check} && {run_cmd} ruff format --check .')
        package_json_content['scripts']['format'] = (
            f'{prettier_w} && {ml_fix} && {run_cmd} ruff format .')
    _prune_empty_nested_dicts(pyproject_content)
    await asyncio.gather(
        anyio.Path('package.json').write_text(json.dumps(package_json_content,
                                                         indent=2,
                                                         sort_keys=True),
                                              encoding='utf-8'),
        anyio.Path('pyproject.toml').write_text(tomlkit.dumps(pyproject_content), encoding='utf-8'))


async def _pyproject_entry_point_scripts() -> tuple[str, ...]:
    """
    Return the script names declared in ``pyproject.toml`` ``[project.scripts]``.

    Returns
    -------
    tuple[str, ...]
        Sorted tuple of script names, or an empty tuple if ``pyproject.toml`` is missing or
        declares no scripts.
    """
    content = tomlkit.loads(await anyio.Path('pyproject.toml').read_text(encoding='utf-8')).unwrap()
    scripts = (cast('dict[str, Any]', content.get('project', {})).get('scripts', {}) or {})
    return tuple(sorted(scripts))


def _pyinstaller_builds_anything(settings: Settings, scripts: Sequence[str]) -> bool:
    """
    Return whether the PyInstaller workflow would build at least one entry point.

    The workflow has work to do when either ``pyinstaller.include_only`` intersects with the
    declared scripts, or (with an empty ``include_only``) when at least one supported platform
    has at least one script not covered by its exclusion list.

    Parameters
    ----------
    settings : Settings
        Merged project settings.
    scripts : Sequence[str]
        Entry point script names from ``pyproject.toml``.

    Returns
    -------
    bool
        ``True`` when the workflow would build something, ``False`` when it would skip every
        script on every supported platform.
    """
    if not scripts:
        return False
    pyi = cast('dict[str, Any]', settings.get('pyinstaller', {})) or {}
    sp = settings.get('supported_platforms', 'all')
    include_only = tuple(pyi.get('include_only') or ())
    script_set = set(scripts)
    if include_only:
        return bool(script_set & set(include_only))
    for platform_key, exclusion_key in (('windows', 'windows_exclusions'), ('macos',
                                                                            'macos_exclusions')):
        if sp != 'all' and platform_key not in sp:
            continue
        if script_set - set(pyi.get(exclusion_key) or ()):
            return True
    return False


def _appimage_builds_anything(settings: Settings, scripts: Sequence[str]) -> bool:
    """
    Return whether the AppImage workflow would build at least one entry point.

    Parameters
    ----------
    settings : Settings
        Merged project settings.
    scripts : Sequence[str]
        Entry point script names from ``pyproject.toml``.

    Returns
    -------
    bool
        ``True`` when the workflow would build something, ``False`` when every script is
        excluded.
    """
    if not scripts:
        return False
    appimage_cfg = cast('dict[str, Any]', settings.get('appimage', {})) or {}
    script_set = set(scripts)
    include_only = tuple(appimage_cfg.get('include_only') or ())
    if include_only:
        return bool(script_set & set(include_only))
    return bool(script_set - set(appimage_cfg.get('exclusions') or ()))


async def _post_process_steps_python(settings: Settings,
                                     *,
                                     debug: bool = False,
                                     on_command: Callable[[str], None] | None = None) -> None:
    is_uv = settings['package_manager'] == 'uv'
    quiet_arg = () if debug else ('--quiet',)
    cleanup_tasks: list[Awaitable[None]] = []
    if is_uv:
        cleanup_tasks.append(anyio.Path('poetry.lock').unlink(missing_ok=True))
    if not settings['want_tests']:
        cleanup_tasks.extend((run_sync(partial(shutil.rmtree, 'tests', ignore_errors=True)),
                              anyio.Path('.github/workflows/tests.yml').unlink(missing_ok=True)))
        if (not settings['vscode']['launch']
                or (len(settings['vscode']['launch']['configurations']) == 1
                    and settings['vscode']['launch']['configurations'][0]['name'] == 'Run tests')):
            cleanup_tasks.append(anyio.Path('.vscode/launch.json').unlink(missing_ok=True))
    if not settings['want_docs']:
        cleanup_tasks.extend((run_sync(partial(shutil.rmtree, 'docs', ignore_errors=True)),
                              anyio.Path('.readthedocs.yaml').unlink(missing_ok=True)))
    if not settings['want_codeql']:
        cleanup_tasks.append(anyio.Path('.github/workflows/codeql.yml').unlink(missing_ok=True))
    scripts = await _pyproject_entry_point_scripts()
    delete_appimage = (not settings.get('want_appimage', False)
                       or not _appimage_builds_anything(settings, scripts))
    if delete_appimage:
        cleanup_tasks.append(anyio.Path('.github/workflows/appimage.yml').unlink(missing_ok=True))
    if not _pyinstaller_builds_anything(settings, scripts):
        cleanup_tasks.append(
            anyio.Path('.github/workflows/pyinstaller.yml').unlink(missing_ok=True))
    await asyncio.gather(*cleanup_tasks)
    await apply_python_pyproject_manifest_edits(settings)
    oc = on_command
    if is_uv:
        await _subprocess_log_run(('uv', *quiet_arg, 'lock', '--upgrade'), on_command=oc)
        await _subprocess_log_run(('uv', *quiet_arg, 'sync', '--all-extras', '--all-groups'),
                                  on_command=oc)
        await _subprocess_log_run(('uv', *quiet_arg, 'run', 'ruff', *quiet_arg, 'check', '--fix'),
                                  on_command=oc,
                                  check=False)
        if settings['export_requirements'].get('enabled', False):
            await _subprocess_log_run(_build_uv_export_args(settings, quiet_arg), on_command=oc)
    else:
        await _subprocess_log_run(('poetry', *quiet_arg, 'lock'), on_command=oc)
        with_arg = ','.join(x for x in ('docs' if settings['want_docs'] else '',
                                        'tests' if settings['want_tests'] else '', 'dev') if x)
        await _subprocess_log_run(
            ('poetry', *quiet_arg, 'update', *((f'--with={with_arg}',) if with_arg else ())),
            on_command=oc)
        await _subprocess_log_run(('poetry', *quiet_arg, 'install', '--all-groups', '--all-extras'),
                                  on_command=oc)
        await _subprocess_log_run(
            ('poetry', *quiet_arg, 'run', 'ruff', *quiet_arg, 'check', '--fix'),
            on_command=oc,
            check=False)
        if settings['export_requirements'].get('enabled', False):
            await _subprocess_log_run(_build_poetry_export_args(settings, quiet_arg), on_command=oc)


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
        case 'typescript' if not settings['private']:
            # The npmjs.com badges only resolve for packages on the public npm registry; for
            # projects publishing to GitHub Packages or another registry, those endpoints return
            # 404, so emit the badges only when the project targets npmjs.org (the default).
            publish_registry = (settings.get('package_json', {}).get('publishConfig', {}).get(
                'registry', '') or '')
            if not publish_registry or publish_registry.startswith('https://registry.npmjs.org'):
                yield (f"[![NPM Version](https://img.shields.io/npm/v/{settings['project_name']})]"
                       f"(https://www.npmjs.com/package/{settings['project_name']})")
                yield (
                    f"[![NPM Downloads](https://img.shields.io/npm/dm/{settings['project_name']})]"
                    f"(https://www.npmjs.com/package/{settings['project_name']})")
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


def _github_badges(settings: Settings, *, has_qa_workflow: bool = True) -> Iterator[str]:
    if not settings['using_github']:
        return
    gh = settings['github']['username']
    name = settings['github_project_name']
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
    if has_qa_workflow:
        yield (f'[![QA]({repo_uri}/actions/workflows/qa.yml/badge.svg)]'
               f'({repo_uri}/actions/workflows/qa.yml)')
    if settings['want_tests']:
        yield (f'[![Tests]({repo_uri}/actions/workflows/tests.yml/badge.svg)]'
               f'({repo_uri}/actions/workflows/tests.yml)')
        if not settings['private']:
            yield (f'[![Coverage Status](https://coveralls.io/repos/github/{gh}/{name}/badge.svg?'
                   f'branch=master)](https://coveralls.io/github/{gh}/{name}?branch={branch})')
    yield _simple_icons_badge('Dependabot', 'dependabot', 'Dependabot-enabled', 'blue',
                              'https://github.com/dependabot')


def _docs_badges(settings: Settings,
                 *,
                 github_pages_build_type: str | None = None,
                 pages_workflow_file: str | None = None) -> Iterator[str]:
    if not settings['want_docs'] or settings['private']:
        return
    if settings['project_type'] == 'python':
        yield (f"[![Documentation Status](https://readthedocs.org/projects/"
               f"{settings['github_project_name']}"
               f"/badge/?version=latest)]({settings['documentation_uri']}/?badge=latest)")
    elif settings['using_github'] and github_pages_build_type is not None:
        gh = settings['github']['username']
        name = settings['github_project_name']
        pages_uri = f'https://{gh.lower()}.github.io/{name}/'
        if github_pages_build_type == 'legacy':
            yield (f'[![pages-build-deployment](https://github.com/{gh}/{name}/actions/workflows/'
                   f'pages/pages-build-deployment/badge.svg)]({pages_uri})')
        elif pages_workflow_file:
            repo_uri = settings['repository_uri']
            yield (f'[![GitHub Pages]({repo_uri}/actions/workflows/'
                   f'{pages_workflow_file}/badge.svg)]({pages_uri})')


def _python_tool_badges(settings: Settings) -> Iterator[str]:
    if settings['project_type'] != 'python':
        return
    if settings['using_django']:
        yield _simple_icons_badge('Django', 'django', 'Django', '092E20',
                                  'https://djangoproject.com')
    yield '[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)'
    if settings['package_manager'] == 'uv':
        yield _simple_icons_badge('uv', 'astral', 'uv', '261230', 'https://docs.astral.sh/uv/')
    else:
        yield _simple_icons_badge('Poetry', 'poetry', 'Poetry', '242d3e',
                                  'https://python-poetry.org')
    dep_names = set(settings['python_deps']['main'])
    name_mapping = {'jinja': 'Jinja', 'pydantic': 'Pydantic', 'sqlalchemy': 'SQLAlchemy'}
    if not settings['private']:
        yield from (_simple_icons_badge(name_mapping.get(package, package), package,
                                        name_mapping.get(package, package), 'black',
                                        f'https://pypi.org/project/{package}/')
                    for package in ('numpy', 'jinja', 'pandas', 'pydantic', 'scrapy', 'sqlalchemy')
                    if package in dep_names)
    if not settings['stubs_only'] and settings['want_tests']:
        yield (
            '[![pytest](https://img.shields.io/badge/pytest-zz?logo=Pytest&labelColor=black&color=black)]'
            '(https://docs.pytest.org/en/stable/)')
    yield ('[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com'
           '/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)')
    if not settings['private']:
        yield (f"[![Downloads](https://static.pepy.tech/badge/{settings['project_name']}/month)]"
               f"(https://pepy.tech/project/{settings['project_name']})")


def _typescript_badges(settings: Settings) -> list[str]:
    if settings['project_type'] != 'typescript':
        return []
    npm_badges: tuple[str, ...] = ()
    if not settings['private']:
        npm_badges = (*(_simple_icons_badge(dep, dep.replace('-', ''), dep, 'black',
                                            f'https://www.npmjs.com/package/{dep}')
                        for dep in ('bootstrap', 'react', 'sass', 'semantic-ui-react', 'sass',
                                    'tailwindcss')
                        if dep in settings['package_json'].get('dependencies', {})),
                      *(_simple_icons_badge(dev_dep, dev_dep.replace('-', ''), dev_dep, 'black',
                                            f'https://www.npmjs.com/package/{dev_dep}')
                        for dev_dep in ('eslint', 'vitest')
                        if dev_dep in settings['package_json']['devDependencies']))
    return sorted(
        (*npm_badges,
         _simple_icons_badge('TypeScript', 'typescript', 'TypeScript', 'black',
                             'https://www.typescriptlang.org/'),
         _simple_icons_badge('Yarn', 'yarn', 'Yarn', '4c335c', 'https://yarnpkg.com/'),
         *((_simple_icons_badge('Next.js', 'nextdotjs', 'Next.js', '000000', 'https://nextjs.org/'),
            ) if 'next' in settings['package_json'].get('dependencies', {}) else ())))


def _misc_badges(settings: Settings) -> Iterator[str]:
    if Path('Dockerfile').exists():
        yield _simple_icons_badge('Docker', 'docker', 'Docker', 'black', 'https://www.docker.com/')
    if settings['using_github'] and not settings['private']:
        gh = settings['github']['username']
        name = settings['github_project_name']
        yield (f'[![Stargazers](https://img.shields.io/github/stars/{gh}/{name}'
               f'?logo=github&style=flat)](https://github.com/{gh}/{name}/stargazers)')
    yield _simple_icons_badge('pre-commit', 'pre-commit', 'pre--commit-enabled', 'brightgreen',
                              'https://github.com/pre-commit/pre-commit')
    if (settings['project_type'] in {'c', 'c++'} and Path('CMakeLists.txt').exists()):
        yield _simple_icons_badge('CMake', 'cmake', 'CMake', '6E6E6E', 'https://cmake.org/')
    yield _simple_icons_badge('Prettier', 'prettier', 'Prettier', 'black', 'https://prettier.io/')


def _social_badges(settings: Settings) -> Iterator[str]:
    keywords_to_args: dict[str, tuple[str, str, str, str, str]] = {
        'dotnet': ('.NET', 'dotnet', '.NET', '512BD4', 'https://dotnet.microsoft.com/'),
        'ffmpeg': ('FFmpeg', 'ffmpeg', 'FFmpeg', 'orange', 'https://ffmpeg.org/'),
        'kde': ('KDE Plasma', 'kdeplasma', 'KDE%20Plasma', 'blue', 'https://kde.org/'),
        'qt': ('Qt', 'qt', 'Qt', '41cd52', 'https://www.qt.io/'),
        'swift': ('Swift', 'swift', 'Swift', 'F05138', 'https://swift.org/')
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
                               # cspell disable-next-line
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


def _custom_project_badges(settings: Settings, *, negative: bool = False) -> Iterator[str]:
    for b in sorted(settings.get('custom_project_badges', []), key=lambda b: b.get('priority', 0)):
        priority = b.get('priority', 0)
        if (negative and priority < 0) or (not negative and priority >= 0):
            yield f"{b['anchor']}({b['href']})"


def _readme_badge_delimiter_indices(lines: Sequence[str]) -> tuple[int, int] | None:
    start_i: int | None = None
    for i, raw in enumerate(lines):
        if raw.strip() == _README_GENERATED_START:
            start_i = i
            break
    if start_i is None:
        return None
    for j in range(start_i + 1, len(lines)):
        if lines[j].strip() == _README_GENERATED_STOP:
            return (start_i, j)
    log.debug('README.md has %s without a matching %s; using legacy badge detection.',
              _README_GENERATED_START, _README_GENERATED_STOP)
    return None


async def _replace_badge_section_legacy(readme: anyio.Path, lines: Sequence[str],
                                        expected: Sequence[str],
                                        social_expected: Sequence[str]) -> None:
    start_idx = next((i for i, line in enumerate(lines) if line.startswith('#')), 0) + 1
    while start_idx < len(lines) and not lines[start_idx].strip():
        start_idx += 1
    end_idx = start_idx
    while end_idx < len(lines) and (lines[end_idx].startswith('[![') or
                                    lines[end_idx].startswith('![') or not lines[end_idx].strip()):
        end_idx += 1
    new_text = '\n'.join((*lines[:start_idx], '', _README_GENERATED_START, '', *expected, '',
                          *social_expected, '', _README_GENERATED_STOP, '', *lines[end_idx:]))
    await readme.write_text(new_text, encoding='utf-8')


async def _replace_badge_section(readme: anyio.Path, lines: Sequence[str], expected: Sequence[str],
                                 social_expected: Sequence[str]) -> None:
    if (region := _readme_badge_delimiter_indices(lines)) is not None:
        start_i, stop_i = region
        prefix = lines[:start_i]
        suffix = lines[stop_i + 1:]
        new_text = '\n'.join((*prefix, _README_GENERATED_START, '', *expected, '', *social_expected,
                              '', _README_GENERATED_STOP, *suffix))
        await readme.write_text(new_text, encoding='utf-8')
        return
    await _replace_badge_section_legacy(readme, lines, expected, social_expected)


async def _check_readme_badges(settings: Settings, *, session: AsyncSession | None = None) -> None:
    log.debug('Checking README.md badges.')
    readme = anyio.Path('README.md')
    if not await readme.exists():
        log.debug('README.md is missing; skipping badge check.')
        return
    build_type: str | None = None
    pages_workflow_file: str | None = None
    has_qa_workflow = await anyio.Path('.github/workflows/qa.yml').exists()
    if (session is not None and settings['using_github'] and not settings['private']
            and settings['want_docs']):
        build_type = await get_github_pages_build_type(session, settings)
    if build_type == 'workflow':
        workflows_dir = anyio.Path('.github/workflows')
        if await workflows_dir.is_dir():
            async for wf in workflows_dir.glob('*.yml'):
                if _RE_DEPLOY_PAGES.search(await wf.read_text(encoding='utf-8')):
                    pages_workflow_file = wf.name
                    break
    await _replace_badge_section(
        readme, (await readme.read_text(encoding='utf-8')).split('\n'),
        (*_custom_project_badges(settings, negative=True), *_project_type_badges(settings),
         *_github_badges(settings, has_qa_workflow=has_qa_workflow), *_docs_badges(
             settings, github_pages_build_type=build_type, pages_workflow_file=pages_workflow_file),
         *_python_tool_badges(settings), *_misc_badges(settings), *_typescript_badges(settings),
         *_custom_project_badges(settings)), list(_social_badges(settings)))
    log.debug('Updated README.md badges.')


_RE_UV_LOCK_DIFF_EXCLUDE_NEWER_HUNK_LINE = re.compile(r'^[+-]\s*exclude-newer\s*=')


def uv_lock_diff_changes_only_exclude_newer(diff_text: str) -> bool:
    """
    Return whether unified diff hunks change only ``exclude-newer`` assignments.

    Parameters
    ----------
    diff_text : str
        Unified diff text, typically from comparing ``uv.lock`` revisions.

    Returns
    -------
    bool
        ``True`` when every ``+``/``-`` line affects only ``exclude-newer`` keys.
    """
    if not diff_text.strip():
        return False
    saw_exclude_newer_change = False
    for line in diff_text.splitlines():
        if line.startswith(('diff --git ', 'index ', '--- ', '+++ ', '@@', '\\')):
            continue
        if not line:
            continue
        marker = line[0]
        if marker == ' ':
            continue
        if marker in '+-':
            if not _RE_UV_LOCK_DIFF_EXCLUDE_NEWER_HUNK_LINE.match(line):
                return False
            saw_exclude_newer_change = True
            continue
        return False
    return saw_exclude_newer_change


async def maybe_revert_uv_lock_if_only_lockfile_changed(settings: Settings,
                                                        *,
                                                        on_command: Callable[[str], None]
                                                        | None = None) -> None:
    """
    Restore ``uv.lock`` from ``HEAD`` when the drift arises from incidental resolution.

    ``uv lock --upgrade`` can refresh the lock without any edits to ``pyproject.toml`` (for example
    when rolling ``exclude-newer`` cut-offs in the user ``uv.toml`` or when the index moves). If the
    working tree differs from ``HEAD`` only in ``uv.lock``, put the lock file back so a run does
    not leave an incidental lock diff. The same applies when other tracked paths also differ, if
    ``git diff --no-color -a HEAD -- uv.lock`` shows changes only on ``exclude-newer`` lines under
    ``[options]`` (compare to ``HEAD``, matching ``git restore --source=HEAD``). ``git restore`` and
    ``git checkout`` pass ``-c`` ``core.hooksPath`` set to the platform null device so hooks (for
    example pre-commit) cannot block reverting the lock.

    Parameters
    ----------
    settings : Settings
        Merged project settings.
    on_command : Callable[[str], None] | None
        Called with the command string before each subprocess runs.
    """
    if settings['package_manager'] != 'uv':
        return
    if not await anyio.Path('.git').exists():
        return
    proc, out, _ = await _subprocess_log_run(('git', 'diff', '--name-only', 'HEAD'),
                                             on_command=on_command,
                                             stdout=asyncio.subprocess.PIPE,
                                             stderr=asyncio.subprocess.DEVNULL,
                                             check=False)
    if proc.returncode != 0:
        log.debug('git diff --name-only HEAD failed; skipping uv.lock restore.')
        return
    diff_names = {
        p.strip().replace('\\', '/')
        for p in (out or b'').decode().splitlines() if p.strip()
    }
    if 'uv.lock' not in diff_names:
        return
    if diff_names == {'uv.lock'}:
        restore_uv_lock = True
    else:
        proc_uv, diff_uv, _ = await _subprocess_log_run(
            ('git', 'diff', '--no-color', '-a', 'HEAD', '--', 'uv.lock'),
            on_command=on_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            check=False)
        if proc_uv.returncode != 0:
            log.debug(
                'git diff --no-color -a HEAD -- uv.lock failed; skipping extended uv.lock restore.')
            return
        restore_uv_lock = uv_lock_diff_changes_only_exclude_newer((diff_uv or b'').decode())
    if not restore_uv_lock:
        return
    proc_restore, _, err = await _subprocess_log_run(
        ('git', *_GIT_CONFIG_NO_HOOKS, 'restore', '--source=HEAD', '--staged', '--worktree', '--',
         'uv.lock'),
        on_command=on_command,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        check=False)
    if proc_restore.returncode != 0:
        log.debug('git restore uv.lock failed (%s); trying git checkout.',
                  (err or b'').decode().strip())
        proc_co, _, err_co = await _subprocess_log_run(
            ('git', *_GIT_CONFIG_NO_HOOKS, 'checkout', 'HEAD', '--', 'uv.lock'),
            on_command=on_command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            check=False)
        if proc_co.returncode != 0:
            log.warning('Could not restore uv.lock from HEAD: %s', (err_co or b'').decode().strip())
            return
    log.debug('Restored uv.lock from HEAD.')


async def post_process_steps(settings: Settings,
                             *,
                             debug: bool = False,
                             on_command: Callable[[str], None] | None = None,
                             session: AsyncSession | None = None) -> None:
    """
    Run post-processing steps after project generation.

    Parameters
    ----------
    settings : Settings
        Project settings.
    debug : bool
        Whether debug mode is enabled. When ``False``, ``uv`` and Poetry are invoked with
        ``--quiet``.
    on_command : Callable[[str], None] | None
        Called with the command string before each subprocess runs.
    session : AsyncSession | None
        Optional HTTP session. When set, ``CHANGELOG.md`` boilerplate links for Keep a Changelog and
        Semantic Versioning are updated from ``olivierlacan/keep-a-changelog`` and ``semver/semver``
        respectively; otherwise pinned fallback URLs are used.
    """
    if settings['private']:
        await anyio.Path('.github/workflows/publish.yml').unlink(missing_ok=True)
    match settings['project_type']:
        case 'python':
            await _post_process_steps_python(settings, debug=debug, on_command=on_command)
        case _:
            qa_yml = anyio.Path('.github/workflows/qa.yml')
            if await qa_yml.exists() and 'jobs: {}' in (await qa_yml.read_text(encoding='utf-8')):
                await qa_yml.unlink(missing_ok=True)
            log.warning('No post-processing steps for project type `%s`.', settings['project_type'])
    await asyncio.gather(_check_readme_badges(settings, session=session),
                         _refresh_changelog_reference_urls(session))
    package_json = anyio.Path('package.json')
    await package_json.write_text(json.dumps(json.loads(await
                                                        package_json.read_text(encoding='utf-8')),
                                             indent=2,
                                             sort_keys=True),
                                  encoding='utf-8')
    if settings['regenerate_yarn_lock']:
        await anyio.Path('yarn.lock').unlink(missing_ok=True)
    yarn_env = os.environ | {'COREPACK_ENABLE_DOWNLOAD_PROMPT': '0'}
    await _subprocess_log_run(('yarn',),
                              env=yarn_env,
                              on_command=on_command,
                              stderr=asyncio.subprocess.PIPE,
                              stdout=asyncio.subprocess.PIPE)
    await asyncio.gather(
        _create_wiswa_ci_cache_dirs(settings), _remove_legacy_wiswa_ai_files(),
        _run_prettier_then_markdownlint_fix(debug=debug, on_command=on_command, env=yarn_env),
        _run_postprocess_language_formatters(settings,
                                             debug=debug,
                                             on_command=on_command,
                                             env=yarn_env),
        _subprocess_log_run(('yarn', 'dict:update'),
                            env=yarn_env,
                            on_command=on_command,
                            stderr=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            check=False),
        maybe_revert_uv_lock_if_only_lockfile_changed(settings, on_command=on_command))
