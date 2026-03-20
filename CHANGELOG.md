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

### Changed

- `want_claude` now defaults to `true`.
- `package.json` scripts no longer prefix tool commands with `yarn` (e.g. `yarn prettier` is now
  `prettier`).
- Formatting scripts use `ruff format` instead of `yapf` when `want_yapf` is false.
- Publish workflow now creates draft releases.

### Removed

- `want_djlint` setting and all djlint-related configuration (pre-commit hook, pyproject section,
  dependency).

## [0.0.1] - 2025-00-00

First version.

[unreleased]: https://github.com/Tatsh/wiswa/-/compare/v0.0.1...HEAD
