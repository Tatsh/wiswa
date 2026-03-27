"""GitHub repository setup."""
from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any
import asyncio
import getpass
import logging

import anyio
import keyring
import niquests

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from wiswa.typing import Settings

__all__ = ('setup_github_project',)

log = logging.getLogger(__name__)


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


async def _setup_github_session(
        session: niquests.AsyncSession) -> tuple[niquests.AsyncSession, str] | None:
    try:
        token = await anyio.to_thread.run_sync(
            lambda: keyring.get_password('tmu-github-api', getpass.getuser()))
    except keyring.errors.NoKeyringError:
        log.warning('No keyring backend available.')
        return None
    if not token:
        log.warning('No GitHub token.')
        return None
    session.headers.update({
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28'
    })
    return session, 'https://api.github.com'


async def _configure_github_repo(session: niquests.AsyncSession, host: str, repo_name: str,
                                 settings: Settings) -> None:
    (await session.patch(f'{host}/repos/{repo_name}',
                         json=_get_repo_config(settings))).raise_for_status()

    async def _put(url: str, **kwargs: Any) -> None:
        (await session.put(url, **kwargs)).raise_for_status()

    put_tasks: list[Awaitable[None]] = [
        _put(f'{host}/repos/{repo_name}/topics',
             json={'names': [x.replace(' ', '-') for x in settings['keywords']]}),
        *(_put(f'{host}/repos/{repo_name}/{ep}')
          for ep in ('automated-security-fixes', 'private-vulnerability-reporting',
                     'vulnerability-alerts')),
    ]
    if settings['github']['immutable_releases']:
        put_tasks.append(_put(f'{host}/repos/{repo_name}/immutable-releases'))
    await asyncio.gather(*put_tasks)


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

    session_data = await _setup_github_session(session)
    if not session_data:
        return

    session, host = session_data
    suffix = settings['repository_uri'].split('/')[-1]
    repo_name = f"{settings['repository_uri'].split('/')[-2]}/{suffix}"

    try:
        await _configure_github_repo(session, host, repo_name, settings)
        r = await session.get(f'{host}/repos/{repo_name}/rulesets', expire_after=0)
        r.raise_for_status()
        rulesets = r.json()
        existing: dict[str, int] = {x['name']: x['id'] for x in rulesets}
        rulesets_url = f'{host}/repos/{repo_name}/rulesets'

        async def _upsert_ruleset(ruleset: dict[str, Any]) -> None:
            name = ruleset['name']
            log.debug('Processing ruleset "%s".', name)
            if name in existing:
                (await session.put(f'{rulesets_url}/{existing[name]}',
                                   json=ruleset)).raise_for_status()
            else:
                (await session.post(rulesets_url, json=ruleset)).raise_for_status()

        await asyncio.gather(*(_upsert_ruleset(rs) for rs in _DESIRED_RULESETS))
        pages_resp = await session.get(f'{host}/repos/{repo_name}/pages')
        if pages_resp.status_code != HTTPStatus.OK:
            (await
             session.post(f'{host}/repos/{repo_name}/pages',
                          json={'source': {
                              'branch': settings['default_branch'],
                              'path': '/'
                          }})).raise_for_status()
    except niquests.HTTPError as e:
        log.warning('Caught error updating repo: %s.', e)
        log.debug('%r', e)
