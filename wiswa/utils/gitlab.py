"""GitLab repository setup."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlparse
import getpass
import logging
import os

import anyio
import gitlab
import gitlab.exceptions
import keyring

if TYPE_CHECKING:
    from wiswa.typing import Settings
    import niquests

__all__ = ('gitlab_merged_remote_tables', 'setup_gitlab_project')

log = logging.getLogger(__name__)

_GITLAB_TOKEN_ENV = 'GITLAB_TOKEN'  # noqa: S105


def gitlab_merged_remote_tables(
        settings: Settings
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """
    Return GitLab API tables from merged settings.

    Defaults and per-field overrides are applied in Jsonnet (``defaults/gitlab.libsonnet`` and
    ``gitlab+:`` in ``.wiswa.jsonnet``).

    Returns
    -------
    tuple
        ``(project_settings, push_rules, project_approvals, default_branch_protection)`` for the
        GitLab REST API.
    """
    glb = settings.get('gitlab') or {}
    project_settings = glb.get('project_settings') or {}
    push_rules = glb.get('push_rules') or {}
    project_approvals = glb.get('project_approvals') or {}
    default_branch_protection = glb.get('default_branch_protection') or {}
    return project_settings, push_rules, project_approvals, default_branch_protection


def _gitlab_base_url(uri: str) -> str:
    parsed = urlparse(uri)
    if not parsed.scheme or not parsed.netloc:
        msg = f'Invalid repository URI for GitLab: {uri!r}'
        raise ValueError(msg)
    return f'{parsed.scheme}://{parsed.netloc}'


def _gitlab_project_path_from_repository_uri(uri: str) -> str:
    parsed = urlparse(uri)
    path = parsed.path.strip('/')
    return path.removesuffix('.git')


def _repository_uri_hostname(uri: str) -> str:
    return urlparse(uri).hostname or ''


def _get_gitlab_token(host: str) -> str | None:
    """
    Resolve a GitLab API token from the environment or host-scoped keyring.

    Keyring entries use service ``wiswa-gitlab:<hostname>``. The username is usually the OS user;
    the hostname alone is also tried as the username.

    Returns
    -------
    str | None
        The token, or ``None`` if unavailable.
    """
    if token := os.environ.get(_GITLAB_TOKEN_ENV):
        return token
    if not host:
        return None
    user = getpass.getuser()
    try:
        token = keyring.get_password(f'wiswa-gitlab:{host}', user)
        if token:
            return token
        return keyring.get_password(f'wiswa-gitlab:{host}', host)
    except keyring.errors.NoKeyringError:
        log.warning('No keyring backend available.')
        return None


def _configure_gitlab_project_sync(settings: Settings, token: str) -> None:
    uri = settings['repository_uri']
    base_url = _gitlab_base_url(uri)
    project_path = _gitlab_project_path_from_repository_uri(uri)
    if not project_path:
        log.warning('Could not derive GitLab project path from %s.', uri)
        return
    gl = gitlab.Gitlab(base_url, private_token=token)
    project = gl.projects.get(project_path)
    project_settings, push_rules, project_approvals, default_branch_protection = (
        gitlab_merged_remote_tables(settings))
    for key, val in project_settings.items():
        setattr(project, key, val)
    project.description = settings['description']
    project.topics = [x.replace(' ', '-') for x in settings['keywords']]
    project.homepage_url = settings['homepage']
    project.save()
    project.pushrules.update(None, push_rules)
    project.approvals.update(None, project_approvals)
    branches = project.branches.list()
    default_branch_name = next(
        (b.name for b in branches if b.attributes.get('default')),
        settings['default_branch'],
    )
    encoded_branch = quote(default_branch_name, safe='')
    gl.http_patch(
        f'/projects/{project.get_id()}/protected_branches/{encoded_branch}',
        post_data=default_branch_protection,
    )


async def setup_gitlab_project(session: niquests.AsyncSession, settings: Settings) -> None:
    """
    Configure the GitLab project (opinionated settings, description, topics).

    Uses ``python-gitlab`` in a worker thread. Authentication uses ``GITLAB_TOKEN``, or keyring
    ``wiswa-gitlab:<hostname>`` (see README).

    Parameters
    ----------
    session : niquests.AsyncSession
        Unused; GitLab configuration uses ``python-gitlab`` with its own HTTP client.
    settings : Settings
        The project settings dictionary.
    """
    del session
    if not settings['using_gitlab']:
        log.debug('Not running GitLab setup.')
        return
    host = _repository_uri_hostname(settings['repository_uri'])
    token = _get_gitlab_token(host)
    if not token:
        log.warning('No GitLab token (set %s or keyring wiswa-gitlab:%s).', _GITLAB_TOKEN_ENV, host)
        return
    try:
        await anyio.to_thread.run_sync(lambda: _configure_gitlab_project_sync(settings, token))
    except gitlab.exceptions.GitlabError as e:
        log.warning('Caught error updating GitLab project: %s.', e)
        log.debug('%r', e)
