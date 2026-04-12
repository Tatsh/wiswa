"""Wiswa command-line interface."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn
import asyncio
import importlib.resources
import logging
import os
import re
import secrets
import sys

from bascom import setup_logging
from niquests_cache import cached_session
from yaspin import yaspin
from yaspin.spinners import Spinners
import anyio
import click
import niquests

from .utils import (
    FlatpakConfigurationError,
    apply_python_pyproject_manifest_edits,
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
    from collections.abc import Awaitable, Callable, Mapping

    from yaspin.core import Yaspin

    from .typing import Settings

__all__ = ('main',)

log = logging.getLogger(__name__)

# Each dots* spinner name is repeated this many times in the draw pool, so those names beat
# any other single spinner.
_DOT_FAMILY_WEIGHT = 4
_DOT_SPINNER_NAMES = ('dots', 'dots2', 'dots3', 'dots4', 'dots5', 'dots6', 'dots7', 'dots8',
                      'dots9', 'dots10', 'dots11', 'dots12', 'dots13', 'dots14')
_OTHER_SPINNER_NAMES = ('sand', 'pipe', 'star', 'star2', 'hamburger', 'growVertical',
                        'growHorizontal', 'earth', 'runner', 'soccerHeader', 'orangePulse',
                        'bluePulse', 'orangeBluePulse')
_SPINNER_CHOICE_POOL: tuple[str, ...] = (tuple(name for name in _DOT_SPINNER_NAMES
                                               for _ in range(_DOT_FAMILY_WEIGHT)) +
                                         _OTHER_SPINNER_NAMES)


def _random_cli_spinner() -> Any:  # pragma: no cover
    return getattr(Spinners, secrets.choice(_SPINNER_CHOICE_POOL))


def _has_legacy_poetry_deps(settings: Settings) -> bool:
    if settings.get('package_manager') != 'uv':
        return False
    poetry = settings.get('pyproject', {}).get('tool', {}).get('poetry', {})
    if poetry.get('dependencies'):
        return True
    return any(group.get('dependencies')
               for group in poetry.get('group', {}).values())  # type: ignore[attr-defined]


def _reraise_or_abort(exc: BaseException, *, debug: bool) -> NoReturn:
    """
    Re-raise *exc* when debugging, otherwise surface a chain-free ``click.Abort``.

    Parameters
    ----------
    exc : BaseException
        The failure to re-raise or fold into an abort.
    debug : bool
        When true, re-raise *exc* so a full traceback is shown.

    Raises
    ------
    click.Abort
        When *debug* is false, raised with ``from None`` to avoid chained context
        in stderr output.
    """
    if debug:
        raise exc
    raise click.Abort from None


def _handle_http_error(e: niquests.HTTPError) -> None:
    resp = e.response
    status = resp.status_code if resp is not None else 0
    if status in {HTTPStatus.FORBIDDEN, HTTPStatus.TOO_MANY_REQUESTS}:
        headers: Mapping[str, str] = resp.headers if resp is not None else {}
        retry_after = headers.get('Retry-After', '')
        rate_limit_remaining = headers.get('X-RateLimit-Remaining', '')
        msg = 'Rate limited by %s.' if rate_limit_remaining == '0' else 'HTTP %d from %s.'
        url = str(e.request.url) if e.request else 'unknown'
        host = re.sub(r'^https?://([^/]+).*', r'\1', url)
        if rate_limit_remaining == '0':
            click.echo(msg % host, err=True)
        else:
            click.echo(msg % (status, host), err=True)
        if retry_after:
            click.echo(f'Retry after {retry_after} seconds.', err=True)
        else:
            click.echo('Please wait a few minutes before trying again.', err=True)
    raise click.Abort


async def _postprocess_or_normalize_python_manifests(*, skip_postprocess: bool, loaded: Settings,
                                                     debug: bool,
                                                     session: niquests.AsyncSession | None,
                                                     spin_update: Callable[[str], None]) -> None:
    if not skip_postprocess:
        spin_update('Post-processing...')
        await post_process_steps(loaded,
                                 debug=debug,
                                 on_command=lambda cmd: spin_update(f'Running `{cmd}` ...'),
                                 session=session)
    elif loaded['project_type'] == 'python':
        spin_update('Normalizing Python manifests...')
        await apply_python_pyproject_manifest_edits(loaded)


async def _main_async(  # noqa: C901
        file: Path,
        jpath: tuple[str, ...] = (),
        *,
        cache_time: int = 600,
        debug: bool = False,
        no_cache: bool = False,
        output_dir: Path | None = None,
        quiet: bool = False,
        skip_github: bool = False,
        skip_jsonnet: bool = False,
        skip_postprocess: bool = False,
        skip_static: bool = False,
        skip_templates: bool = False,
        skip_yarn: bool = False) -> None:
    setup_logging(debug=debug,
                  loggers={
                      'niquests_cache': {},
                      'urllib3': {},
                      'urllib3.util.retry': {
                          'level': 'WARNING'
                      },
                      'wiswa': {}
                  })
    os.chdir(file.parent)
    spinner_enabled = (not debug and not quiet
                       and (sys.stderr.isatty() or os.environ.get('WISWA_PROGRESS') == '1'))
    progress_spinner: Yaspin | None = None

    def spin_update(message: str) -> None:  # pragma: no cover
        nonlocal progress_spinner
        if not spinner_enabled:
            return
        if progress_spinner is None:
            progress_spinner = yaspin(_random_cli_spinner(), text=message, stream=sys.stderr)
            progress_spinner.start()
            return
        progress_spinner.text = message

    async def spin_stop() -> None:  # pragma: no cover
        nonlocal progress_spinner
        if progress_spinner is None:
            return
        await asyncio.to_thread(progress_spinner.stop)
        progress_spinner = None

    spin_update('Evaluating settings...')
    try:
        async with cached_session(aio=True,
                                  no_cache=no_cache,
                                  app_name='wiswa',
                                  expire_after=timedelta(seconds=cache_time)) as session:
            with (importlib.resources.as_file(
                    importlib.resources.files('wiswa-jsonnet') / 'defaults.libsonnet') as
                  jsonnet_defaults_file,
                  importlib.resources.as_file(importlib.resources.files('wiswa')) as module_path):
                lib_path = Path(jsonnet_defaults_file).parent
                jpathdir = [str(lib_path)]
                merged_settings, loaded = await evaluate_merged_settings(
                    [*jpath, *jpathdir], lib_path, await
                    anyio.Path(file).read_text(encoding='utf-8'), session)
                if _has_legacy_poetry_deps(loaded):
                    log.warning(
                        'pyproject.tool.poetry.*.dependencies is deprecated. '
                        'Move dependencies to python_deps.main/dev/docs/tests in .wiswa.jsonnet.')
                # Skip only wiswa-jsonnet/project.jsonnet (manifest files). Merged settings from
                # evaluate_merged_settings always run Jsonnet first.
                if not skip_jsonnet:
                    spin_update('Evaluating project. Please be patient...')
                    await evaluate_jsonnet_project(lib_path,
                                                   jpathdir,
                                                   merged_settings,
                                                   session,
                                                   output_dir=output_dir)
                if not skip_templates:
                    spin_update('Writing templated files...')
                    await write_templated_files(module_path, loaded, session)
                if not skip_yarn:
                    spin_update('Downloading Yarn...')
                    await asyncio.gather(download_yarn(session, loaded['yarn_version']),
                                         download_yarn_plugins(session))
                if not skip_static:
                    spin_update('Copying static files...')
                    copy_tasks: list[Awaitable[None]] = [copy_static_files(loaded, module_path)]
                    if loaded['project_type'] == 'python' and not loaded['stubs_only']:
                        copy_tasks.append(create_py_typed_files(loaded))
                    await asyncio.gather(*copy_tasks)
                await _postprocess_or_normalize_python_manifests(skip_postprocess=skip_postprocess,
                                                                 loaded=loaded,
                                                                 debug=debug,
                                                                 session=session,
                                                                 spin_update=spin_update)
                if not skip_github:
                    spin_update('Configuring GitHub project settings...')
                    await setup_github_project(session, loaded)
    except niquests.HTTPError as e:
        await spin_stop()
        click.echo(click.style('Failed.', fg='red'), err=True)
        _handle_http_error(e)
    except click.Abort:
        raise
    except FlatpakConfigurationError as e:
        await spin_stop()
        click.echo(click.style('Failed.', fg='red'), err=True)
        click.echo(str(e), err=True)
        log.debug('FlatpakConfigurationError', exc_info=e)
        _reraise_or_abort(e, debug=debug)
    except RuntimeError as e:
        await spin_stop()
        click.echo(click.style('Failed.', fg='red'), err=True)
        msg = str(e)
        first_line = msg.split('\n', maxsplit=1)[0].removeprefix('RUNTIME ERROR: ')
        click.echo(first_line, err=True)
        if 'Could not get latest tag' in msg:
            click.echo(
                'This is often GitHub API rate limiting or a repository without semver tags or '
                'releases. Wait and retry, set GITHUB_TOKEN, or check the upstream repo publishes '
                'tags.',
                err=True)
        log.debug('RuntimeError', exc_info=e)
        _reraise_or_abort(e, debug=debug)
    except Exception as e:
        await spin_stop()
        click.echo(click.style('Failed.', fg='red'), err=True)
        log.debug('Unhandled exception', exc_info=e)
        _reraise_or_abort(e, debug=debug)
    else:
        await spin_stop()
        if not quiet:
            click.echo('Done.')
    finally:
        await spin_stop()


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.option('--cache-time',
              default=600,
              show_default=True,
              type=int,
              help='Cache expiration time in seconds.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option(
    '-J',
    '--jpath',
    multiple=True,
    help=('Add a directory to the Jsonnet search path (only used when evaluating settings).'))
@click.option('--no-cache', is_flag=True, help='Disable HTTP response caching.')
@click.option('-o',
              '--output-dir',
              default=None,
              type=click.Path(file_okay=False, path_type=Path),
              help='Output directory for generated files.')
@click.option('-q',
              '--quiet',
              is_flag=True,
              help='Suppress the progress spinner and the final Done message.')
@click.option('--skip-github', is_flag=True, help='Skip configuring GitHub project.')
@click.option(
    '--skip-jsonnet',
    is_flag=True,
    help=('Skip project.jsonnet output (for example pyproject.toml, package.json, and workflows). '
          'Merged settings from .wiswa.jsonnet still use Jsonnet.'))
@click.option('--skip-postprocess', is_flag=True, help='Skip post-processing steps.')
@click.option('--skip-static', is_flag=True, help='Skip copying static files.')
@click.option('--skip-templates', is_flag=True, help='Skip Jinja2 template evaluation.')
@click.option('--skip-yarn', is_flag=True, help='Skip Yarn download.')
@click.argument('file',
                default='.wiswa.jsonnet',
                type=click.Path(exists=True, dir_okay=False, path_type=Path, resolve_path=True))
def main(file: Path,
         jpath: tuple[str, ...] = (),
         *,
         cache_time: int = 600,
         debug: bool = False,
         no_cache: bool = False,
         output_dir: Path | None = None,
         quiet: bool = False,
         skip_github: bool = False,
         skip_jsonnet: bool = False,
         skip_postprocess: bool = False,
         skip_static: bool = False,
         skip_templates: bool = False,
         skip_yarn: bool = False) -> None:
    """Generate and maintain projects with Jsonnet."""  # noqa: DOC501

    async def _run() -> None:
        await _main_async(file,
                          jpath,
                          cache_time=cache_time,
                          debug=debug,
                          no_cache=no_cache,
                          output_dir=output_dir,
                          quiet=quiet,
                          skip_github=skip_github,
                          skip_jsonnet=skip_jsonnet,
                          skip_postprocess=skip_postprocess,
                          skip_static=skip_static,
                          skip_templates=skip_templates,
                          skip_yarn=skip_yarn)

    try:
        anyio.run(_run)
    except (click.Abort, KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        if debug:
            raise
        log.debug('Uncaught exception', exc_info=exc)
        click.echo(click.style('Failed.', fg='red'), err=True)
        detail = str(exc).strip() or type(exc).__name__
        click.echo(detail, err=True)
        raise click.Abort from None
