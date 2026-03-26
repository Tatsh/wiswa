"""Version fetching and Yarn download utilities."""
from __future__ import annotations

from pathlib import Path
from shutil import rmtree
from typing import TYPE_CHECKING, cast
import re

from bs4 import BeautifulSoup as Soup
from packaging.version import InvalidVersion, Version, parse as parse_version
from wiswa.constants import PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI
import anyio

if TYPE_CHECKING:
    from aiohttp import ClientSession

__all__ = ('download_yarn', 'download_yarn_plugins', 'get_github_release_latest_tag',
           'get_latest_yarn_version', 'get_npm_latest_package_version',
           'get_pypi_latest_package_version')

_PYPI_YANKED_RELEASES = {
    'sphinx-8.3.0',
}

_cache: dict[str, str] = {}


async def get_latest_yarn_version(session: ClientSession) -> str:  # pragma: no cover
    """
    Get the latest Yarn version.

    Parameters
    ----------
    session : ClientSession
        The aiohttp session.

    Returns
    -------
    str
        The latest stable Yarn version string.
    """
    key = 'yarn_latest'
    if key in _cache:
        return _cache[key]
    async with session.get('https://repo.yarnpkg.com/tags', timeout=15) as resp:
        resp.raise_for_status()
        data = await resp.json()
    result = cast('str', data['latest']['stable'])
    _cache[key] = result
    return result


async def get_npm_latest_package_version(session: ClientSession,
                                         package: str) -> str:  # pragma: no cover
    """
    Get the latest version of an NPM package.

    Parameters
    ----------
    session : ClientSession
        The aiohttp session.
    package : str
        The NPM package name.

    Returns
    -------
    str
        The latest version string.
    """
    key = f'npm_{package}'
    if key in _cache:
        return _cache[key]
    async with session.get(f'https://registry.npmjs.org/{package}/latest', timeout=15) as resp:
        resp.raise_for_status()
        data = await resp.json()
    result = cast('str', data['version'])
    _cache[key] = result
    return result


async def get_pypi_latest_package_version(session: ClientSession,
                                          package: str) -> str:  # pragma: no cover
    """
    Get the latest version of a PyPI package.

    Parameters
    ----------
    session : ClientSession
        The aiohttp session.
    package : str
        The PyPI package name.

    Returns
    -------
    str
        The latest non-prerelease, non-dev version string.

    Raises
    ------
    ValueError
        If no versions are found.
    """
    key = f'pypi_{package}'
    if key in _cache:
        return _cache[key]
    async with session.get(f'https://pypi.org/rss/project/{package}/releases.xml',
                           timeout=15) as resp:
        resp.raise_for_status()
        content = await resp.read()
    root = Soup(content, 'xml')
    versions = [x.text for x in root.select('item > title')]
    if not versions:
        msg = f'No versions found for package `{package}`.'
        raise ValueError(msg)

    def parse_version_safe(v: str) -> Version | None:
        try:
            return parse_version(v)
        except InvalidVersion:
            return None

    result = str(
        max(w for w in (parse_version_safe(v) for v in versions) if w and not w.is_prerelease
            and not w.is_devrelease and f'{package}-{w}' not in _PYPI_YANKED_RELEASES))
    _cache[key] = result
    return result


async def download_yarn_plugins(session: ClientSession) -> None:
    """
    Download Yarn plugins.

    Parameters
    ----------
    session : ClientSession
        The aiohttp session.
    """
    async with session.get(PLUGIN_PRETTIER_AFTER_ALL_INSTALLED_URI, timeout=15) as resp:
        resp.raise_for_status()
        text = await resp.text()
    plugins_dir = anyio.Path('.yarn/plugins')
    await plugins_dir.mkdir(parents=True, exist_ok=True)
    await (plugins_dir / 'plugin-prettier-after-all-installed.cjs').write_text(f'{text.strip()}\n',
                                                                               encoding='utf-8')


async def download_yarn(session: ClientSession, version: str) -> None:
    """
    Download the specified version of Yarn and save it to ``.yarn/releases``.

    Parameters
    ----------
    session : ClientSession
        The aiohttp session.
    version : str
        The Yarn version to download.
    """
    async with session.get(f'https://repo.yarnpkg.com/{version}/packages/yarnpkg-cli/bin/yarn.js',
                           timeout=15) as resp:
        resp.raise_for_status()
        text = await resp.text()
    releases_dir = Path('.yarn/releases')
    await anyio.to_thread.run_sync(lambda: rmtree(releases_dir, ignore_errors=True))
    aio_releases_dir = anyio.Path(releases_dir)
    await aio_releases_dir.mkdir(parents=True, exist_ok=True)
    target = aio_releases_dir / f'yarn-{version}.cjs'
    await target.write_text(f'{text.strip()}\n', encoding='utf-8')
    await anyio.to_thread.run_sync(lambda: Path(target).chmod(0o755))


async def get_github_release_latest_tag(session: ClientSession,
                                        owner: str,
                                        repo: str,
                                        *,
                                        actions: bool = False,
                                        skip_releases: bool = False,
                                        allow_suffixes: bool = True) -> str:
    """
    Get the latest release tag from a GitHub repository.

    Parameters
    ----------
    session : ClientSession
        The aiohttp session.
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
    key = f'gh_{owner}/{repo}_{actions}_{skip_releases}_{allow_suffixes}'
    if key in _cache:
        return _cache[key]
    version: str | None = None
    if not skip_releases:
        async with session.get(f'https://api.github.com/repos/{owner}/{repo}/releases/latest',
                               timeout=15) as resp:
            if resp.ok:
                data = await resp.json()
                version = data['tag_name']
    if not version:
        async with session.get(f'https://api.github.com/repos/{owner}/{repo}/tags',
                               timeout=15) as resp:
            if resp.ok:
                data = await resp.json()
                tags = [x['name'] for x in data if 'name' in x]
                if tags:
                    if actions or (owner == 'google' and repo == 'yapf'):
                        version = next(x for x in tags if x.startswith('v') and (
                            re.search(r'\d$', x) if not allow_suffixes else True))
                    else:
                        version = tags[0]
    if not version:
        msg = f'Could not get latest tag for {owner}/{repo}.'
        raise ValueError(msg)
    result = version.split('.')[0] if actions else version
    _cache[key] = result
    return result
