"""Tests for GitLab integration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock
import json

from wiswa.utils.gitlab import setup_gitlab_project
import _jsonnet  # noqa: PLC2701

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from wiswa.typing import Settings

_WISWA_JSONNET = Path(__file__).resolve().parent.parent / 'wiswa-jsonnet'


def _make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        'default_branch': 'master',
        'description': 'A test project',
        'gitlab': {},
        'homepage': 'https://example.com',
        'keywords': ['test', 'example project'],
        'repository_uri': 'https://gitlab.example.com/group/sub/repo',
        'using_gitlab': True,
    }
    base |= overrides
    return cast('Settings', base)


def test_gitlab_defaults_libsonnet_merge_preserves_other_project_settings() -> None:
    merged = json.loads(
        _jsonnet.evaluate_snippet(
            '',
            """
            local g = import "defaults/gitlab.libsonnet";
            g + {
              project_settings+: {
                merge_method: "merge",
              },
            }
            """,
            jpathdir=[str(_WISWA_JSONNET)],
        ))
    assert merged['project_settings']['merge_method'] == 'merge'
    assert merged['project_settings']['issues_enabled'] == 'true'


def test_gitlab_merged_remote_tables_returns_gitlab_subsections() -> None:
    from wiswa.utils.gitlab import gitlab_merged_remote_tables

    gitlab = {
        'default_branch_protection': {
            'allow_force_push': 'false'
        },
        'project_approvals': {
            'approvals_before_merge': 2
        },
        'project_settings': {
            'issues_enabled': 'false'
        },
        'push_rules': {
            'prevent_secrets': 'false'
        },
    }
    ps, pr, pa, dbp = gitlab_merged_remote_tables(_make_settings(gitlab=gitlab))
    assert ps == gitlab['project_settings']
    assert pr == gitlab['push_rules']
    assert pa == gitlab['project_approvals']
    assert dbp == gitlab['default_branch_protection']


async def test_setup_gitlab_project_skips_when_not_using_gitlab(mocker: MockerFixture) -> None:
    run_sync = mocker.patch('wiswa.utils.gitlab.anyio.to_thread.run_sync')
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings(using_gitlab=False))
    run_sync.assert_not_called()


async def test_setup_gitlab_project_skips_when_no_token(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.gitlab._get_gitlab_token', return_value=None)
    run_sync = mocker.patch('wiswa.utils.gitlab.anyio.to_thread.run_sync')
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings())
    run_sync.assert_not_called()


async def test_setup_gitlab_project_runs_configure(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.gitlab._get_gitlab_token', return_value='test-gitlab-token')
    mock_project = MagicMock()
    branch = MagicMock()
    branch.name = 'master'
    branch.attributes = {'default': True}
    mock_project.branches.list.return_value = [branch]
    mock_gl = MagicMock()
    mock_gl.projects.get.return_value = mock_project
    mocker.patch('wiswa.utils.gitlab.gitlab.Gitlab', return_value=mock_gl)
    run_sync = mocker.patch('wiswa.utils.gitlab.anyio.to_thread.run_sync',
                            side_effect=lambda fn: fn())
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings())
    run_sync.assert_called_once()
    mock_gl.projects.get.assert_called_once_with('group/sub/repo')
    assert mock_project.description == 'A test project'
    assert mock_project.topics == ['test', 'example-project']
