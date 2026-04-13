"""GitHub repository setup."""
from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
import getpass
import logging

from anyio.to_thread import run_sync
import keyring
import keyring.errors
import niquests

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from wiswa.typing import Settings

__all__ = ('setup_github_project',)

log = logging.getLogger(__name__)

_HTTP_ERROR_BODY_LOG_MAX = 500


def _http_error_message(exc: niquests.HTTPError) -> str:
    resp = getattr(exc, 'response', None)
    code = getattr(resp, 'status_code', None) if resp is not None else None
    if code is not None:
        base = f'HTTP {code}'
    else:
        text = str(exc).strip()
        base = text or type(exc).__name__
    if resp is None:
        return base

    raw_text = getattr(resp, 'text', None)
    if isinstance(raw_text, str) and '"message":' in raw_text:
        json_fn = getattr(resp, 'json', None)
        if callable(json_fn):
            try:
                data = json_fn()
            except (ValueError, TypeError, OSError):
                data = None
            if isinstance(data, dict):
                msg = data.get('message')
                if isinstance(msg, str) and msg.strip():
                    return f'{base} — {msg.strip()}'

    if isinstance(raw_text, str):
        snippet = raw_text.strip()
        if snippet:
            if len(snippet) > _HTTP_ERROR_BODY_LOG_MAX:
                snippet = f'{snippet[:_HTTP_ERROR_BODY_LOG_MAX - 3]}...'
            return f'{base} — {snippet}'
    return base


async def _append_on_http_error(step: str, awaitable: Awaitable[None]) -> None:
    try:
        await awaitable
    except niquests.HTTPError as e:
        log.warning('GitHub setup step failed: %s (%s)', step, _http_error_message(e))


def _repository_uri_hostname(uri: str) -> str:
    return urlparse(uri).hostname or ''


def _get_github_token(settings: Settings) -> str | None:
    """
    Resolve a GitHub API token from the keyring.

    Only two lookups are used, both with the current OS username: ``wiswa-github:<hostname>``
    (hostname from ``repository_uri``, default ``github.com``; documented in the README), then
    ``tmu-github-api`` (legacy).

    Returns
    -------
    str | None
        The token, or ``None`` if unavailable.
    """
    host = _repository_uri_hostname(settings['repository_uri']) or 'github.com'
    user = getpass.getuser()
    try:
        token = keyring.get_password(f'wiswa-github:{host}', user)
        if token:
            return token
        return keyring.get_password('tmu-github-api', user)
    except keyring.errors.NoKeyringError:
        log.warning('No keyring backend available.')
        return None


def _get_repo_config(settings: Settings) -> dict[str, Any]:
    return {
        'allow_auto_merge': False,
        'allow_merge_commit': False,
        'allow_rebase_merge': True,
        'allow_squash_merge': True,
        'allow_update_branch': True,
        'archived': False,
        'delete_branch_on_merge': True,
        'dependabot_on_actions_enabled': True,
        'dependency_graph_autosubmit_action_enabled': True,
        'dependency_graph_autosubmit_action_use_labeled_runners': False,
        'description': settings['description'],
        'enable_max_pushes_checkbox': False,
        'enable_repository_funding_links': True,
        'has_discussions': False,
        'has_downloads': True,
        'has_issues': True,
        'has_pages': True,
        'has_projects': False,
        'has_wiki': False,
        'homepage': settings['homepage'],
        'include_lfs_objects': False,
        'security_and_analysis': {
            'dependabot_security_updates': {
                'status': 'enabled'
            },
            'secret_scanning': {
                'status': 'enabled'
            },
            'secret_scanning_non_provider_patterns': {
                'status': 'disabled'
            },
            'secret_scanning_push_protection': {
                'status': 'enabled'
            },
            'secret_scanning_validity_checks': {
                'status': 'disabled'
            }
        },
        'squash_merge_commit_message': 'COMMIT_MESSAGES',
        'squash_merge_commit_title': 'COMMIT_OR_PR_TITLE',
        'use_squash_pr_title_as_default': False,
        'vulnerability_updates_grouping_enabled': True,
        'web_commit_signoff_required': True
    }


async def _setup_github_session(session: niquests.AsyncSession,
                                settings: Settings) -> tuple[niquests.AsyncSession, str] | None:
    token = await run_sync(lambda: _get_github_token(settings))
    if not token:
        gh_host = _repository_uri_hostname(settings['repository_uri']) or 'github.com'
        log.warning('No GitHub token (set keyring %s for user %r).', f'wiswa-github:{gh_host}',
                    getpass.getuser())
        return None
    session.headers.update({
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28'
    })
    return session, 'https://api.github.com'


