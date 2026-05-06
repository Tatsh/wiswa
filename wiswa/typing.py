"""Type definitions for Wiswa settings and related structures."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypeAlias, TypedDict

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

__all__ = ('CustomProjectBadge', 'ExportRequirements', 'GitlabRemoteSettings', 'PackageJSON',
           'PackageManager', 'ProjectType', 'PyProject', 'PyProjectBuildSystem', 'PyProjectProject',
           'PyProjectTool', 'PyProjectToolCommitizen', 'PyProjectToolPoetry',
           'PyProjectToolPoetryPackage', 'PythonDeps', 'Settings', 'SettingsGitHub',
           'SettingsSocial', 'SettingsSocialMastodon', 'SettingsSocialTextAndURI', 'VSCode',
           'VSCodeLaunch', 'VSCodeLaunchConfiguration')

PackageManager: TypeAlias = Literal['poetry', 'uv']
"""
The Python package manager to use.

:meta hide-value:
"""
ProjectType: TypeAlias = Literal['c', 'c++', 'generic', 'lua', 'python', 'typescript', 'xcode']
"""
The type of project being generated.

:meta hide-value:
"""


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
    """A list of packages to include in the distribution."""


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
    dependencies: Sequence[str]
    """A list of PEP 508 dependency strings (used with uv)."""
    description: str
    """A short description of the project."""
    license: str
    """The project licence."""
    name: str
    """The name of the project."""
    version: str
    """The version of the project."""


class PyProjectBuildSystem(TypedDict, total=False):
    """``[build-system]`` section of pyproject.toml."""

    requires: Sequence[str]
    """Build system requirements."""
    build_backend: str
    """Build backend to use."""


class PyProject(TypedDict, total=False):
    """Parsed ``pyproject.toml``."""

    build_system: PyProjectBuildSystem
    """Build system section of pyproject.toml."""
    dependency_groups: Mapping[str, Sequence[str]]
    """Dependency groups (used with uv)."""
    project: PyProjectProject
    """Project section of pyproject.toml."""
    tool: PyProjectTool
    """Tool section of pyproject.toml."""


class PythonDeps(TypedDict, total=False):
    """Python dependency groups in Poetry-style syntax."""

    main: Mapping[str, Any]
    """Main project dependencies."""
    dev: Mapping[str, Any]
    """Development dependencies."""
    docs: Mapping[str, Any]
    """Documentation dependencies."""
    tests: Mapping[str, Any]
    """Test dependencies."""


class GitlabRemoteSettings(TypedDict, total=False):
    """GitLab API tables from merged settings (see ``defaults/gitlab.libsonnet``)."""

    project_settings: dict[str, Any]
    """Project attributes for ``python-gitlab`` (from merged ``gitlab.project_settings``)."""
    push_rules: dict[str, Any]
    """Push rules payload (from merged ``gitlab.push_rules``)."""
    project_approvals: dict[str, Any]
    """Merge request approval settings (from merged ``gitlab.project_approvals``)."""
    default_branch_protection: dict[str, Any]
    """Protected default branch PATCH body (from merged ``gitlab.default_branch_protection``)."""


class SettingsGitHub(TypedDict):
    """GitHub settings."""

    immutable_releases: bool
    """If releases should be immutable."""
    username: str
    """The GitHub username."""


class CustomProjectBadge(TypedDict, total=False):
    """A custom project badge displayed before the social section in the README."""

    anchor: str
    """Markdown anchor text, e.g. ``[![alt](image_url)]``."""
    href: str
    """Link target URL."""
    priority: int
    """Sort key (default 0). Lower values appear first."""


class SettingsSocialMastodon(TypedDict):
    """Mastodon settings."""

    id: str
    """The Mastodon ID for the project or its maintainer."""
    domain: str
    """The Mastodon instance domain."""


class SettingsSocialTextAndURI(TypedDict):
    """A social media entry with display text and a URI."""

    text: str
    """The text shown in the badge."""
    uri: str
    """The target URI for the badge link."""


class SettingsSocial(TypedDict):
    """Social media settings."""

    bsky: str
    """The Bluesky handle for the project or its maintainer."""
    mastodon: SettingsSocialMastodon
    """Mastodon account for the project or its maintainer."""
    custom_badges: list[str]
    """Custom badges to include in the README."""
    youtube: SettingsSocialTextAndURI
    """YouTube link for the README (display text and URI)."""
    patreon: str
    """The Patreon username for the project or its maintainer."""
    cashapp: str
    """Cash App $Cashtag."""
    slashdot: str
    """The Slashdot username for the project or its maintainer."""
    calendly: SettingsSocialTextAndURI
    """Calendly link for the README (display text and URI)."""
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


class ExportRequirements(TypedDict, total=False):
    """Configuration for exporting requirements from the lock file."""

    enabled: bool
    """Whether to run the export step and add a pre-commit hook."""
    format: str
    """Output format (``requirements.txt``, ``pylock.toml``, ``cyclonedx1.5``)."""
    output_filename: str
    """Path to write the exported file."""
    all_extras: bool
    """Include all optional dependencies."""
    all_groups: bool
    """Include dependencies from all dependency groups."""
    all_packages: bool
    """Export the entire workspace."""
    extra: Sequence[str]
    """Include optional dependencies from these extra names."""
    frozen: bool
    """Do not update the lock file before exporting."""
    group: Sequence[str]
    """Include dependencies from these dependency groups."""
    locked: bool
    """Assert that the lock file will remain unchanged."""
    no_annotate: bool
    """Exclude comment annotations indicating the source of each package."""
    no_default_groups: bool
    """Ignore the default dependency groups."""
    no_dev: bool
    """Disable the development dependency group."""
    no_editable: bool
    """Export editable dependencies as non-editable."""
    no_emit_local: bool
    """Do not include local path dependencies."""
    no_emit_package: Sequence[str]
    """Do not emit these packages."""
    no_emit_project: bool
    """Do not emit the current project."""
    no_emit_workspace: bool
    """Do not emit any workspace members."""
    no_extra: Sequence[str]
    """Exclude these optional dependencies when ``all_extras`` is set."""
    no_group: Sequence[str]
    """Disable these dependency groups."""
    no_hashes: bool
    """Omit hashes in the generated output."""
    no_header: bool
    """Exclude the comment header."""
    only_dev: bool
    """Only include the development dependency group."""
    only_group: Sequence[str]
    """Only include dependencies from these groups."""
    package: Sequence[str]
    """Export dependencies for these specific workspace packages."""
    prune: Sequence[str]
    """Prune these packages from the dependency tree."""
    script: str
    """Export dependencies for a PEP 723 script instead of the project."""
    with_hashes: bool
    """Include hashes (default ``True``; set to ``False`` to pass ``--no-hashes``)."""


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
    github_project_name: str
    """The GitHub repository name (may differ from :py:attr:`project_name`)."""
    gitlab: GitlabRemoteSettings
    """GitLab remote project tables (merged in Jsonnet; see ``defaults/gitlab.libsonnet``)."""
    has_multiple_entry_points: bool
    """If the project has multiple entry points (CLI commands)."""
    homepage: str
    """The HTTP URI of the project's homepage."""
    keywords: Iterable[str]
    """A list of keywords describing the project."""
    mastodon_id: str | None
    """The Mastodon ID for the project or its maintainer."""
    node_engine: str
    """
    Node-engine constraint written into ``package_json.engines.node`` and consulted by
    ``utils.latestNpmPackageVersion*`` to filter candidate npm releases by the target Node major.
    """
    npm_age_gate_exclude_packages: Iterable[str]
    """
    npm package names whose ``utils.latestNpmPackageVersion*`` lookups bypass the
    ``yarnrc.npmMinimalAgeGate`` cutoff, used when a freshly published trusted dependency must
    be consumed before the gate window elapses.
    """
    package_json: PackageJSON
    """Parsed ``package.json``."""
    primary_module: str
    """
    Import name for the layout Wiswa manages; dots denote nested packages on disk.

    For a PEP 420 namespace root, use a single top-level segment here and set
    ``primary_module_qualified`` to the full dotted import path.
    """
    primary_module_qualified: str
    """
    Fully qualified import name for the on-disk package (e.g. ``vendor.product.service``).

    Defaults to the same value as ``primary_module``. A namespace-style layout (namespace root plus
    a deeper package) is inferred when this differs from ``primary_module`` and contains a dot.
    """
    private: bool
    """If the project is private."""
    project_name: str
    """The name of the project."""
    project_type: ProjectType
    """The type of the project."""
    pypi_project_name: str
    """The name of the project on PyPI."""
    python_deps: PythonDeps
    """Python dependencies in Poetry-style syntax."""
    pyproject: PyProject
    """Parsed ``pyproject.toml``."""
    repository_uri: str
    """The HTTP URI of the project's repository (on GitHub, etc.)."""
    social: SettingsSocial
    """Social media settings."""
    stubs_only: bool
    """If the project consists of only typing stubs."""
    supported_platforms: str | list[str]
    """
    Supported platforms for the project, ``'all'``, string, or an array of strings. Values:
    ``'windows'``, ``'linux'``, ``'macos'``, ``'ios'``.
    """
    using_django: bool
    """If the project is using Django."""
    using_github: bool
    """If the project is hosted on GitHub primarily."""
    using_gitlab: bool
    """If the project is hosted on GitLab primarily."""
    vscode: VSCode
    """Visual Studio Code settings."""
    want_ai: bool
    """If the project should include ``AGENTS.md``, ``CLAUDE.md``, and the ``.claude/`` tree."""
    uses_user_defaults: bool
    """
    If user-level ``defaults.jsonnet`` is merged with project settings.

    Wiswa detects this only from a literal ``uses_user_defaults: true`` in ``.wiswa.jsonnet``; the
    flag cannot be enabled from user ``defaults.jsonnet`` alone.
    """
    want_appimage: bool
    """If the project should generate an AppImage workflow."""
    want_codeql: bool
    """If the project should include ``.github/workflows/codeql.yml``."""
    want_gpg: bool
    """If Git commits and tags should be GPG-signed."""
    claude_settings_local: dict[str, Any]
    """JSON object written to ``.claude/settings.local.json`` when ``want_ai`` is true."""
    custom_project_badges: Sequence[CustomProjectBadge]
    """Custom project badges displayed before the social section in the README."""
    export_requirements: ExportRequirements
    """Configuration for exporting requirements from the lock file."""
    want_docs: bool
    """If the project will generate documentation."""
    sphinx_fail_on_warning: bool
    """If Sphinx runs should treat warnings as errors."""
    want_main: bool
    """If the project will have a script entry point."""
    want_man: bool
    """If the project will have manual pages."""
    package_manager: PackageManager
    """The Python package manager to use ('poetry' or 'uv')."""
    regenerate_yarn_lock: bool
    """If ``yarn.lock`` should be deleted before running Yarn during post-processing."""
    want_tests: bool
    """If the project will have tests."""
    want_yapf: bool
    """If the project will use YAPF for formatting."""
    version: str
    """The version of the project."""
    yarn_version: str
    """The version of Yarn to use."""
    _readme_existed: bool
    """
    Whether ``README.md`` existed before the current Wiswa run (informational).

    README badge refresh runs whenever ``README.md`` is present after templating.
    """
    _has_established_pytest_modules: bool
    """
    Whether ``tests/`` already contained ``test_*.py`` files other than ``test_main.py`` before
    templating (used to skip the starter ``tests/test_main.py``).
    """
