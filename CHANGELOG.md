<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `--no-cache` CLI option to disable HTTP response caching.
- `--cache-time` CLI option to set cache expiry duration in seconds.
- `--skip-yarn` CLI option to skip Yarn download.
- `--skip-static` CLI option to skip static file copying.
- `--skip-postprocess` CLI option to skip post-processing.
- `-o`/`--output-dir` CLI option to set the output directory for generated files.
- `-q`/`--quiet` CLI option to suppress the progress spinner.
- Optional Windows Authenticode signing and macOS code signing with notarisation steps to the
  PyInstaller workflow template (`pyinstaller.yml.j2`).
- Configurable GitHub secret variable names under `github.secret_vars` in `defaults.libsonnet`,
  allowing users to customise the secret names used for binary signing.
- Sphinx documentation page (`docs/binary-signing.rst`) explaining how to set up binary signing.

### Changed

- Replaced `aiohttp` and `aiohttp-client-cache` with `niquests` as the HTTP client. The session
  module now implements its own filesystem-backed cache via `CachedAsyncSession`. HTTP/2 and HTTP/3
  are supported natively.
- urllib3 request logging now appears in debug mode. Noisy `urllib3.util.retry` messages are
  suppressed.
- Jsonnet evaluation now emits a debug log message.
- Parallelised independent async operations across the generation pipeline for faster project
  creation and updates:
  - `wiswa/main.py`: Yarn download and plugin fetch now run concurrently; static file copying and
    `py.typed` creation also run in parallel.
  - `wiswa/utils/templating.py`: Common, agent/skill, and Python-specific template writes now
    execute concurrently via `asyncio.gather`.
  - `wiswa/utils/github.py`: Removed duplicate API calls; security PUT requests and ruleset upsert
    operations now run in parallel.
  - `wiswa/utils/postprocess.py`: File cleanup operations and configuration file writes now run
    concurrently.

### Fixed

- GitHub expressions in workflow `run:` blocks moved to `env:` variables to prevent script injection
  (release, cleanup, publish-pypi, publish-luarocks workflows).
- `dict:update`, `format`, `check-formatting`, and `check-spelling` scripts are now included in
  `package.json` for all project types (previously only Python, C/C++, and TypeScript).
- QA workflow no longer generates an empty `changes` job for non-C/C++ project types.
- Cache and artifact cleanup for private projects is now a dedicated `cleanup.yml` workflow running
  on Linux instead of inline steps in PyInstaller, AppImage, Snap, and Flatpak workflows (fixes
  failures on Windows runners where `xargs` is unavailable).
- CodeQL workflow now filters by language-specific file extensions (`.py`/`.pyi` for Python,
  `.ts`/`.tsx`/`.js`/`.jsx` for TypeScript, C/C++ extensions for C/C++ and Xcode/Swift projects),
  so it only runs when relevant source files change. When `actions` is in the CodeQL languages
  array, workflow YAML files are also included in the path filters.
- `python_deps`, `using_django`, and `using_drf` in `defaults.libsonnet` are now guarded by
  `project_type == 'python'`, skipping unnecessary PyPI version lookups for non-Python project types.
- Coveralls steps in generated tests workflows now skip pull request events.
- Post-processing now sets `COREPACK_ENABLE_DOWNLOAD_PROMPT=0` in the environment for yarn
  subprocess calls, preventing Corepack from prompting interactively.
- `_setup_github_session` now catches `keyring.errors.NoKeyringError` and logs a warning instead of
  crashing, so environments without a keyring backend no longer produce a traceback.

## [0.0.1] - 2026-03-24

First version.

[unreleased]: https://github.com/Tatsh/wiswa/-/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/Tatsh/bascom/releases/tag/v0.0.1
