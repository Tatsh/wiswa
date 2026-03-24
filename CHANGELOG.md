<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `want_claude_agents` setting to generate `.claude/agents/`, skill files, `CLAUDE.md`, and
  `AGENTS.md` in target projects. Enabled by default when `want_claude` is true.
- PyInstaller settings: `include_only`, `collect_data`, `collect_submodules`, `hidden_imports`,
  `test_commands`, `uv_sync_args`, and `vcpkg` for finer control over PyInstaller builds.
- AppImage settings: `include_only`, `test_commands`, `uv_sync_args`, and `requirements_filter`.
- Platform support (`sys_platform`) in Poetry-to-PEP 508 dependency conversion.
- `dict:update` script to `package.json` for regenerating the cspell dictionary.
- Prettier override for `*.json.dist` files.
- Pre-commit CI skip list for hooks that should not run in CI.
- Expanded default Claude permissions (git, grep, formatting, QA, and test commands).
- `github.immutable_releases` setting (defaults to `true`) that enables immutable releases on the
  GitHub repository, preventing release assets from being modified after publication.
- SBOM attestation in PyInstaller and AppImage workflows using `anchore/sbom-action` and
  `actions/attest-sbom`.
- FastMCP server for Wiswa settings discovery and override guidance. New `wiswa-mcp` entry point
  exposes four MCP tools (`get_defaults`, `lookup_setting`, `list_settings`, `search_settings`) that
  resolve Wiswa's Jsonnet defaults and help AI assistants set settings in `.wiswa.jsonnet`.
- Animated spinner progress indicator in non-debug mode showing the current operation. Prints
  `Done.` on success and red `Failed.` on error. Friendly error messages for `RuntimeError`
  (e.g. Jsonnet evaluation failures, GitHub API rate limiting).
- `on_command` callback parameter on `post_process_steps` and `_subprocess_log_run`, allowing
  callers to be notified of each subprocess command line before it runs.
- `package_sources` setting for custom package index sources (PyPI alternatives) in generated
  `pyproject.toml`.
- `using_gitlab` setting in the `Settings` TypedDict, enabling GitLab-aware template rendering.
- GitLab equivalents in agent and skill templates: GitHub-specific content (Dependabot references,
  `.github/instructions/` paths, workflow prefix examples, issue trailer text) is now conditional
  with GitLab alternatives emitted where appropriate.
- GitLab CI support in the `workflow-shellcheck` agent template (`.gitlab-ci.yml` with `script:`,
  `before_script:`, and `after_script:` blocks) alongside existing GitHub Actions workflow support.
- `_CI_PLATFORM_AGENTS` set to skip CI-platform-specific agents when neither GitHub nor GitLab is
  used.
- GitLab-specific managed files (`.gitlab-ci.yml`) documented in the `wiswa-sync` agent alongside
  the existing GitHub section.

### Fixed

- Circular import between `wiswa.extensions` and `wiswa.utils.templating`.
- HTTP 403/429 errors now display a user-friendly rate-limit message instead of a traceback.
- `markdownlint-cli2` invocations in the non-yapf code path of `post_process_steps` were missing
  `--config package.json --configPointer /markdownlint-cli2` flags, causing the linter to ignore
  project configuration.
- Duplicate `--configPointer` flag in generated `package.json` scripts (in `package.libjsonnet`).
- PyInstaller and AppImage build scripts failed with "unexpected end of file" when the project had
  multiple entry points (or empty `include_only`), because heredoc `EOF` terminators were indented
  inside the `while` loop body.
- Stubs-only projects using hatchling now include `tool.hatch.build.targets.wheel.packages` in
  `pyproject.toml`, fixing wheel build failures where hatchling could not find the stubs package
  directory.
- Hatchling `[tool.hatch.build.targets.wheel] packages` is now generated for all projects where the
  `primary_module` differs from the normalised `project_name`, not only stubs-only projects. This
  fixes wheel builds for projects like `chocolatey-choco` whose module name (`choco`) does not match
  the PyPI name. Non-stubs projects use `settings.modules` for the packages list.
- C/C++ `format` script now includes `markdownlint-cli2 --fix` invocation.
- `poetryVerToPep508` now prefixes bare version numbers with `==` instead of leaving them unqualified.
- GitHub Pages badge URL now lowercases the username for correct `.github.io` domain resolution.
- MCP server's `_get_defaults()` did not pass an `aiohttp.ClientSession` to `resolve_defaults_only()`,
  so native Jsonnet callbacks for version lookups (e.g. `latestNpmPackageVersion`) were never
  registered, causing a "only functions can be called, got null" runtime error when any MCP tool
  tried to resolve defaults.

### Changed

- Converted the entire project from synchronous to async. `requests`/`requests-cache` replaced with
  `aiohttp`/`aiohttp-client-cache`, `subprocess.run` replaced with `asyncio.create_subprocess_exec`,
  and synchronous file I/O replaced with `anyio.Path`. All utility functions are now async. The Click
  CLI entry point bridges to async via `anyio.run()`. Jinja2 templates use async mode.
- Generated workflow templates now include path-based filtering to skip unnecessary CI runs. Tests,
  QA, Flatpak, Snap, AppImage, and PyInstaller workflows only trigger when relevant source files
  change. QA workflows use `dorny/paths-filter` to conditionally skip language-specific checks
  (Ruff/mypy for Python, ESLint for TypeScript, clang-format for C/C++).
- Badges in `docs/index.rst.j2` extracted into a separate `docs/badges.rst.j2` template included
  via `.. include:: badges.rst`, allowing the badge-sync agent to update badges independently.
- `want_claude` now defaults to `true`.
- `package.json` scripts no longer prefix tool commands with `yarn` (e.g. `yarn prettier` is now
  `prettier`).
- Formatting scripts use `ruff format` instead of `yapf` when `want_yapf` is false.
- Publish workflow now creates draft releases.
- `.claude/settings.local.json.dist` is now generated dynamically from `claude_settings_local`
  instead of being copied from a static file. It is written alongside `.claude/settings.local.json`
  when `want_claude` is true.
- HTTP response cache now expires after 10 minutes instead of 30 minutes and ignores upstream
  `Cache-Control` headers, preventing rate-limiting on immediate subsequent runs.
- Simplified unreachable `elif` branch to `else` in `list_settings` MCP tool.
- Added `# pragma: no cover` to genuinely untestable code paths (MCP entry point, async-to-sync
  thread bridge, defensive `KeyError` handler, aiohttp trace callback).
- Tests now use public APIs instead of importing private functions (`_parse_md_badge`,
  `_make_native_callbacks`, `_on_request_end`).
- Achieved 100% branch coverage with new tests for MCP defaults caching, `list_settings` depth edge
  cases, subprocess failure handling, `on_command` callback, custom project badges, badge generation
  branches, session pass-through, agent skipping for non-Python projects, Jsonnet session callbacks,
  and GitHub tag cache hits.

### Removed

- `want_djlint` setting and all djlint-related configuration (pre-commit hook, pyproject section,
  dependency).

## [0.0.1] - 2025-00-00

First version.

[unreleased]: https://github.com/Tatsh/wiswa/-/compare/v0.0.1...HEAD
