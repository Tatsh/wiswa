"""Jinja2 templating and writing generated files."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple
import logging

from wiswa.extensions import (
    GithubAPIExtension,
    ParseMarkdownBadgeExtension,
    ShellExtension,
    ToPythonExtension,
)
import anyio
import jinja2

from .path import non_empty_file_exists, primary_module_to_path

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiohttp import ClientSession
    from wiswa.typing import Settings

log = logging.getLogger(__name__)

__all__ = ('write_templated_files',)


class _TemplateEnvTuple(NamedTuple):
    env: jinja2.Environment
    templates_dir: Path
    resolve_template: Callable[[Path], jinja2.Template]
    write_file: Callable[..., Awaitable[None]]


def _template_env(module_path: Path,
                  settings: Settings,
                  session: ClientSession | None = None) -> _TemplateEnvTuple:
    env = jinja2.Environment(autoescape=jinja2.select_autoescape(),
                             enable_async=True,
                             extensions=(GithubAPIExtension, ParseMarkdownBadgeExtension,
                                         ShellExtension, ToPythonExtension),
                             loader=jinja2.PackageLoader('wiswa'),
                             lstrip_blocks=True,
                             trim_blocks=True,
                             undefined=jinja2.StrictUndefined)
    if session is not None:
        env.globals['_aiohttp_session'] = session
    templates_dir = module_path / 'templates'

    def resolve_template(file_path: Path) -> jinja2.Template:
        return env.get_template(str(file_path.relative_to(templates_dir)))

    async def write_file(template: jinja2.Template,
                         output_file: Path | str,
                         *,
                         overwrite: bool = False) -> None:
        output_file = Path(output_file)
        if not overwrite and await non_empty_file_exists(output_file):
            log.debug('Skipping template `%s`.', output_file)
            return
        aio_output = anyio.Path(output_file)
        await aio_output.parent.mkdir(parents=True, exist_ok=True)
        content = await template.render_async({'settings': settings})
        await aio_output.write_text(f'{content.strip()}\n')
        log.debug('Wrote `%s`.', output_file)

    return _TemplateEnvTuple(env, templates_dir, resolve_template, write_file)


async def _write_templated_files_c_cpp(templates_dir: Path,
                                       resolve_template: Callable[[Path], jinja2.Template],
                                       write_file: Callable[..., Awaitable[None]]) -> None:
    await write_file(resolve_template(templates_dir / 'CMakeLists.txt.j2'), 'CMakeLists.txt')
    await write_file(resolve_template(templates_dir / 'src/CMakeLists.txt.j2'),
                     'src/CMakeLists.txt')


async def _write_templated_files_cpp(settings: Settings, templates_dir: Path,
                                     resolve_template: Callable[[Path], jinja2.Template],
                                     write_file: Callable[..., Awaitable[None]]) -> None:
    if settings['want_main'] and not settings['has_multiple_entry_points']:
        await write_file(resolve_template(templates_dir / 'src/main.cpp.j2'), 'src/main.cpp')


async def _write_templated_files_c(settings: Settings, templates_dir: Path,
                                   resolve_template: Callable[[Path], jinja2.Template],
                                   write_file: Callable[..., Awaitable[None]]) -> None:
    if settings['want_main'] and not settings['has_multiple_entry_points']:
        await write_file(resolve_template(templates_dir / 'src/main.c.j2'), 'src/main.c')


async def _write_template_files_lua(templates_dir: Path,
                                    resolve_template: Callable[[Path], jinja2.Template],
                                    write_file: Callable[..., Awaitable[None]]) -> None:
    await write_file(resolve_template(templates_dir / '.busted.j2'), '.busted')
    await write_file(resolve_template(templates_dir / '.luacov.j2'), '.luacov')


async def _write_templated_files_python(settings: Settings, templates_dir: Path,
                                        resolve_template: Callable[[Path], jinja2.Template],
                                        write_file: Callable[..., Awaitable[None]]) -> None:
    if not settings['stubs_only']:
        await write_file(resolve_template(templates_dir / '_module_/__init__.py.j2'),
                         f'{primary_module_to_path(settings["primary_module"])}/__init__.py')
    if settings['want_tests']:
        await write_file(resolve_template(templates_dir / 'tests/conftest.py.j2'),
                         'tests/conftest.py')
        if settings['want_main'] and not settings['has_multiple_entry_points']:
            await write_file(resolve_template(templates_dir / 'tests/test_main.py.j2'),
                             'tests/test_main.py')
    if settings['want_docs']:
        for file_path in (templates_dir / 'docs/conf.py.j2', templates_dir / 'docs/index.rst.j2',
                          templates_dir / 'docs/badges.rst.j2'):
            await write_file(resolve_template(file_path),
                             file_path.relative_to(templates_dir).with_suffix(''))
    if ((settings['want_main'] or settings['has_multiple_entry_points'])
            and settings['using_github']):
        if (settings['supported_platforms'] == 'all' or 'windows' in settings['supported_platforms']
                or 'macos' in settings['supported_platforms']):
            await write_file(resolve_template(
                templates_dir / '.github/workflows/pyinstaller.yml.j2'),
                             '.github/workflows/pyinstaller.yml',
                             overwrite=True)
        if settings['supported_platforms'] == 'all' or 'linux' in settings['supported_platforms']:
            await write_file(resolve_template(templates_dir / '.github/workflows/appimage.yml.j2'),
                             '.github/workflows/appimage.yml',
                             overwrite=True)


async def _write_templated_files_typescript(settings: Settings, templates_dir: Path,
                                            resolve_template: Callable[[Path], jinja2.Template],
                                            write_file: Callable[..., Awaitable[None]]) -> None:
    if not settings['stubs_only']:
        await write_file(resolve_template(templates_dir / 'src/index.ts.j2'), 'src/index.ts')
    if settings['want_tests'] and not settings['stubs_only']:
        await write_file(resolve_template(templates_dir / 'jest.config.ts.j2'), 'jest.config.ts')
    await write_file(resolve_template(templates_dir / 'eslint.config.mjs.j2'),
                     'eslint.config.mjs',
                     overwrite=True)


_PYTHON_ONLY_AGENTS = frozenset({
    'click-auditor',
    'coverage-improver',
    'docstring-fixer',
    'mypy-fixer',
    'python-expert',
    'python-moderniser',
    'test-writer',
})


async def _write_templated_files_claude(settings: Settings, templates_dir: Path,
                                        resolve_template: Callable[[Path], jinja2.Template],
                                        write_file: Callable[..., Awaitable[None]]) -> None:
    agents_dir = templates_dir / '.claude/agents'
    if agents_dir.is_dir():
        for file_path in sorted(agents_dir.iterdir()):
            if file_path.suffix != '.j2':
                continue
            agent_name = file_path.stem.removesuffix('.md')
            output = Path('.claude/agents') / file_path.stem
            if (agent_name in _PYTHON_ONLY_AGENTS and settings['project_type'] != 'python'):
                output.unlink(missing_ok=True)
                continue
            await write_file(resolve_template(file_path), output, overwrite=True)
    skills_dir = templates_dir / '.claude/skills'
    if skills_dir.is_dir():
        for skill_subdir in sorted(skills_dir.iterdir()):
            if skill_subdir.is_dir():
                for file_path in sorted(skill_subdir.iterdir()):
                    if file_path.suffix == '.j2':
                        output = Path('.claude/skills') / skill_subdir.name / file_path.stem
                        await write_file(resolve_template(file_path), output, overwrite=True)
    await write_file(resolve_template(templates_dir / 'CLAUDE.md.j2'), 'CLAUDE.md', overwrite=True)
    await write_file(resolve_template(templates_dir / 'AGENTS.md.j2'), 'AGENTS.md', overwrite=True)


async def _should_overwrite_contributing(settings: Settings) -> bool:
    contributing = anyio.Path('CONTRIBUTING.md')
    if not await contributing.exists():
        return False
    content = await contributing.read_text(encoding='utf-8')
    if settings['package_manager'] == 'uv' and 'poetry' in content.lower():
        return True
    return bool(settings['package_manager'] == 'poetry' and 'uv sync' in content)


async def write_templated_files(module_path: Path,
                                settings: Settings,
                                session: ClientSession | None = None) -> None:
    """
    Write templated files.

    Parameters
    ----------
    module_path : Path
        Path to the :py:mod:`wiswa` package directory.
    settings : Settings
        Project settings.
    session : ClientSession | None
        Optional aiohttp session for HTTP callbacks in templates.
    """
    _, templates_dir, resolve_template, write_file = _template_env(module_path, settings, session)
    await anyio.Path('.github/copilot-instructions.md').unlink(missing_ok=True)
    general_instructions = anyio.Path('.github/instructions/general.instructions.md')
    general_instructions_template = (templates_dir /
                                     '.github/instructions/general.instructions.md.j2')
    if settings['want_copilot']:
        await write_file(resolve_template(general_instructions_template),
                         Path(general_instructions),
                         overwrite=True)
    else:
        template = resolve_template(general_instructions_template)
        expected = f'{(await template.render_async({"settings": settings})).strip()}\n'
        if (await general_instructions.exists()
                and await general_instructions.read_text(encoding='utf-8') == expected):
            await general_instructions.unlink()
            log.debug('Removed `%s` (matched would-be content).', general_instructions)
    if settings.get('want_claude_agents', False):
        await _write_templated_files_claude(settings, templates_dir, resolve_template, write_file)
    contributing_overwrite = await _should_overwrite_contributing(settings)
    common_templates = (('CODEOWNERS.j2', True), ('CONTRIBUTING.md.j2', contributing_overwrite),
                        ('LICENSE.txt.j2', not settings['private']), ('SECURITY.md.j2', True),
                        ('CHANGELOG.md.j2', False), ('README.md.j2', False))
    for template_name, overwrite in common_templates:
        template_path = templates_dir / template_name
        output_path = Path(template_name).with_suffix('')
        await write_file(resolve_template(template_path), output_path, overwrite=overwrite)
    match settings['project_type']:
        case 'python':
            await _write_templated_files_python(settings, templates_dir, resolve_template,
                                                write_file)
        case 'c++':
            await _write_templated_files_c_cpp(templates_dir, resolve_template, write_file)
            await _write_templated_files_cpp(settings, templates_dir, resolve_template, write_file)
        case 'c':
            await _write_templated_files_c_cpp(templates_dir, resolve_template, write_file)
            await _write_templated_files_c(settings, templates_dir, resolve_template, write_file)
        case 'lua':
            await _write_template_files_lua(templates_dir, resolve_template, write_file)
        case 'typescript':
            await _write_templated_files_typescript(settings, templates_dir, resolve_template,
                                                    write_file)
        case _:
            log.warning('No templated files to write for project type `%s`.',
                        settings['project_type'])
