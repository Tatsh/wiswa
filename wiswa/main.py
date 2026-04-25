"""Wiswa command-line interface."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn
import asyncio
import importlib.resources
import logging
import os
import re
import sys

from bascom import setup_logging
from niquests_cache import cached_session
import anyio
import click
import niquests

from .progress import ProgressDisplay, TaskId
from .utils import (
    FlatpakConfigurationError,
    RemoteHostConflictError,
    apply_python_pyproject_manifest_edits,
    copy_static_files,
    create_py_typed_files,
    download_yarn,
    download_yarn_plugins,
    evaluate_jsonnet_project,
    evaluate_merged_settings,
    post_process_steps,
    setup_github_project,
    setup_gitlab_project,
    write_templated_files,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Mapping

    from .typing import Settings

__all__ = ('main',)

log = logging.getLogger(__name__)


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
                                                     progress: ProgressDisplay) -> bool:
    """
    Run post-processing steps or fall back to Python manifest normalisation.

    Parameters
    ----------
    skip_postprocess : bool
        Whether ``--skip-postprocess`` was requested.
    loaded : Settings
        The loaded project settings.
    debug : bool
        Whether debug output is enabled.
    session : niquests.AsyncSession | None
        Optional shared HTTP session.
    progress : ProgressDisplay
        Progress display used to surface the currently running subcommand.

    Returns
    -------
    bool
        ``True`` when any work was performed, ``False`` when the step was fully skipped.
    """
    if not skip_postprocess:
        progress.start_task(TaskId.POST_PROCESS, 'Post-processing...')
        await post_process_steps(
            loaded,
            debug=debug,
            on_command=lambda cmd: progress.update_message(f'Running `{cmd}` ...'),
            session=session)
        return True
    if loaded['project_type'] == 'python':
        progress.start_task(TaskId.POST_PROCESS, 'Normalizing Python manifests...')
        await apply_python_pyproject_manifest_edits(loaded)
        return True
    return False


async def _run_copy_static(progress: ProgressDisplay, *, loaded: Settings, module_path: Path,
                           skip_static: bool) -> None:
    if skip_static:
        progress.skip(TaskId.COPY_STATIC)
        return
    progress.start_task(TaskId.COPY_STATIC, 'Copying static files...')
    copy_tasks: list[Awaitable[None]] = [copy_static_files(loaded, module_path)]
    if loaded['project_type'] == 'python' and not loaded['stubs_only']:
        copy_tasks.append(create_py_typed_files(loaded))
    await asyncio.gather(*copy_tasks)
    progress.complete(TaskId.COPY_STATIC)


async def _run_configure_remote(progress: ProgressDisplay, *, loaded: Settings,
                                session: niquests.AsyncSession, skip_remote: bool) -> None:
    if skip_remote:
        progress.skip(TaskId.CONFIGURE_REMOTE)
        return
    if loaded['using_github']:
        progress.start_task(TaskId.CONFIGURE_REMOTE, 'Configuring GitHub project settings...')
        await setup_github_project(session, loaded)
        progress.complete(TaskId.CONFIGURE_REMOTE)
        return
    if loaded['using_gitlab']:
        progress.start_task(TaskId.CONFIGURE_REMOTE, 'Configuring GitLab project settings...')
        await setup_gitlab_project(session, loaded)
        progress.complete(TaskId.CONFIGURE_REMOTE)
        return
    progress.skip(TaskId.CONFIGURE_REMOTE)


async def _run_workflow(progress: ProgressDisplay, *, debug: bool, file: Path,
                        jpath: tuple[str, ...], jpathdir: list[str], lib_path: Path,
                        module_path: Path, output_dir: Path | None, session: niquests.AsyncSession,
                        skip_jsonnet: bool, skip_postprocess: bool, skip_remote: bool,
                        skip_static: bool, skip_templates: bool, skip_yarn: bool) -> None:
    progress.start_task(TaskId.EVALUATE_SETTINGS, 'Evaluating settings...')
    merged_settings, loaded = await evaluate_merged_settings(
        [*jpath, *jpathdir], lib_path, await anyio.Path(file).read_text(encoding='utf-8'), session)
    progress.complete(TaskId.EVALUATE_SETTINGS)
    if _has_legacy_poetry_deps(loaded):
        log.warning('pyproject.tool.poetry.*.dependencies is deprecated. '
                    'Move dependencies to python_deps.main/dev/docs/tests in .wiswa.jsonnet.')
    # Skip only wiswa-jsonnet/project.jsonnet (manifest files). Merged settings from
    # evaluate_merged_settings always run Jsonnet first.
    if not skip_jsonnet:
        progress.start_task(TaskId.EVALUATE_PROJECT, 'Evaluating project. Please be patient...')
        await evaluate_jsonnet_project(lib_path,
                                       jpathdir,
                                       merged_settings,
                                       session,
                                       output_dir=output_dir)
        progress.complete(TaskId.EVALUATE_PROJECT)
    else:
        progress.skip(TaskId.EVALUATE_PROJECT)
    if not skip_templates:
        progress.start_task(TaskId.WRITE_TEMPLATES, 'Writing templated files...')
        await write_templated_files(module_path, loaded, session)
        progress.complete(TaskId.WRITE_TEMPLATES)
    else:
        progress.skip(TaskId.WRITE_TEMPLATES)
    if not skip_yarn:
        progress.start_task(TaskId.DOWNLOAD_YARN, 'Downloading Yarn...')
        await asyncio.gather(download_yarn(session, loaded['yarn_version']),
                             download_yarn_plugins(session))
        progress.complete(TaskId.DOWNLOAD_YARN)
    else:
        progress.skip(TaskId.DOWNLOAD_YARN)
    await _run_copy_static(progress,
                           loaded=loaded,
                           module_path=module_path,
                           skip_static=skip_static)
    if await _postprocess_or_normalize_python_manifests(skip_postprocess=skip_postprocess,
                                                        loaded=loaded,
                                                        debug=debug,
                                                        session=session,
                                                        progress=progress):
        progress.complete(TaskId.POST_PROCESS)
    else:
        progress.skip(TaskId.POST_PROCESS)
    await _run_configure_remote(progress, loaded=loaded, session=session, skip_remote=skip_remote)


async def _main_async(file: Path,
                      jpath: tuple[str, ...] = (),
                      *,
                      cache_time: int = 600,
                      debug: bool = False,
                      no_cache: bool = False,
                      output_dir: Path | None = None,
                      quiet: bool = False,
                      skip_remote: bool = False,
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
    progress_enabled = (not debug and not quiet
                        and (sys.stderr.isatty() or os.environ.get('WISWA_PROGRESS') == '1'))
    progress = ProgressDisplay(enabled=progress_enabled)
    progress.start()
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
                await _run_workflow(progress,
                                    debug=debug,
                                    file=file,
                                    jpath=jpath,
                                    jpathdir=jpathdir,
                                    lib_path=lib_path,
                                    module_path=module_path,
                                    output_dir=output_dir,
                                    session=session,
                                    skip_jsonnet=skip_jsonnet,
                                    skip_postprocess=skip_postprocess,
                                    skip_remote=skip_remote,
                                    skip_static=skip_static,
                                    skip_templates=skip_templates,
                                    skip_yarn=skip_yarn)
    except niquests.HTTPError as e:
        progress.stop()
        click.echo(click.style('Failed.', fg='red'), err=True)
        _handle_http_error(e)
    except click.Abort:
        raise
    except FlatpakConfigurationError as e:
        progress.stop()
        click.echo(click.style('Failed.', fg='red'), err=True)
        click.echo(str(e), err=True)
        log.debug('FlatpakConfigurationError', exc_info=e)
        _reraise_or_abort(e, debug=debug)
    except RemoteHostConflictError as e:
        progress.stop()
        click.echo(click.style('Failed.', fg='red'), err=True)
        click.echo(str(e), err=True)
        log.debug('RemoteHostConflictError', exc_info=e)
        _reraise_or_abort(e, debug=debug)
    except RuntimeError as e:
        progress.stop()
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
        progress.stop()
        click.echo(click.style('Failed.', fg='red'), err=True)
        log.debug('Unhandled exception', exc_info=e)
        _reraise_or_abort(e, debug=debug)
    else:
        progress.stop()
        if not quiet:
            click.echo('Done.')
    finally:
        progress.stop()


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
@click.option('--skip-remote',
              is_flag=True,
              help='Skip configuring the remote Git host (GitHub or GitLab project API).')
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
         skip_remote: bool = False,
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
                          skip_remote=skip_remote,
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
