"""Utilities."""
from __future__ import annotations

from .github import setup_github_project
from .jsonnet import (
    FlatpakConfigurationError,
    evaluate_jsonnet_file,
    evaluate_jsonnet_project,
    evaluate_merged_settings,
    resolve_defaults_only,
    validate_flatpak_app_id,
)
from .misc import create_py_typed_files
from .path import non_empty_file_exists, primary_module_to_path, remove_empty_dirs
from .postprocess import apply_python_pyproject_manifest_edits, post_process_steps
from .static import copy_static_files
from .templating import write_templated_files
from .versions import download_yarn, download_yarn_plugins, get_latest_yarn_version

__all__ = ('FlatpakConfigurationError', 'apply_python_pyproject_manifest_edits',
           'copy_static_files', 'create_py_typed_files', 'download_yarn', 'download_yarn_plugins',
           'evaluate_jsonnet_file', 'evaluate_jsonnet_project', 'evaluate_merged_settings',
           'get_latest_yarn_version', 'non_empty_file_exists', 'post_process_steps',
           'primary_module_to_path', 'remove_empty_dirs', 'resolve_defaults_only',
           'setup_github_project', 'validate_flatpak_app_id', 'write_templated_files')
