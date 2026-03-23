"""Main script."""
from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
import asyncio
import contextlib
import importlib.resources
import logging
import os
import re
import sys

from bascom import setup_logging
import aiohttp
import anyio
import click

from .session import cached_session
from .utils import (
    copy_static_files,
    create_py_typed_files,
    download_yarn,
    download_yarn_plugins,
    evaluate_jsonnet_project,
    evaluate_merged_settings,
    post_process_steps,
    setup_github_project,
    write_templated_files,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .typing import Settings

__all__ = ('main',)

log = logging.getLogger(__name__)
_DEP_NAME_RE = re.compile(r'^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)')


class _Spinner:
    """Animated progress indicator for non-debug mode."""

    _FRAMES = ('=   ', '==  ', '=== ', '====', ' ===', '  ==', '   =', '    ')

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled and (sys.stderr.isatty() or os.environ.get('WISWA_PROGRESS') == '1')
        self._message = ''
        self._task: asyncio.Task[None] | None = None

    async def _animate(self) -> None:
        i = 0
        while True:
            frame = self._FRAMES[i % len(self._FRAMES)]
            sys.stderr.write(f'\r\033[2K[{frame}] {self._message}')
            sys.stderr.flush()
            i += 1
            await asyncio.sleep(0.12)

    def update(self, message: str) -> None:
        """Update the status message."""
        self._message = message
        if not self._enabled:
            return
        if self._task is None:
            self._task = asyncio.get_event_loop().create_task(self._animate())

    async def stop(self) -> None:
        """Stop the spinner and clear the line."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._enabled:
            sys.stderr.write('\r\033[2K')
            sys.stderr.flush()


def _has_legacy_poetry_deps(settings: Settings) -> bool:
    if settings.get('package_manager') != 'uv':
        return False
    python_deps = cast('dict[str, Any]', settings.get('python_deps', {}))
    pyproject = settings.get('pyproject', {})
    project = pyproject.get('project', {})
    dep_groups = cast('dict[str, Any]', pyproject.get('dependency-groups', {}))
    for group_name, resolved_deps in (
        ('main', list(project.get('dependencies', ()))),
            *((name, list(dep_groups.get(name, ()))) for name in ('dev', 'docs', 'tests')),
    ):
        canonical = set(python_deps.get(group_name, {}))
        if not canonical:
            continue
        for dep in resolved_deps:
            m = _DEP_NAME_RE.match(dep)
            if m and m.group(1) not in canonical:
                return True
    return False


def _handle_http_error(e: aiohttp.ClientResponseError) -> None:
    if e.status in {HTTPStatus.FORBIDDEN, HTTPStatus.TOO_MANY_REQUESTS}:
        headers: Mapping[str, str] = e.headers or {}
        retry_after = headers.get('Retry-After', '')
        rate_limit_remaining = headers.get('X-RateLimit-Remaining', '')
        msg = 'Rate limited by %s.' if rate_limit_remaining == '0' else 'HTTP %d from %s.'
        url = str(e.request_info.url) if e.request_info else 'unknown'
        host = re.sub(r'^https?://([^/]+).*', r'\1', url)
        if rate_limit_remaining == '0':
            click.echo(msg % host, err=True)
        else:
            click.echo(msg % (e.status, host), err=True)
        if retry_after:
            click.echo(f'Retry after {retry_after} seconds.', err=True)
        else:
            click.echo('Please wait a few minutes before trying again.', err=True)
    raise click.Abort


async def _main_async(file: Path,
                      jpath: tuple[str, ...] = (),
                      *,
                      debug: bool = False,
                      skip_github: bool = False,
                      skip_jsonnet: bool = False,
                      skip_templates: bool = False,
                      user_defaults: bool = False) -> None:
    setup_logging(
        debug=debug,
        loggers={'wiswa': {}},
    )
    logging.getLogger('aiohttp_client_cache').setLevel(logging.WARNING)
    logging.getLogger('aiosqlite').setLevel(logging.WARNING)
    os.chdir(file.parent)
    spin = _Spinner(enabled=not debug)
    try:
        async with cached_session() as session:
            with (importlib.resources.as_file(importlib.resources.files('wiswa-jsonnet')) as
                  lib_path, importlib.resources.as_file(importlib.resources.files('wiswa')) as
                  module_path):
                jpathdir = [str(lib_path)]
                merged_settings, loaded = await evaluate_merged_settings(
                    [*jpath, *jpathdir],
                    lib_path,
                    await anyio.Path(file).read_text(encoding='utf-8'),
                    session,
                    user_defaults=user_defaults)
                if _has_legacy_poetry_deps(loaded):
                    log.warning(
                        'pyproject.tool.poetry.*.dependencies is deprecated. '
                        'Move dependencies to python_deps.main/dev/docs/tests in .wiswa.jsonnet.')
                if not skip_jsonnet:
                    spin.update('Generating project files (please be patient).')
                    await evaluate_jsonnet_project(lib_path, jpathdir, merged_settings, session)
                if not skip_templates:
                    spin.update('Writing templated files.')
                    await write_templated_files(module_path, loaded, session)
                spin.update('Downloading Yarn.')
                await download_yarn(session, loaded['yarn_version'])
                await download_yarn_plugins(session)
                spin.update('Copying static files.')
                await copy_static_files(loaded, module_path)
                if loaded['project_type'] == 'python' and not loaded['stubs_only']:
                    await create_py_typed_files(loaded)
                spin.update('Post-processing.')
                await post_process_steps(loaded,
                                         on_command=lambda cmd: spin.update(f'Running {cmd}'))
                if not skip_github:
                    spin.update('Configuring GitHub project settings')
                    await setup_github_project(session, loaded)
    except aiohttp.ClientResponseError as e:
        await spin.stop()
        click.echo(click.style('Failed.', fg='red'), err=True)
        _handle_http_error(e)
    except RuntimeError as e:
        await spin.stop()
        click.echo(click.style('Failed.', fg='red'), err=True)
        msg = str(e)
        first_line = msg.split('\n', maxsplit=1)[0].removeprefix('RUNTIME ERROR: ')
        click.echo(first_line, err=True)
        if 'Could not get latest tag' in msg:
            click.echo(
                'This is usually caused by GitHub API rate limiting. '
                'Wait a few minutes and try again.',
                err=True)
        log.debug('RuntimeError', exc_info=e)
        raise click.Abort from e
    except Exception as e:
        await spin.stop()
        click.echo(click.style('Failed.', fg='red'), err=True)
        log.debug('Unhandled exception', exc_info=e)
        raise click.Abort from e
    else:
        await spin.stop()
        click.echo('Done.')
    finally:
        await spin.stop()


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-J',
              '--jpath',
              multiple=True,
              help=('Add a directory to the Jsonnet search path '
                    '(only used when evaluating settings).'))
@click.option('-u',
              '--user-defaults',
              is_flag=True,
              help='Use defaults.jsonnet file in user preferences directory.')
@click.option('--skip-github', is_flag=True, help='Skip configuring GitHub project.')
@click.option('--skip-jsonnet', is_flag=True, help='Skip Jsonnet evaluation.')
@click.option('--skip-templates', is_flag=True, help='Skip Jinja2 template evaluation.')
@click.argument('file',
                default='.wiswa.jsonnet',
                type=click.Path(exists=True, dir_okay=False, path_type=Path, resolve_path=True))
def main(file: Path,
         jpath: tuple[str, ...] = (),
         *,
         debug: bool = False,
         skip_github: bool = False,
         skip_jsonnet: bool = False,
         skip_templates: bool = False,
         user_defaults: bool = False) -> None:
    """Entry point for the Wiswa CLI."""
    async def _run() -> None:
        await _main_async(file,
                          jpath,
                          debug=debug,
                          skip_github=skip_github,
                          skip_jsonnet=skip_jsonnet,
                          skip_templates=skip_templates,
                          user_defaults=user_defaults)

    anyio.run(_run)
