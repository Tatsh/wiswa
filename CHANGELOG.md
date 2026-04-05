<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `cspell_pre_commit_hook` setting (default `true`). When set to `false`, the cspell pre-commit
  hook is excluded from `.pre-commit-config.yaml`.
- Version age gating for PyPI and npm package version fetching:
  - PyPI version fetching now respects `exclude-newer` and `exclude-newer-package` from
    `~/.config/uv/uv.toml`, filtering out versions published after the configured cutoff.
  - npm version fetching now filters out versions published within the last 7 days, matching Yarn's
    `npmMinimalAgeGate` default.
- `npmMinimalAgeGate: 10080` to default yarnrc settings, enforcing a 7-day minimum age before new
  npm package versions are used.
- 7-day cooldown and `multi-ecosystem-groups` to default Dependabot configuration.
- `regenerate_yarn_lock` setting (default `true`). When enabled, `yarn.lock` is deleted before
  running Yarn during post-processing, ensuring a fresh lock file is generated.
- `export_requirements` setting that replaces the `saves_requirements_txt` boolean with a rich
  configuration object supporting all `uv export` options.
  - When enabled, a local pre-commit hook runs `uv export` (for uv projects) or the
    `poetry-plugin-export` hook is configured (for Poetry projects) to keep requirements in sync
    with the lock file.
  - Post-processing now runs `uv export` or `poetry export` when `export_requirements.enabled` is
    true.
  - `output_filename` automatically derives from `format` (e.g. `pylock.toml` format produces a
    `pylock.toml` filename).
  - `pylock*.toml` is now included in Prettier ignore patterns.
  - Backward-compatible alias `saves_requirements_txt` is preserved.
- Wiswa CLI progress uses `yaspin` on stderr with weighted random cli-spinners (dots-style
  animations are more likely than other styles), and shows a `Starting up.` message before
  long-running work begins.
- `clear_resolved_defaults_cache()` on `wiswa.mcp` and `clear_resolution_caches()` on
  `wiswa.utils.versions` for tests and long-lived processes that need fresh Jsonnet defaults or
  version-resolution caches.
- `CachedAsyncSession.cache_directory` and `CachedAsyncSession.expire_after_total_seconds`
  properties for cache introspection and testing.

### Deprecated

- `saves_requirements_txt` setting. Use `export_requirements` instead.

### Changed

- Coverage `omit` lists now include `**/*.j2` in this repository and in generated
  `pyproject.toml` defaults so Jinja templates are not measured as Python.
- Generated Sphinx `conf.py` now uses the standard-library `tomllib` module instead of `tomlkit`
  when the project's minimum Python version is 3.11 or higher. The `tomlkit` docs dependency is
  only included for projects that still support Python < 3.11.
- Expanded default Claude Code permissions in `defaults.libsonnet`: package manager commands (uv or
  Poetry based on `package_manager` setting), `cspell`/`markdownlint-cli2`/`prettier` yarn scripts,
  C/C++ tools (`cmake`, `clang-format`, `vcpkg`), `WebFetch` domains, and temp file
  read/write permissions. `gh` and `glab` API permissions are now conditional on platform settings.
- Dictionary update script now invokes `python` instead of `python3`.
- `get_github_release_latest_tag` no longer truncates action tags to the major version (e.g. `v7`
  instead of `v7.0.0`), returning full semver tags instead. This fixes compatibility with
  repositories like `astral-sh/setup-uv` that only publish immutable full version tags.
- Removed the `actions` parameter from `get_github_release_latest_tag`; the `not allow_suffixes`
  condition now drives the filtering behaviour previously gated by `actions`.
- Split QA workflows for all project types (Python, TypeScript, C/C++) into granular parallel jobs
  (ruff, mypy, format, eslint, prettier, markdownlint, spelling) using native GitHub Actions path
  filters instead of `dorny/paths-filter`. Only mypy uses a Python version matrix. The format job
  uses the minimum supported Python version.
- Added path filters to the TypeScript tests workflow.
- All publish workflows (NPM, PyPI, LuaRocks, WinGet) now wait for QA and test workflows to
  succeed before publishing.
- NPM and LuaRocks publish workflows now create a draft GitHub release.
- Python, TypeScript, and Lua projects now unconditionally get a release workflow that publishes the
  draft GitHub release after all workflows succeed.
- PyInstaller workflow template no longer excludes `windows-11-arm` from the build matrix based on
  the `niquests` dependency. Windows ARM64 builds are now always included for non-private projects.
- `uv lock` now runs with `--upgrade` during post-processing so all packages (including transitive
  dependencies) are resolved to their highest possible versions.
- Poetry commands now receive `--quiet` when debug mode is off, matching the existing behaviour for
  uv commands.
