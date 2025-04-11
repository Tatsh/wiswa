"""Utilities."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from shlex import quote
from shutil import copyfile
from typing import Any, cast
import json
import logging
import subprocess as sp

import _jsonnet  # type: ignore[import-not-found] # noqa: PLC2701
import jinja2
import requests

from .constants import PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI, STATIC_MODULE_FILES
from .extensions import ToPythonExtension

__all__ = ('copy_static_files', 'create_py_typed_files', 'download_yarn_plugins',
           'evaluate_jsonnet_project', 'evaluate_merged_settings', 'post_process_steps',
           'write_templated_files')

log = logging.getLogger(__name__)


def subprocess_log_run(*args: Any, **kwargs: Any) -> sp.CompletedProcess[Any]:
    """Run a subprocess and log its output."""
    assert isinstance(args[0], Iterable)
    log.debug('Running command: %s', ' '.join(quote(x) for x in args[0]))
    return sp.run(*args, check=kwargs.pop('check', True), **kwargs)


def post_process_steps() -> None:
    """Run post-processing steps."""
    subprocess_log_run(('poetry', 'lock'), check=True)
    subprocess_log_run(('poetry', 'install', '--all-extras', '--all-groups'), check=True)
    subprocess_log_run(('yarn',))
    subprocess_log_run(('yarn', 'format'))
    subprocess_log_run(('ruff', 'check', '--fix'), check=False)


def create_py_typed_files(settings: dict[str, Any]) -> None:
    """Create ``py.typed`` files for all packages."""
    for path in (Path(x['include']) for x in settings['pyproject']['tool']['poetry']['packages']):
        path.mkdir(parents=True, exist_ok=True)
        target = path / 'py.typed'
        target.touch()
        log.debug('Touched `%s`.', target)


def copy_static_files(merged_settings_loaded: dict[str, Any], module_path: Path) -> None:
    """Copy static files to the current directory."""
    for filename in STATIC_MODULE_FILES:
        static_path = module_path / 'static' / filename
        output_file = Path(f'{merged_settings_loaded["primary_module"]}/{filename}')
        if output_file.exists() and len(output_file.read_text()) > 0:
            log.debug('Skipping `%s`.', output_file)
            continue
        output_file.parent.mkdir(parents=True, exist_ok=True)
        copyfile(static_path, output_file)
        log.debug('Wrote `%s`.', output_file)


def download_yarn_plugins() -> None:
    """Download Yarn plugins."""
    r = requests.get(PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI, timeout=15)
    r.raise_for_status()
    plugins_dir = Path('.yarn/plugins')
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / 'plugin-prettier-after-all-installed.cjs').write_text(f'{r.text.strip()}\n',
                                                                         encoding='utf-8')


def write_templated_files(module_path: Path, merged_settings_loaded: dict[str, Any]) -> None:
    """Write templated files."""
    env = jinja2.Environment(autoescape=jinja2.select_autoescape(),
                             extensions=(ToPythonExtension,),
                             loader=jinja2.PackageLoader(__package__, 'templates'),
                             lstrip_blocks=True,
                             trim_blocks=True,
                             undefined=jinja2.StrictUndefined)
    templates_dir = module_path / 'templates'
    to_skip = merged_settings_loaded['skip']
    for file_path in templates_dir.rglob('*.j2'):
        if (file_path.name in {'__main__.py.j2', 'main.py.j2', 'test_main.py.j2'}
                and not merged_settings_loaded['want_main']):
            log.debug('Skipping template `%s`.', file_path)
            continue
        template_path = file_path.relative_to(templates_dir)
        template = env.get_template(str(template_path))
        output_file = template_path.with_suffix('')
        try:
            if output_file.parts[-2] == '_module_':
                output_file = Path(merged_settings_loaded['primary_module']) / output_file.name
        except IndexError:
            pass
        if ((output_file.exists() and len(output_file.read_text()) > 0)
                and str(output_file) in to_skip):
            log.debug('Skipping `%s`.', output_file)
            continue
        output_file.parent.mkdir(parents=True, exist_ok=True)
        content = template.render({'settings': merged_settings_loaded})
        output_file.write_text(f'{content.strip()}\n')
        log.debug('Wrote `%s`.', output_file)


def evaluate_jsonnet_project(lib_path: Path, jpathdir: list[str], merged_settings: str) -> None:
    """Evaluate ``project.jsonnet`` to output generated files."""
    for filename, content in json.loads(
            _jsonnet.evaluate_file(str(lib_path / 'project.jsonnet'),
                                   jpathdir=jpathdir,
                                   tla_codes={'settings': merged_settings})).items():
        output_file = Path(filename)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(f'{content.strip()}\n')
        log.debug('Wrote `%s`.', output_file)


def evaluate_merged_settings(jpathdir: list[str], lib_path: Path,
                             file: Path) -> tuple[str, dict[str, Any]]:
    """Evaluate the merged settings using Jsonnet."""
    s = cast(
        'str',
        _jsonnet.evaluate_snippet('',
                                  'function(defaults, settings) defaults + settings',
                                  jpathdir=jpathdir,
                                  tla_codes={
                                      'defaults': (lib_path / 'defaults.libjsonnet').read_text(),
                                      'settings': file.read_text()
                                  }))
    return s, json.loads(s)
