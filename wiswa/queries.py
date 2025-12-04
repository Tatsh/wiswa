"""General data fetching."""
from __future__ import annotations

import re

from .session import cached_session


def get_github_release_latest_tag(owner: str,
                                  repo: str,
                                  *,
                                  actions: bool = False,
                                  skip_releases: bool = False,
                                  allow_suffixes: bool = True) -> str:
    """
    Get the latest release tag from a GitHub repository.

    Raises
    ------
    ValueError
        If no tags are found.
    """
    version: str | None = None
    session = cached_session()
    if (not skip_releases
            and (r := session.get(f'https://api.github.com/repos/{owner}/{repo}/releases/latest',
                                  timeout=15)).ok):
        version = r.json()['tag_name']
    if (not version and
        (r := session.get(f'https://api.github.com/repos/{owner}/{repo}/tags', timeout=15)).ok
            and (tags := [x['name'] for x in r.json() if 'name' in x])):
        if actions or (owner == 'google' and repo == 'yapf'):
            version = next(
                x for x in tags
                if x.startswith('v') and (re.search(r'\d$', x) if not allow_suffixes else True))
        else:
            version = tags[0]
    if not version:
        msg = f'Could not get latest tag for {owner}/{repo}.'
        raise ValueError(msg)
    if actions:
        return version.split('.')[0]
    return version
