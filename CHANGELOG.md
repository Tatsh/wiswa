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

### Fixed

- Circular import between `wiswa.extensions` and `wiswa.utils.templating`.
- HTTP 403/429 errors now display a user-friendly rate-limit message instead of a traceback.
- PyInstaller and AppImage build scripts failed with "unexpected end of file" when the project had
  multiple entry points (or empty `include_only`), because heredoc `EOF` terminators were indented
  inside the `while` loop body.
- Stubs-only projects using hatchling now include `tool.hatch.build.targets.wheel.packages` in
  `pyproject.toml`, fixing wheel build failures where hatchling could not find the stubs package
  directory.

### Changed

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

### Removed

- `want_djlint` setting and all djlint-related configuration (pre-commit hook, pyproject section,
  dependency).

## [0.0.1] - 2025-00-00

First version.

[unreleased]: https://github.com/Tatsh/wiswa/-/compare/v0.0.1...HEAD
