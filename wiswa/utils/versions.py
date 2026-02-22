"""Version fetching and Yarn download utilities."""
from __future__ import annotations

from functools import cache
from pathlib import Path
from shutil import rmtree
from typing import cast
import re

from bs4 import BeautifulSoup as Soup
from packaging.version import InvalidVersion, Version, parse as parse_version
from wiswa.constants import PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI
from wiswa.session import cached_session

__all__ = ('download_yarn', 'download_yarn_plugins', 'get_github_release_latest_tag',
           'get_latest_yarn_version', 'get_npm_latest_package_version',
           'get_pypi_latest_package_version')

_PYPI_YANKED_RELEASES = {
    'sphinx-8.3.0',
}


@cache
def get_latest_yarn_version() -> str:  # pragma: no cover
    """Get the latest Yarn version."""
    r = cached_session().get('https://repo.yarnpkg.com/tags', timeout=15)
    r.raise_for_status()
    return cast('str', r.json()['latest']['stable'])


@cache
def get_npm_latest_package_version(package: str) -> str:  # pragma: no cover
    """Get the latest version of an NPM package."""
    r = cached_session().get(f'https://registry.npmjs.org/{package}/latest', timeout=15)
    r.raise_for_status()
    return cast('str', r.json()['version'])


@cache
def get_pypi_latest_package_version(package: str) -> str:  # pragma: no cover
    """
    Get the latest version of a PyPI package.

    Raises
    ------
    ValueError
        If no versions are found.
    """
    r = cached_session().get(f'https://pypi.org/rss/project/{package}/releases.xml', timeout=15)
    r.raise_for_status()
    root = Soup(r.content, 'xml')
    versions = [x.text for x in root.select('item > title')]
    if not versions:
        msg = f'No versions found for package `{package}`.'
        raise ValueError(msg)

    def parse_version_safe(v: str) -> Version | None:
        try:
            return parse_version(v)
        except InvalidVersion:
            return None

    return str(
        max(w for w in (parse_version_safe(v) for v in versions) if w and not w.is_prerelease
            and not w.is_devrelease and f'{package}-{w}' not in _PYPI_YANKED_RELEASES))


def download_yarn_plugins() -> None:
    """Download Yarn plugins."""
    r = cached_session().get(PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI, timeout=15)
    r.raise_for_status()
    plugins_dir = Path('.yarn/plugins')
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / 'plugin-prettier-after-all-installed.cjs').write_text(f'{r.text.strip()}\n',
                                                                         encoding='utf-8')


def download_yarn(version: str) -> None:
    """Download the specified version of Yarn and save it to ``.yarn/releases``."""
    r = cached_session().get(f'https://repo.yarnpkg.com/{version}/packages/yarnpkg-cli/bin/yarn.js',
                             timeout=15)
    r.raise_for_status()
    releases_dir = Path('.yarn/releases')
    rmtree(releases_dir, ignore_errors=True)
    releases_dir.mkdir(parents=True, exist_ok=True)
    target = releases_dir / f'yarn-{version}.cjs'
    target.write_text(f'{r.text.strip()}\n', encoding='utf-8')
    target.chmod(0o755)


@cache
def get_github_release_latest_tag(owner: str,
                                  repo: str,
                                  *,
                                  actions: bool = False,
                                  skip_releases: bool = False,
                                  allow_suffixes: bool = True) -> str:
    """
    Get the latest release tag from a GitHub repository.

    Parameters
    ----------
    owner : str
        The repository owner.
    repo : str
        The repository name.
    actions : bool
        Whether to only consider tags that look like they are for GitHub Actions.
    skip_releases : bool
        Whether to skip releases and only consider tags.
    allow_suffixes : bool
        Whether to allow tags with suffixes (e.g. ``-beta``).

    Returns
    -------
    str
        The latest release tag.

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
