"""Types."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypedDict

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

ProjectType = Literal['c', 'c++', 'generic', 'lua', 'python', 'typescript', 'xcode']


class VSCodeLaunchConfiguration(TypedDict):
    """Visual Studio Code launch configuration for a specific task."""
    console: str
    """The console type (e.g., 'integratedTerminal' or 'externalTerminal')."""
    env: Mapping[str, str]
    """Environment variables for the launch configuration."""
    name: str
    """The name of the launch configuration."""
    program: str
    """The path to the program to be launched."""
    request: str
    """The request type (e.g., 'launch' or 'attach')."""
    type: str
    """The type of the launch configuration (e.g., 'python')."""


class VSCodeLaunch(TypedDict):
    """Visual Studio Code launch configuration."""
    configurations: Sequence[VSCodeLaunchConfiguration]
    """A list of configurations for launching the project."""
    version: str
    """The version of the launch configuration."""


class VSCode(TypedDict):
    """Visual Studio Code settings."""
    extensions: Iterable[str]
    """A list of VS Code extensions to install."""
    launch: VSCodeLaunch
    """Launch configurations."""


class PyProjectToolPoetryPackage(TypedDict):
    """A package in the ``[tool.poetry.packages]`` section of the pyproject.toml."""
    include: str
    """The path to the package to include."""


class PyProjectToolPoetry(TypedDict, total=False):
    """``[tool.poetry]`` section of pyproject.toml."""
    dependencies: Mapping[str, str]
    """A mapping of dependencies and their versions."""
    packages: Iterable[PyProjectToolPoetryPackage]


class PyProjectToolCommitizen(TypedDict, total=False):
    """``[tool.commitizen]`` section of pyproject.toml."""
    tag_format: str
    """The format for tags."""
    version_files: Iterable[str]
    """A list of files to update with the new version after a release."""
    version_provider: str
    """The version provider to use."""


class PyProjectTool(TypedDict, total=False):
    """Tool section of pyproject.toml."""
    commitizen: PyProjectToolCommitizen
    """Commitizen configuration."""
    poetry: PyProjectToolPoetry
    """Poetry configuration."""


class PyProjectProject(TypedDict, total=False):
    """``[project]`` section of pyproject.toml."""
    authors: Iterable[str]
    """A list of authors of the project."""
    classifiers: Iterable[str]
    """A list of classifiers for the project."""
    description: str
    """A short description of the project."""
    license: str
    """The license of the project."""
    name: str
    """The name of the project."""
    version: str
    """The version of the project."""


class PyProject(TypedDict):
    """Parsed ``pyproject.toml``."""
    project: PyProjectProject
    """Project section of pyproject.toml."""
    tool: PyProjectTool
    """Tool section of pyproject.toml."""


class SettingsGitHub(TypedDict):
    """GitHub settings."""
    username: str
    """The GitHub username."""


class SettingsSocialMastodon(TypedDict):
    """Mastodon settings."""
    id: str
    """The Mastodon ID for the project or its maintainer."""
    domain: str
    """The Mastodon instance domain."""


class SettingsSocialTextAndURI(TypedDict):
    """YouTube settings."""
    text: str
    """The text shown in badge."""
    uri: str
    """URI."""


class SettingsSocial(TypedDict):
    """Social media settings."""
    bsky: str
    """The Bluesky handle for the project or its maintainer."""
    mastodon: SettingsSocialMastodon
    """The Mastodon ID for the project or its maintainer."""
    custom_badges: list[str]
    """Custom badges to include in the README."""
    youtube: SettingsSocialTextAndURI
    """YouTube settings."""
    patreon: str
    """Patreon settings."""
    cashapp: str
    """Cash App $Cashtag."""
    slashdot: str
    """The Slashdot username for the project or its maintainer."""
    calendly: SettingsSocialTextAndURI
    """The Calendly username for the project or its maintainer."""
    buymeacoffee: str
    """Buy Me a Coffee username."""
    libera_irc: str
    """The Libera.Chat IRC nickname for the project or its maintainer."""


class PackageJSON(TypedDict):
    """Parsed ``package.json``."""
    dependencies: Mapping[str, str]
    """A mapping of dependencies and their versions."""
    devDependencies: Mapping[str, str]
    """A mapping of development dependencies and their versions."""


class Settings(TypedDict):
    """Project settings."""
    default_branch: str
    """The default Git branch."""
    description: str
    """A short description of the project."""
    documentation_uri: str
    """The HTTP URI of the project's documentation."""
    github: SettingsGitHub
    """GitHub settings."""
    has_multiple_entry_points: bool
    """If the project has multiple entry points (CLI commands)."""
    homepage: str
    """The HTTP URI of the project's homepage."""
    keywords: Iterable[str]
    """A list of keywords describing the project."""
    mastodon_id: str | None
    """The Mastodon ID for the project or its maintainer."""
    package_json: PackageJSON
    """Parsed ``package.json``."""
    primary_module: str
    """The primary module."""
    private: bool
    """If the project is private."""
    project_name: str
    """The name of the project."""
    project_type: ProjectType
    """The type of the project."""
    pypi_project_name: str
    """The name of the project on PyPI."""
    pyproject: PyProject
    """Parsed ``pyproject.toml``."""
    repository_uri: str
    """The HTTP URI of the project's repository (on GitHub, etc)."""
    social: SettingsSocial
    """Social media settings."""
    stubs_only: bool
    """If the project consists of only typing stubs."""
    supported_platforms: str | list[str]
    """
    Supported platforms for the project, "all", string, or an array of strings. Values: "windows",
    "linux", "macos", "ios".
    """
    using_django: bool
    """If the project is using Django."""
    using_github: bool
    """If the project is hosted on GitHub primarily."""
    vscode: VSCode
    """Visual Studio Code settings."""
    want_claude: bool
    """If the project should include ``.claude/settings.local.json``."""
    want_codeql: bool
    """If the project should include ``.github/workflows/codeql.yml``."""
    want_copilot: bool
    """If the project should include ``.github/instructions`` dir and files."""
    want_cursor: bool
    """If the project should include ``.cursor`` dir and files."""
    claude_settings_local: dict[str, Any]
    """JSON object written to ``.claude/settings.local.json`` when ``want_claude`` is true."""
    want_docs: bool
    """If the project will generate documentation."""
    want_main: bool
    """If the project will have a script entry point."""
    want_man: bool
    """If the project will have manual pages."""
    want_tests: bool
    """If the project will have tests."""
    want_yapf: bool
    """If the project will use YAPF for formatting."""
    version: str
    """The version of the project."""
    yarn_version: str
    """The version of Yarn to use."""
    _readme_existed: bool
