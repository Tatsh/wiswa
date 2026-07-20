"""Tests for Wiswa's GitLab dispatch wrapper."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock
import json

from wiswa.tool.utils.gitlab import setup_gitlab_project
import _jsonnet  # ruff:ignore[import-private-name]
import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from wiswa.tool.typing import Settings

_WISWA_JSONNET = Path(__file__).resolve().parent.parent / 'wiswa' / 'jsonnet'


def _make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        'default_branch': 'master',
        'description': 'A test project',
        'gitlab': {},
        'homepage': 'https://example.com',
        'keywords': ['test', 'example project'],
        'package_manager': 'uv',
        'private': False,
        'project_type': 'python',
        'repository_uri': 'https://gitlab.example.com/group/sub/repo',
        'stubs_only': False,
        'using_django': False,
        'using_gitlab': True,
        'want_tests': True
    }
    base |= overrides
    return cast('Settings', base)


def test_gitlab_defaults_libsonnet_merge_preserves_other_project_settings() -> None:
    merged = json.loads(
        _jsonnet.evaluate_snippet('',
                                  """
            local g = import "defaults/gitlab.libsonnet";
            g + {
              project_settings+: {
                merge_method: "merge",
              },
            }
            """,
                                  jpathdir=[str(_WISWA_JSONNET)]))
    assert merged['project_settings']['merge_method'] == 'merge'
    assert merged['project_settings']['issues_enabled'] == 'true'


async def test_setup_gitlab_project_skips_when_not_using_gitlab(mocker: MockerFixture) -> None:
    configure = mocker.patch('wiswa.tool.utils.gitlab.configure_project')
    await setup_gitlab_project(MagicMock(), _make_settings(using_gitlab=False))
    configure.assert_not_called()


async def test_setup_gitlab_project_skips_when_no_token(mocker: MockerFixture) -> None:
    configure = mocker.patch('wiswa.tool.utils.gitlab.configure_project')
    mocker.patch('wiswa.tool.utils.gitlab.get_gitlab_token', return_value=None)
    await setup_gitlab_project(MagicMock(), _make_settings())
    configure.assert_not_called()


async def test_setup_gitlab_project_invalid_repository_uri_raises(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.tool.utils.gitlab.configure_project')
    mocker.patch('wiswa.tool.utils.gitlab.get_gitlab_token', return_value='tok')
    with pytest.raises(ValueError, match='Invalid repository URI'):
        await setup_gitlab_project(MagicMock(), _make_settings(repository_uri='https:'))


async def test_setup_gitlab_project_delegates_to_wiswa_vcs(mocker: MockerFixture) -> None:
    configure = mocker.patch('wiswa.tool.utils.gitlab.configure_project')
    mocker.patch('wiswa.tool.utils.gitlab.get_gitlab_token', return_value='tok')
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings())
    configure.assert_called_once()
    kwargs = configure.call_args.kwargs
    assert kwargs['repository_uri'] == 'https://gitlab.example.com/group/sub/repo'
    assert kwargs['description'] == 'A test project'
    assert kwargs['project_type'] == 'python'
    assert kwargs['package_manager'] == 'uv'
