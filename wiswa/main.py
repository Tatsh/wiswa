"""Main script."""
from __future__ import annotations

from pathlib import Path
import importlib
import importlib.resources
import logging
import os

from bascom import setup_logging
import click

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

__all__ = ('main',)

log = logging.getLogger(__name__)


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-J',
              '--jpath',
              multiple=True,
              help=('Add a directory to the Jsonnet search path '
                    '(only used when evaluating settings).'))
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
         skip_templates: bool = False) -> None:
    """Entry point for the Wiswa CLI."""
    setup_logging(
        debug=debug,
        loggers={
            'urllib3': {
                'level': 'DEBUG' if debug else 'INFO',
                'handlers': ('console',),
                'propagate': False,
            },
            'wiswa': {
                'level': 'DEBUG' if debug else 'INFO',
                'handlers': ('console',),
                'propagate': False,
            }
        },
    )
    log.debug('GitHub enabled: %s', not skip_github)
    os.chdir(file.parent)
    with (importlib.resources.as_file(importlib.resources.files('wiswa-jsonnet')) as
          lib_path, importlib.resources.as_file(importlib.resources.files('wiswa')) as module_path):
        jpathdir = [str(lib_path)]
        merged_settings, loaded = evaluate_merged_settings([*jpath, *jpathdir], lib_path,
                                                           file.read_text(encoding='utf-8'))
        if not skip_jsonnet:
            evaluate_jsonnet_project(lib_path, jpathdir, merged_settings)
        if not skip_templates:
            write_templated_files(module_path, loaded)
        download_yarn(loaded['yarn_version'])
        download_yarn_plugins()
        copy_static_files(loaded, module_path)
        if loaded['project_type'] == 'python' and not loaded['stubs_only']:
            create_py_typed_files(loaded)
        post_process_steps(loaded)
        if not skip_github:
            setup_github_project(loaded)


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-J',
              '--jpath',
              multiple=True,
              help=('Add a directory to the Jsonnet search path '
                    '(only used when evaluating settings).'))
def gen_docs_main(jpath: tuple[str, ...] = (), *, debug: bool = False) -> None:  # pragma: no cover
    """Generate Jsonnet documentation."""
    setup_logging(
        debug=debug,
        loggers={
            'urllib3': {
                'level': 'DEBUG' if debug else 'INFO',
                'handlers': ('console',),
                'propagate': False,
            },
            'wiswa': {
                'level': 'DEBUG' if debug else 'INFO',
                'handlers': ('console',),
                'propagate': False,
            }
        },
    )
    with (importlib.resources.as_file(importlib.resources.files('wiswa-jsonnet')) as
          lib_path, importlib.resources.as_file(importlib.resources.files('wiswa'))):
        jpathdir = ['/usr/share/jsonnet', *jpath, str(lib_path)]
        merged_settings, _ = evaluate_merged_settings(jpathdir, lib_path, '{}')
        evaluate_jsonnet_project(lib_path, jpathdir, merged_settings, lib_path / 'docs.jsonnet',
                                 Path('docs'))