- British English spelling rules in generated templates (Copilot `general.instructions.md`,
  Cursor `general.mdc`, Claude `copy-editor.md`) are now conditional on the `cspell_language`
  setting. When `cspell_language` is `en-US`, en-GB rules are excluded. Cursor `general.mdc` was
  converted from a static file to a Jinja2 template, and `cspell_language` was added as a derived
  Jsonnet field.
- `gitlab_ci` in `defaults.libsonnet` now defaults to an empty object; `project.jsonnet` checks
  non-emptiness instead of using `std.objectHas`, so users no longer need to define `gitlab_ci` when
  `using_gitlab` is true.
- Relaxed minimum versions for `fastmcp` (3.2.0 to 3.1.1), `niquests` (3.18.3 to 3.18.2), and
  `ruff` (0.15.8 to 0.15.7).
- Regenerated template layout now uses `claude/`, `cursor/`, and `github/` segments under
  `wiswa/templates/` instead of dotted directories (`.claude`, `.cursor`, `.github`) in the template
  tree.
- Static AI language rules ship as Markdown under `wiswa/static/claude/rules/`; bundled Cursor
  `.mdc` rule copies under `wiswa/static/.cursor/rules/` are removed.
- Post-processing removes legacy Cursor rule and GitHub Copilot instruction paths from generated
  projects when consolidating on the new layout.
- `evaluate_merged_settings` now requires `-u` / `--user-defaults` on the `wiswa` CLI to load user
  Jsonnet defaults (defaults are off without the flag).
- Jsonnet defaults replace `want_claude` and `want_claude_agents` with `want_ai`, which gates
  `AGENTS.md`, `CLAUDE.md`, and the `.claude/` tree. Removed `want_copilot` and `want_cursor`; editor
  artefacts now follow the consolidated template layout.
- Added Jsonnet `uses_user_defaults` (default `false`) so generated `yarn regen` can opt into
  passing `-u` / `--user-defaults`.

### Fixed

- Release agent template no longer shows `uv lock` or `gen-manpage` steps for non-Python projects.
- Agent templates with conditional steps now use Markdown auto-numbering to avoid gaps.

- Templates that render to empty content now auto-delete the output file instead of writing a
  near-empty file, replacing the hardcoded `_CI_PLATFORM_AGENTS` filtering with template-driven
  conditional rendering.
- The `gitlab_ci` field is now optional when `using_gitlab` is true, preventing a crash when
  projects override `using_gitlab` without providing a `.gitlab-ci.yml` configuration.
- `get_npm_latest_package_version` now filters out unpublished npm versions (versions present in the
  registry `time` map but absent from the `versions` map), fixing incorrect version resolution for
  packages with unpublished versions such as `pyright-to-gitlab-ci`.
- Bundled Jsonnet defaults failed to load on Python 3.10 and 3.11 in the CLI and MCP server when
  `importlib.resources.as_file()` was used on the package directory (multiplexed path); resolution
  now anchors on `defaults.libsonnet` and uses its parent as the library path.

## [0.1.0] - 2026-03-27

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
- Explicit `permissions: { contents: 'read' }` to the LuaRocks and WinGet publish workflows,
  restricting the default `GITHUB_TOKEN` to read-only.
- MCP server (`wiswa-mcp`) that exposes settings discovery tools for AI assistants.
- `utils.libjsonnet` symlink for backwards compatibility.

### Changed

- Replaced `aiohttp` and `aiohttp-client-cache` with `niquests` as the HTTP client. The session
  module now implements its own filesystem-backed cache via `CachedAsyncSession`. HTTP/2 and HTTP/3
  are supported natively.
- urllib3 request logging now appears in debug mode. Noisy `urllib3.util.retry` messages are
  suppressed.
- Jsonnet evaluation now emits a debug log message.
- Legacy Poetry dependencies declared via `pyproject.tool.poetry.dependencies` and
  `pyproject.tool.poetry.group.*.dependencies` are now merged into `python_deps` at evaluation time,
  making `python_deps` the single source of truth for all dependency existence checks in templates
  and settings.
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
- Renamed `.libjsonnet` files to `.libsonnet`.
- `uv` is now invoked with `--quiet` when not in debug mode during post-processing.
- `license` field is now always included in generated `package.json`.

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
- Vcpkg setup in the PyInstaller workflow template now appends to `PKG_CONFIG_PATH`,
  `CMAKE_PREFIX_PATH`, `LIB`, and `INCLUDE` environment variables instead of overriding them,
  preserving existing values from Visual Studio and other tools.
- PyInstaller workflow template now excludes `windows-11-arm` from the build matrix when `niquests`
  is a main dependency, since niquests' dependency qh3 does not provide a non-free-threaded wheel
  for Windows ARM64.
- MacOS binaries are now signed before testing in PyInstaller workflow.

## [0.0.1] - 2026-03-24

First version.

[unreleased]: https://github.com/Tatsh/wiswa/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Tatsh/wiswa/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/Tatsh/wiswa/releases/tag/v0.0.1