async def _configure_github_repo(session: niquests.AsyncSession, host: str, repo_name: str,
                                 settings: Settings) -> None:
    async def _patch_repo() -> None:
        r = await session.patch(f'{host}/repos/{repo_name}', json=_get_repo_config(settings))
        r.raise_for_status()

    await _append_on_http_error('repository settings', _patch_repo())

    async def _put_topics() -> None:
        r = await session.put(
            f'{host}/repos/{repo_name}/topics',
            json={'names': [x.replace(' ', '-') for x in settings['keywords']]},
        )
        r.raise_for_status()

    await _append_on_http_error('repository topics', _put_topics())

    for ep in (
            'automated-security-fixes',
            'private-vulnerability-reporting',
            'vulnerability-alerts',
    ):

        async def _put_security(endpoint: str = ep) -> None:
            r = await session.put(f'{host}/repos/{repo_name}/{endpoint}')
            r.raise_for_status()

        await _append_on_http_error(f'repository {ep}', _put_security())

    if settings['github']['immutable_releases']:

        async def _put_immutable() -> None:
            r = await session.put(f'{host}/repos/{repo_name}/immutable-releases')
            r.raise_for_status()

        await _append_on_http_error('immutable releases', _put_immutable())


_DESIRED_RULESETS: list[dict[str, Any]] = [{
    'name':
        'Protect version tags',
    'target':
        'tag',
    'bypass_actors': [{
        'actor_id': 5,
        'actor_type': 'RepositoryRole',
        'bypass_mode': 'always'
    }],
    'conditions': {
        'ref_name': {
            'exclude': [],
            'include': ['refs/tags/v*']
        }
    },
    'enforcement':
        'active',
    'rules': [{
        'type': 'deletion'
    }, {
        'type': 'non_fast_forward'
    }, {
        'type': 'required_linear_history'
    }, {
        'type': 'creation'
    }, {
        'type': 'update'
    }, {
        'type': 'required_signatures'
    }],
}, {
    'name':
        'Protect default branch',
    'target':
        'branch',
    'bypass_actors': [{
        'actor_id': 5,
        'actor_type': 'RepositoryRole',
        'bypass_mode': 'always'
    }],
    'conditions': {
        'ref_name': {
            'exclude': [],
            'include': ['~DEFAULT_BRANCH']
        }
    },
    'enforcement':
        'active',
    'rules': [{
        'type': 'deletion'
    }, {
        'type': 'non_fast_forward'
    }, {
        'parameters': {
            'allowed_merge_methods': ['squash', 'rebase'],
            'dismiss_stale_reviews_on_push': True,
            'require_code_owner_review': True,
            'require_last_push_approval': True,
            'required_approving_review_count': 1,
            'required_review_thread_resolution': True
        },
        'type': 'pull_request'
    }],
}, {
    'name': 'Copilot review for default branch',
    'target': 'branch',
    'enforcement': 'active',
    'conditions': {
        'ref_name': {
            'exclude': [],
            'include': ['~DEFAULT_BRANCH']
        }
    },
    'rules': [{
        'type': 'deletion'
    }, {
        'type': 'copilot_code_review',
        'parameters': {
            'review_on_push': True,
            'review_draft_pull_requests': True
        }
    }],
    'bypass_actors': [{
        'actor_id': 5,
        'actor_type': 'RepositoryRole',
        'bypass_mode': 'always'
    }],
}]


async def setup_github_project(session: niquests.AsyncSession, settings: Settings) -> None:
    """
    Configure the GitHub repository (topics, rulesets, security, Pages).

    API authentication uses the keyring (see README): ``wiswa-github:<hostname>``.

    HTTP failures on individual steps do not stop the rest; each failure is logged
    at warning with a short message (no traceback).

    Parameters
    ----------
    session : niquests.AsyncSession
        The HTTP session.
    settings : Settings
        The project settings dictionary.
    """
    if not settings['using_github']:
        log.debug('Not running GitHub setup.')
        return

    session_data = await _setup_github_session(session, settings)
    if not session_data:
        return

    session, host = session_data
    suffix = settings['repository_uri'].split('/')[-1]
    repo_name = f"{settings['repository_uri'].split('/')[-2]}/{suffix}"

    await _configure_github_repo(session, host, repo_name, settings)

    rulesets_state: dict[str, Any] = {'existing': {}}

    async def _fetch_rulesets() -> None:
        r = await session.get(f'{host}/repos/{repo_name}/rulesets', expire_after=0)
        r.raise_for_status()
        rulesets_state['existing'] = {x['name']: x['id'] for x in r.json()}

    await _append_on_http_error('list rulesets', _fetch_rulesets())
    existing: dict[str, int] = rulesets_state['existing']
    rulesets_url = f'{host}/repos/{repo_name}/rulesets'

    async def _upsert_ruleset(ruleset: dict[str, Any]) -> None:
        name = ruleset['name']
        log.debug('Processing ruleset "%s".', name)
        if name in existing:
            r = await session.put(f'{rulesets_url}/{existing[name]}', json=ruleset)
            r.raise_for_status()
        else:
            r = await session.post(rulesets_url, json=ruleset)
            r.raise_for_status()

    for rs in _DESIRED_RULESETS:
        await _append_on_http_error(f'upsert ruleset {rs["name"]!r}', _upsert_ruleset(rs))

    if not settings.get('private', False):

        async def _configure_pages() -> None:
            pages_response = await session.get(f'{host}/repos/{repo_name}/pages')
            if pages_response.status_code == HTTPStatus.OK:
                return
            r = await session.post(
                f'{host}/repos/{repo_name}/pages',
                json={'source': {
                    'branch': settings['default_branch'],
                    'path': '/'
                }},
            )
            r.raise_for_status()

        await _append_on_http_error('GitHub Pages', _configure_pages())
