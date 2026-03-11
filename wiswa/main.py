"""Main script."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
import importlib.resources
import logging
import os
import re

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

if TYPE_CHECKING:
    from .typing import Settings

__all__ = ('main',)

log = logging.getLogger(__name__)
_DEP_NAME_RE = re.compile(r'^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)')


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
    setup_logging(
        debug=debug,
        loggers={
            'urllib3': {},
            'wiswa': {}
        },
    )
    log.debug('GitHub enabled: %s', not skip_github)
    os.chdir(file.parent)
    with (importlib.resources.as_file(importlib.resources.files('wiswa-jsonnet')) as
          lib_path, importlib.resources.as_file(importlib.resources.files('wiswa')) as module_path):
        jpathdir = [str(lib_path)]
        merged_settings, loaded = evaluate_merged_settings([*jpath, *jpathdir],
                                                           lib_path,
                                                           file.read_text(encoding='utf-8'),
                                                           user_defaults=user_defaults)
        if _has_legacy_poetry_deps(loaded):
            log.warning('pyproject.tool.poetry.*.dependencies is deprecated. '
                        'Move dependencies to python_deps.main/dev/docs/tests in .wiswa.jsonnet.')
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
