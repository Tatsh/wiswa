"""GitHub repository setup."""
from __future__ import annotations

from typing import TYPE_CHECKING
import logging

from anyio.to_thread import run_sync
from wiswa.vcs.github import (
    USER_AGENT,
    NiquestsGitHubAPI,
    configure_project,
    get_github_token,
    get_pages_build_type,
    slug_from_uri,
)
from wiswa.vcs.gitlab import repository_uri_hostname

if TYPE_CHECKING:
    from wiswa.tool.typing import Settings
    from wiswa.vcs.github import PagesBuildType
    import niquests

__all__ = ('get_github_pages_build_type', 'setup_github_project')

log = logging.getLogger(__name__)


def _resolve_github_token(settings: Settings) -> str | None:
    host = repository_uri_hostname(settings['repository_uri']) or 'github.com'
    return get_github_token(host)


async def get_github_pages_build_type(session: niquests.AsyncSession,
                                      settings: Settings) -> PagesBuildType | None:
    """
    Return the GitHub Pages ``build_type`` for the repository.

    Parameters
    ----------
    session : ~niquests.AsyncSession
        HTTP session forwarded to the wiswa-vcs GitHub API client.
    settings : Settings
        Project settings dictionary.

    Returns
    -------
    PagesBuildType | None
        ``'legacy'`` when Pages deploys from a branch, ``'workflow'`` when it uses GitHub Actions,
        or ``None`` when the token is unavailable or the API call fails.
    """
    token = await run_sync(lambda: _resolve_github_token(settings))
    if not token:
        return None
    api = NiquestsGitHubAPI(session, USER_AGENT, oauth_token=token)
    return await get_pages_build_type(api, slug_from_uri(settings['repository_uri']))


async def setup_github_project(session: niquests.AsyncSession, settings: Settings) -> None:
    """
    Configure the GitHub repository (topics, rulesets, security, Pages).

    Delegates to :py:func:`wiswa.vcs.github.configure_project`. API authentication uses the
    keyring (see README): ``wiswa-github:<hostname>``.

    Parameters
    ----------
    session : niquests.AsyncSession
        HTTP session forwarded to ``wiswa-vcs``.
    settings : Settings
        Merged project settings.
    """
    if not settings['using_github']:
        log.debug('Not running GitHub setup.')
        return
    await configure_project(session,
                            repository_uri=settings['repository_uri'],
                            description=settings['description'],
                            homepage=settings['homepage'],
                            keywords=settings['keywords'],
                            default_branch=settings['default_branch'],
                            private=settings.get('private', False),
                            immutable_releases=settings['github']['immutable_releases'])
