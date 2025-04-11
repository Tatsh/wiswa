"""Main script."""
from __future__ import annotations

from pathlib import Path
import importlib
import importlib.resources
import logging
import os

import click

from .utils import (
    copy_static_files,
    create_py_typed_files,
    download_yarn,
    download_yarn_plugins,
    evaluate_jsonnet_project,
    evaluate_merged_settings,
    post_process_steps,
    write_templated_files,
)

__all__ = ('main',)


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.option('-J',
              '--jpath',
              multiple=True,
              help=('Add a directory to the Jsonnet search path '
                    '(only used when evaluating settings).'))
@click.option('--skip-jsonnet', is_flag=True, help='Skip Jsonnet evaluation.')
@click.option('--skip-templates', is_flag=True, help='Skip Jinja2 template evaluation.')
@click.argument('file',
                default='.wiswa.jsonnet',
                type=click.Path(exists=True, dir_okay=False, path_type=Path, resolve_path=True))
def main(file: Path,
         jpath: tuple[str, ...] = (),
         *,
         debug: bool = False,
         skip_jsonnet: bool = False,
         skip_templates: bool = False) -> None:
    """Entry point for the Wiswa CLI."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.WARNING,
                        format='%(levelname)s:%(module)s:%(lineno)d:%(funcName)s: %(message)s')
    os.chdir(file.parent)
    with (importlib.resources.as_file(importlib.resources.files('wiswa-jsonnet')) as
          lib_path, importlib.resources.as_file(importlib.resources.files('wiswa')) as module_path):
        jpathdir = [str(lib_path)]
        merged_settings, loaded = evaluate_merged_settings([*jpath, *jpathdir], lib_path, file)
        if not skip_jsonnet:
            evaluate_jsonnet_project(lib_path, jpathdir, merged_settings)
        if not skip_templates:
            write_templated_files(module_path, loaded)
        download_yarn(loaded['yarn_version'])
        download_yarn_plugins()
        copy_static_files(loaded, module_path)
        create_py_typed_files(loaded)
        post_process_steps()
