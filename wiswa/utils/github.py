"""GitHub repository setup."""
from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any
import getpass
import logging

from wiswa.session import cached_session
import keyring
import requests

if TYPE_CHECKING:
    from wiswa.typing import Settings
    import requests_cache

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


def _setup_github_session() -> tuple[requests_cache.CachedSession, str] | None:
    token = keyring.get_password('tmu-github-api', getpass.getuser())
    if not token:
        log.warning('No GitHub token.')
        return None

    session = cached_session()
    session.headers.update({
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28'
    })
    return session, 'https://api.github.com'


def _configure_github_repo(session: requests_cache.CachedSession, host: str, repo_name: str,
                           settings: Settings) -> None:
    session.patch(f'{host}/repos/{repo_name}', json=_get_repo_config(settings)).raise_for_status()
    session.put(f'{host}/repos/{repo_name}/topics',
                json={
                    'names': [x.replace(' ', '-') for x in settings['keywords']]
                }).raise_for_status()

    # Enable security features
    for endpoint in [
            'automated-security-fixes', 'private-vulnerability-reporting', 'vulnerability-alerts'
    ]:
        session.put(f'{host}/repos/{repo_name}/{endpoint}').raise_for_status()
    if settings['github']['immutable_releases']:
        session.put(f'{host}/repos/{repo_name}/immutable-releases').raise_for_status()


def setup_github_project(settings: Settings) -> None:
    """
    Configure the GitHub repository (topics, rulesets, security, Pages).

    Parameters
    ----------
    settings : Settings
        The project settings dictionary.
    """
    if not settings['using_github']:
        log.debug('Not running GitHub setup.')
        return

    session_data = _setup_github_session()
    if not session_data:
        return

    session, host = session_data
    suffix = settings['repository_uri'].split('/')[-1]
    repo_name = f"{settings['repository_uri'].split('/')[-2]}/{suffix}"

    try:
        _configure_github_repo(session, host, repo_name, settings)
        session.put(f'{host}/repos/{repo_name}/topics',
                    json={
                        'names': [x.replace(' ', '-') for x in settings['keywords']]
                    }).raise_for_status()
        session.put(f'{host}/repos/{repo_name}/automated-security-fixes').raise_for_status()
        session.put(f'{host}/repos/{repo_name}/private-vulnerability-reporting').raise_for_status()
        session.put(f'{host}/repos/{repo_name}/vulnerability-alerts').raise_for_status()
        r = session.get(f'{host}/repos/{repo_name}/rulesets')
        r.raise_for_status()
        rulesets = r.json()
        names = [x['name'] for x in rulesets]
        if 'Protect version tags' not in names:
            session.post(f'{host}/repos/{repo_name}/rulesets',
                         json={
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
                         }).raise_for_status()
        if 'Protect default branch' not in names:
            session.post(f'{host}/repos/{repo_name}/rulesets',
                         json={
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
                                     'automatic_copilot_code_review_enabled': False,
                                     'dismiss_stale_reviews_on_push': True,
                                     'require_code_owner_review': True,
                                     'require_last_push_approval': True,
                                     'required_approving_review_count': 1,
                                     'required_review_thread_resolution': True
                                 },
                                 'type': 'pull_request'
                             }],
                         }).raise_for_status()
        if 'Copilot review for default branch' not in names:
            session.post(f'{host}/repos/{repo_name}/rulesets',
                         json={
                             'name':
                                 'Copilot review for default branch',
                             'target':
                                 'branch',
                             'enforcement':
                                 'active',
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
                         }).raise_for_status()
        if session.get(f'{host}/repos/{repo_name}/pages').status_code != HTTPStatus.OK:
            session.post(f'{host}/repos/{repo_name}/pages',
                         json={
                             'source': {
                                 'branch': settings['default_branch'],
                                 'path': '/'
                             }
                         }).raise_for_status()
    except requests.HTTPError as e:
        log.warning('Caught error updating repo: %s.', e.response.text)
