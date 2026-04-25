"""Tests for GitLab integration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
import json

from wiswa.utils.gitlab import (
    _desired_gitlab_badges,  # noqa: PLC2701
    _sync_gitlab_badges,  # noqa: PLC2701
    setup_gitlab_project,
)
import _jsonnet  # noqa: PLC2701
import gitlab.exceptions
import keyring.errors
import pytest

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
        }
    }
    ps, pr, pa, dbp = gitlab_merged_remote_tables(_make_settings(gitlab=gitlab))
    assert ps == gitlab['project_settings']
    assert pr == gitlab['push_rules']
    assert pa == gitlab['project_approvals']
    assert dbp == gitlab['default_branch_protection']


async def test_setup_gitlab_project_skips_when_not_using_gitlab(mocker: MockerFixture) -> None:
    run_sync = mocker.patch('wiswa.utils.gitlab.run_sync')
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings(using_gitlab=False))
    run_sync.assert_not_called()


async def test_setup_gitlab_project_skips_when_no_token(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.gitlab._get_gitlab_token', return_value=None)
    run_sync = mocker.patch('wiswa.utils.gitlab.run_sync')
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
    mock_project.badges.list.return_value = []
    mock_gl = MagicMock()
    mock_gl.projects.get.return_value = mock_project
    mocker.patch('wiswa.utils.gitlab.gitlab.Gitlab', return_value=mock_gl)
    run_sync = mocker.patch('wiswa.utils.gitlab.run_sync', side_effect=lambda fn: fn())
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings())
    run_sync.assert_called_once()
    mock_gl.projects.get.assert_called_once_with('group/sub/repo')
    assert mock_project.description == 'A test project'
    assert mock_project.topics == ['test', 'example-project']


async def test_setup_gitlab_project_uses_token_from_env(monkeypatch: pytest.MonkeyPatch,
                                                        mocker: MockerFixture) -> None:
    monkeypatch.setenv('GITLAB_TOKEN', 'env-gitlab-token')
    mock_project = MagicMock()
    branch = MagicMock()
    branch.name = 'master'
    branch.attributes = {'default': True}
    mock_project.branches.list.return_value = [branch]
    mock_project.badges.list.return_value = []
    mock_gl = MagicMock()
    mock_gl.projects.get.return_value = mock_project
    gitlab_ctor = mocker.patch('wiswa.utils.gitlab.gitlab.Gitlab', return_value=mock_gl)
    mocker.patch('wiswa.utils.gitlab.run_sync', side_effect=lambda fn: fn())
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings())
    gitlab_ctor.assert_called_once()
    _, kwargs = gitlab_ctor.call_args
    assert kwargs['private_token'] == 'env-gitlab-token'
    mock_gl.projects.get.assert_called_once_with('group/sub/repo')


async def test_setup_gitlab_project_keyring_prefers_os_username(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.gitlab.os.environ.get', return_value=None)
    mocker.patch('wiswa.utils.gitlab.keyring.get_password', return_value='keyring-token')
    mock_project = MagicMock()
    branch = MagicMock()
    branch.name = 'master'
    branch.attributes = {'default': True}
    mock_project.branches.list.return_value = [branch]
    mock_project.badges.list.return_value = []
    mock_gl = MagicMock()
    mock_gl.projects.get.return_value = mock_project
    gitlab_ctor = mocker.patch('wiswa.utils.gitlab.gitlab.Gitlab', return_value=mock_gl)
    mocker.patch('wiswa.utils.gitlab.run_sync', side_effect=lambda fn: fn())
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings())
    _, kwargs = gitlab_ctor.call_args
    assert kwargs['private_token'] == 'keyring-token'


async def test_setup_gitlab_project_keyring_falls_back_to_hostname_username(
        mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.gitlab.os.environ.get', return_value=None)
    mocker.patch('wiswa.utils.gitlab.getpass.getuser', return_value='alice')

    def get_pw(service: str, user: str) -> str | None:
        if user == 'alice':
            return None
        if user == 'gitlab.example.com':
            return 'host-user-token'
        return None

    mocker.patch('wiswa.utils.gitlab.keyring.get_password', side_effect=get_pw)
    mock_project = MagicMock()
    branch = MagicMock()
    branch.name = 'master'
    branch.attributes = {'default': True}
    mock_project.branches.list.return_value = [branch]
    mock_project.badges.list.return_value = []
    mock_gl = MagicMock()
    mock_gl.projects.get.return_value = mock_project
    gitlab_ctor = mocker.patch('wiswa.utils.gitlab.gitlab.Gitlab', return_value=mock_gl)
    mocker.patch('wiswa.utils.gitlab.run_sync', side_effect=lambda fn: fn())
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings())
    _, kwargs = gitlab_ctor.call_args
    assert kwargs['private_token'] == 'host-user-token'


async def test_setup_gitlab_project_skips_when_no_keyring_backend(mocker: MockerFixture) -> None:
    mocker.patch('wiswa.utils.gitlab.os.environ.get', return_value=None)
    mocker.patch('wiswa.utils.gitlab.keyring.get_password',
                 side_effect=keyring.errors.NoKeyringError())
    run_sync = mocker.patch('wiswa.utils.gitlab.run_sync')
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings())
    run_sync.assert_not_called()


async def test_setup_gitlab_project_skips_when_empty_hostname_and_no_env_token(
        monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.delenv('GITLAB_TOKEN', raising=False)
    mocker.patch('wiswa.utils.gitlab.os.environ.get', return_value=None)
    run_sync = mocker.patch('wiswa.utils.gitlab.run_sync')
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings(repository_uri='https://'))
    run_sync.assert_not_called()


async def test_setup_gitlab_project_invalid_repository_uri_raises(monkeypatch: pytest.MonkeyPatch,
                                                                  mocker: MockerFixture) -> None:
    monkeypatch.setenv('GITLAB_TOKEN', 'tok')
    mocker.patch('wiswa.utils.gitlab.run_sync', side_effect=lambda fn: fn())
    session = MagicMock()
    with pytest.raises(ValueError, match='Invalid repository URI'):
        await setup_gitlab_project(session, _make_settings(repository_uri='https:'))


async def test_setup_gitlab_project_returns_when_project_path_empty(monkeypatch: pytest.MonkeyPatch,
                                                                    mocker: MockerFixture) -> None:
    monkeypatch.setenv('GITLAB_TOKEN', 'tok')
    gitlab_ctor = mocker.patch('wiswa.utils.gitlab.gitlab.Gitlab')
    mocker.patch('wiswa.utils.gitlab.run_sync', side_effect=lambda fn: fn())
    session = MagicMock()
    await setup_gitlab_project(session,
                               _make_settings(repository_uri='https://gitlab.example.com/'))
    gitlab_ctor.assert_not_called()


async def test_setup_gitlab_project_catches_gitlab_error(monkeypatch: pytest.MonkeyPatch,
                                                         mocker: MockerFixture) -> None:
    monkeypatch.setenv('GITLAB_TOKEN', 'tok')
    mocker.patch('wiswa.utils.gitlab.run_sync',
                 new_callable=AsyncMock,
                 side_effect=gitlab.exceptions.GitlabError)
    session = MagicMock()
    await setup_gitlab_project(session, _make_settings())


async def test_setup_gitlab_project_applies_project_settings_from_merged_settings(
        monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    monkeypatch.setenv('GITLAB_TOKEN', 'tok')
    mock_project = MagicMock()
    branch = MagicMock()
    branch.name = 'master'
    branch.attributes = {'default': True}
    mock_project.branches.list.return_value = [branch]
    mock_project.badges.list.return_value = []
    mock_gl = MagicMock()
    mock_gl.projects.get.return_value = mock_project
    mocker.patch('wiswa.utils.gitlab.gitlab.Gitlab', return_value=mock_gl)
    mocker.patch('wiswa.utils.gitlab.run_sync', side_effect=lambda fn: fn())
    session = MagicMock()
    settings = _make_settings(gitlab={'project_settings': {'issues_enabled': 'false'}})
    await setup_gitlab_project(session, settings)
    assert mock_project.issues_enabled == 'false'


def test_desired_gitlab_badges_python_uv() -> None:
    badges = _desired_gitlab_badges(_make_settings())
    names = [b['name'] for b in badges]
    assert names == [
        'QA', 'Coverage', 'Latest Release', 'mypy', 'uv', 'pytest', 'Ruff', 'pre-commit', 'Prettier'
    ]


def test_desired_gitlab_badges_python_poetry() -> None:
    badges = _desired_gitlab_badges(_make_settings(package_manager='poetry'))
    names = [b['name'] for b in badges]
    assert 'Poetry' in names
    assert 'uv' not in names


def test_desired_gitlab_badges_no_tests() -> None:
    badges = _desired_gitlab_badges(_make_settings(want_tests=False))
    names = [b['name'] for b in badges]
    assert 'Coverage' not in names
    assert 'pytest' not in names
    assert 'Latest Release' in names


def test_desired_gitlab_badges_private_includes_all_ci_badges() -> None:
    badges = _desired_gitlab_badges(_make_settings(private=True))
    names = [b['name'] for b in badges]
    assert 'Coverage' in names
    assert 'Latest Release' in names


def test_desired_gitlab_badges_stubs_only_skips_pytest() -> None:
    badges = _desired_gitlab_badges(_make_settings(stubs_only=True))
    names = [b['name'] for b in badges]
    assert 'pytest' not in names
    assert 'mypy' in names


def test_desired_gitlab_badges_non_python() -> None:
    badges = _desired_gitlab_badges(_make_settings(project_type='typescript'))
    names = [b['name'] for b in badges]
    assert 'mypy' not in names
    assert 'uv' not in names
    assert 'Ruff' not in names
    assert names == ['QA', 'Coverage', 'Latest Release', 'pre-commit', 'Prettier']


def test_desired_gitlab_badges_uses_placeholders() -> None:
    badges = _desired_gitlab_badges(_make_settings())
    base = 'https://gitlab.example.com/%{project_path}'
    by_name = {b['name']: b for b in badges}
    assert by_name['QA']['image_url'].startswith(base)
    assert '%{default_branch}' in by_name['QA']['image_url']
    assert by_name['QA']['link_url'] == f'{base}/-/pipelines'
    assert by_name['Coverage']['image_url'].startswith(base)
    assert '%{default_branch}' in by_name['Coverage']['image_url']
    assert by_name['Latest Release']['link_url'] == f'{base}/-/releases'


def test_desired_gitlab_badges_pipeline_and_coverage_ignore_skipped() -> None:
    badges = _desired_gitlab_badges(_make_settings())
    by_name = {b['name']: b for b in badges}
    assert 'ignore_skipped=true' in by_name['QA']['image_url']
    assert 'ignore_skipped=true' in by_name['Coverage']['image_url']


def test_desired_gitlab_badges_release() -> None:
    badges = _desired_gitlab_badges(_make_settings())
    by_name = {b['name']: b for b in badges}
    assert 'Latest Release' in by_name
    assert 'release.svg' in by_name['Latest Release']['image_url']
    assert '/-/releases' in by_name['Latest Release']['link_url']


def test_desired_gitlab_badges_django() -> None:
    badges = _desired_gitlab_badges(_make_settings(using_django=True))
    names = [b['name'] for b in badges]
    assert 'Django' in names
    assert names.index('Django') < names.index('mypy')


def test_sync_gitlab_badges_creates_missing() -> None:
    project = MagicMock()
    project.badges.list.return_value = []
    desired = [{
        'image_url': 'https://example.com/img.svg',
        'link_url': 'https://example.com',
        'name': 'QA'
    }]
    _sync_gitlab_badges(project, desired)
    project.badges.create.assert_called_once_with(desired[0])


def test_sync_gitlab_badges_updates_changed() -> None:
    existing_badge = MagicMock()
    existing_badge.kind = 'project'
    existing_badge.name = 'QA'
    existing_badge.image_url = 'https://old.example.com/img.svg'
    existing_badge.link_url = 'https://old.example.com'
    project = MagicMock()
    project.badges.list.return_value = [existing_badge]
    desired = [{
        'image_url': 'https://new.example.com/img.svg',
        'link_url': 'https://new.example.com',
        'name': 'QA'
    }]
    _sync_gitlab_badges(project, desired)
    assert existing_badge.image_url == 'https://new.example.com/img.svg'
    assert existing_badge.link_url == 'https://new.example.com'
    existing_badge.save.assert_called_once()
    project.badges.create.assert_not_called()


def test_sync_gitlab_badges_skips_up_to_date() -> None:
    existing_badge = MagicMock()
    existing_badge.kind = 'project'
    existing_badge.name = 'QA'
    existing_badge.image_url = 'https://example.com/img.svg'
    existing_badge.link_url = 'https://example.com'
    project = MagicMock()
    project.badges.list.return_value = [existing_badge]
    desired = [{
        'image_url': 'https://example.com/img.svg',
        'link_url': 'https://example.com',
        'name': 'QA'
    }]
    _sync_gitlab_badges(project, desired)
    existing_badge.save.assert_not_called()
    project.badges.create.assert_not_called()


def test_sync_gitlab_badges_ignores_group_badges() -> None:
    group_badge = MagicMock()
    group_badge.kind = 'group'
    group_badge.name = 'QA'
    project = MagicMock()
    project.badges.list.return_value = [group_badge]
    desired = [{
        'image_url': 'https://example.com/img.svg',
        'link_url': 'https://example.com',
        'name': 'QA'
    }]
    _sync_gitlab_badges(project, desired)
    project.badges.create.assert_called_once_with(desired[0])
    group_badge.save.assert_not_called()


def test_sync_gitlab_badges_ignores_badges_with_empty_name() -> None:
    nameless_badge = MagicMock()
    nameless_badge.kind = 'project'
    nameless_badge.name = ''
    project = MagicMock()
    project.badges.list.return_value = [nameless_badge]
    desired = [{
        'image_url': 'https://example.com/img.svg',
        'link_url': 'https://example.com',
        'name': 'QA'
    }]
    _sync_gitlab_badges(project, desired)
    project.badges.create.assert_called_once_with(desired[0])
    nameless_badge.save.assert_not_called()


def test_sync_gitlab_badges_updates_when_only_image_url_differs() -> None:
    existing_badge = MagicMock()
    existing_badge.kind = 'project'
    existing_badge.name = 'QA'
    existing_badge.image_url = 'https://old.example.com/img.svg'
    existing_badge.link_url = 'https://example.com'
    project = MagicMock()
    project.badges.list.return_value = [existing_badge]
    desired = [{
        'image_url': 'https://new.example.com/img.svg',
        'link_url': 'https://example.com',
        'name': 'QA'
    }]
    _sync_gitlab_badges(project, desired)
    assert existing_badge.image_url == 'https://new.example.com/img.svg'
    existing_badge.save.assert_called_once()


def test_sync_gitlab_badges_updates_when_only_link_url_differs() -> None:
    existing_badge = MagicMock()
    existing_badge.kind = 'project'
    existing_badge.name = 'QA'
    existing_badge.image_url = 'https://example.com/img.svg'
    existing_badge.link_url = 'https://old.example.com'
    project = MagicMock()
    project.badges.list.return_value = [existing_badge]
    desired = [{
        'image_url': 'https://example.com/img.svg',
        'link_url': 'https://new.example.com',
        'name': 'QA'
    }]
    _sync_gitlab_badges(project, desired)
    assert existing_badge.link_url == 'https://new.example.com'
    existing_badge.save.assert_called_once()


def test_sync_gitlab_badges_preserves_user_badges() -> None:
    user_badge = MagicMock()
    user_badge.kind = 'project'
    user_badge.name = 'Custom'
    project = MagicMock()
    project.badges.list.return_value = [user_badge]
    _sync_gitlab_badges(project, [{
        'image_url': 'https://example.com/img.svg',
        'link_url': 'https://example.com',
        'name': 'QA'
    }])
    user_badge.save.assert_not_called()
    user_badge.delete.assert_not_called()
