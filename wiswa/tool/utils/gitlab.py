"""GitLab repository setup."""
from __future__ import annotations

from typing import TYPE_CHECKING, cast
from urllib.parse import urlparse
import logging

from wiswa.vcs.gitlab import configure_project, get_gitlab_token, repository_uri_hostname

if TYPE_CHECKING:
    from wiswa.tool.typing import Settings
    from wiswa.vcs.typing import RemoteSettings
    import niquests

__all__ = ('setup_gitlab_project',)

log = logging.getLogger(__name__)


async def setup_gitlab_project(session: niquests.AsyncSession, settings: Settings) -> None:
    """
    Configure the GitLab project (opinionated settings, description, topics, badges).

    Delegates to :py:func:`wiswa.vcs.gitlab.configure_project`. Authentication uses
    ``GITLAB_TOKEN`` or the host-scoped keyring entry (see README).

    Parameters
    ----------
    session : niquests.AsyncSession
        HTTP session forwarded to ``wiswa-vcs``.
    settings : Settings
        Merged project settings.

    Raises
    ------
    ValueError
        If ``settings['repository_uri']`` cannot be parsed as a URI with both scheme and host.
    """
    if not settings['using_gitlab']:
        log.debug('Not running GitLab setup.')
        return
    uri = settings['repository_uri']
    parsed = urlparse(uri)
    if not parsed.scheme or not parsed.netloc:
        msg = f'Invalid repository URI for GitLab: {uri!r}'
        raise ValueError(msg)
    host = repository_uri_hostname(uri)
    if not get_gitlab_token(host):
        log.warning('No GitLab token (set GITLAB_TOKEN or keyring wiswa-gitlab:%s).', host)
        return
    await configure_project(session,
                            repository_uri=uri,
                            description=settings['description'],
                            homepage=settings['homepage'],
                            keywords=settings['keywords'],
                            default_branch=settings['default_branch'],
                            gitlab_config=cast('RemoteSettings | None', settings.get('gitlab')),
                            package_manager=settings['package_manager'],
                            project_type=settings['project_type'],
                            stubs_only=settings['stubs_only'],
                            using_django=settings['using_django'],
                            want_tests=settings['want_tests'])
