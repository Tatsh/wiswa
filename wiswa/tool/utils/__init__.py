"""Utilities."""
from __future__ import annotations

from .github import get_github_pages_build_type, setup_github_project
from .gitlab import setup_gitlab_project
from .jsonnet import (
    FlatpakConfigurationError,
    RemoteHostConflictError,
    evaluate_jsonnet_file,
    evaluate_jsonnet_project,
    evaluate_merged_settings,
    resolve_defaults_only,
    validate_flatpak_app_id,
    validate_remote_host_flags,
)
from .misc import create_py_typed_files
from .path import non_empty_file_exists, primary_module_to_path, remove_empty_dirs
from .postprocess import apply_python_pyproject_manifest_edits, post_process_steps
from .run_metadata import get_wiswa_version_or_sha, write_wiswa_run_metadata
from .static import copy_static_files
from .templating import write_templated_files
from .versions import download_yarn, download_yarn_plugins, get_latest_yarn_version

__all__ = ('FlatpakConfigurationError', 'RemoteHostConflictError',
           'apply_python_pyproject_manifest_edits', 'copy_static_files', 'create_py_typed_files',
           'download_yarn', 'download_yarn_plugins', 'evaluate_jsonnet_file',
           'evaluate_jsonnet_project', 'evaluate_merged_settings', 'get_github_pages_build_type',
           'get_latest_yarn_version', 'get_wiswa_version_or_sha', 'non_empty_file_exists',
           'post_process_steps', 'primary_module_to_path', 'remove_empty_dirs',
           'resolve_defaults_only', 'setup_github_project', 'setup_gitlab_project',
           'validate_flatpak_app_id', 'validate_remote_host_flags', 'write_templated_files',
           'write_wiswa_run_metadata')
