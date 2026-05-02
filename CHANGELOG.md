<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Generated TypeScript projects published on npm now include "NPM Version" and "NPM Downloads"
  badges in `README.md`, linking to the package page on npmjs.com. Private TypeScript projects do
  not get them.
- Generated TypeScript projects' Dependabot npm-ecosystem config now ignores `typescript` versions
  `>=6.0.0`, preventing Dependabot from opening PRs that bump TypeScript past major version 6.

### Fixed

- Generated `publish-*` workflows (`publish-pypi-any`, `publish-luarocks`, `publish-winget`,
  `publish-npm-any`) and the `release` workflow gate no longer treat freshly-queued tag-triggered
  workflows as "missing" and silently skip them. Watched workflows are split at template time into
  a required list (build artefacts plus user-supplied `release_gate_workflows`) that must register
  a run before the gate clears, and an optional list (`Prettier`, `QA`, `Spelling`,
  `markdownlint`, and `Tests` when applicable) that is master- or PR-triggered and is skipped
  silently when absent. Previously, when GitHub's API had not yet indexed the freshly-queued runs
  on a tag push, the gate could exit on its first iteration and let `pypa/gh-action-pypi-publish`
  upload a wheel before the build matrix had finished.
- Workflow names with spaces or shell metacharacters (for example `Windows Installer (NSIS)`) now
  round-trip through the gate scripts intact: the bash uses real arrays with `"${arr[@]}"`
  instead of word-splitting a space-delimited string.
- The `process_workflow` helper returns code `2` to signal "pending". Under GitHub Actions' default
  `bash -e` shells, that non-zero return previously aborted the gate script before the caller could
  inspect `$?`, so the loop exited with code 2 instead of retrying. Each call site now uses the
  `rc=0; cmd || rc=$?` idiom so the helper's return code is captured without tripping `errexit`.
- Generated `publish-winget` workflow skips the `update-winget` job (with a workflow warning)
  when the `WINGET_TOKEN` secret is empty, instead of failing the job. Because GitHub Actions
  does not permit `secrets.X` references in a job-level `if`, the `check` job now reads
  `WINGET_TOKEN` into an environment variable, exposes its presence as a `has_winget_token`
  output, and `update-winget` gates on that output.
- Generated `CHANGELOG.md` and `.claude/agents/changelog.md` no longer link to a 404 Keep a
  Changelog URL: the resolved `keepachangelog.com/en/<tag>/` URL is HEAD-verified before being
  emitted (falling back to `1.1.0/` when the tag-derived page is not published), and the Claude
  changelog agent template now consumes the resolved URL instead of a hardcoded literal.

## [0.3.1] - 2026-04-27

### Changed

- `node_engine` now defaults to an empty string. Generated projects no longer carry a `>=20.0`
  Node-engine constraint by default, and the npm version resolver skips Node-engine filtering
  unless a project sets `node_engine` explicitly.

## [0.3.0] - 2026-04-27

### Added

- After a successful run, Wiswa records a `_wiswa` block in the generated `package.json` with the
  invocation `commandLine`, the UTC `lastRun` timestamp, and the `version` of Wiswa that produced
  the file. The version is the seven-character commit SHA (suffixed `-dirty` when the working
  tree has uncommitted changes) when Wiswa runs from a source checkout, otherwise the installed
  package version reported by `importlib.metadata`.
- `wiswa_tag` setting (default `true`) controls whether the `_wiswa` block is written. Setting it
  to `false` removes the block from `package.json` on the next run.

## [0.2.3] - 2026-04-26

### Changed

- `tomlkit` is no longer added to default docs dependencies for Python projects below 3.11 when
  the project already lists `tomlkit` in its main dependencies.
- `latestPypiPackageVersion` (and the caret/ge/tilde wrappers) now read the project's
  `pyproject.toml` `[tool.uv]` section in addition to the user-level `uv.toml`, with project
  values overriding user values. This matches uv's own precedence so per-project overrides take
  effect during Wiswa runs.

### Fixed

- `[tool.uv.exclude-newer-package].<package> = false` now correctly exempts that package from any
  global `exclude-newer` cutoff during PyPI version resolution. Previously this entry was
  ignored, so the global cutoff still filtered out releases of the named package.

### Removed

- `docutils<0.22` constraint and `numpydoc` from default docs dependencies.
- `engines.node` field from generated `package.json` files.

## [0.2.2] - 2026-04-23

### Added

- `get_pypi_latest_package_version` accepts a `host` parameter (default `'pypi.org'`) for querying
  private or alternative PyPI-compatible registries.
- `get_pypi_latest_package_version` accepts a `python` parameter for filtering releases by
  `requires_python` compatibility using `packaging.specifiers.SpecifierSet`.
- Jsonnet `latestPypiPackageVersion`, `latestPypiPackageVersionCaret`,
  `latestPypiPackageVersionGe`, and `latestPypiPackageVersionTilde` accept optional `host` and
  `python` parameters.

### Changed

- Generated `eslint.config.mjs` uses `tseslint.config()` with spread syntax instead of
  `defineConfig()` with `globalIgnores()` and `.concat()`.
- Default `tsconfig.json` for generated TypeScript projects removes `baseUrl: 'src'` from
  `compilerOptions` and changes `moduleResolution` from `'node'` to `'bundler'`.
- `get_pypi_latest_package_version` uses the PyPI JSON API (`/pypi/<package>/json`) instead of the
  RSS feed, removing the `beautifulsoup4` and `lxml` runtime dependencies.
- README badge for GitHub Pages now uses the GitHub API to detect whether Pages deploys from a
  branch or GitHub Actions. Legacy deploys render the built-in `pages-build-deployment` badge;
  workflow deploys scan `.github/workflows/*.yml` for `actions/deploy-pages` and render that
  workflow's badge. Previously it always rendered a `pages.yml` badge.

### Fixed

- QA badge is no longer rendered in the README when `.github/workflows/qa.yml` does not exist
  (e.g. C++ projects that use `clang-format.yml` instead).
- Generated PyPI publish workflow no longer gates on the Tests workflow for `stubs_only` packages,
  which do not have tests.
- Hatchling sdist `include` now adds `man` when `want_man` is true, so generated sdists for
  uv/Hatchling projects include man pages (previously only Poetry-based projects included them).

### Removed

- `beautifulsoup4` and `lxml` runtime dependencies.

## [0.2.1] - 2026-04-18

### Added

- GitLab remote project setup (`python-gitlab`): Jsonnet defaults live in `defaults/gitlab.libsonnet`
  and merge with `gitlab+:` overrides; `using_gitlab` detects GitLab hosts from `repository_uri`.
- CLI `--skip-remote` to skip GitHub or GitLab API configuration (replaces `--skip-github` /
  `--skip-gitlab`).
- Host-scoped keyring services for API tokens: `wiswa-github:<hostname>` and
  `wiswa-gitlab:<hostname>`; documented in README and `docs/remote-api-tokens.rst`.
- `RemoteHostConflictError` when merged settings set both `using_github` and `using_gitlab`.
- `package_sources` entries may set `publish-url` (or Jsonnet `publish_url`) for uv projects;
  Wiswa copies them into `[[tool.uv.index]]` for `uv publish` alongside the PEP 503 `url`.
- Jsonnet `primary_module_qualified` (defaults to `primary_module`): full dotted import path for the
  on-disk package, with `primary_module` as the namespace root when they differ.
- Jsonnet `utils.moduleImportToPath` for turning dotted import names into POSIX path segments.
- VS Code default `files.associations` mapping `*.json.dist` to the JSON language id.
- Jsonnet `sphinx_fail_on_warning` (default `true`): controls ReadTheDocs `sphinx.fail_on_warning`
  in generated configs, and is exposed on `Settings`.
- README template marks the generated badge block with `<!-- WISWA-GENERATED-README:START -->` and
  `<!-- WISWA-GENERATED-README:STOP -->` so post-processing replaces only that region.
- Sphinx library docs include a `wiswa.mcp` API page (`docs/library/mcp.rst`) linked from the
  library toctree.
- Sphinx `conf.py` intersphinx mappings for Jinja2, niquests, and niquests-cache (alongside the
  Python mapping).
- GitLab project badge management via the Badge API during remote setup (`wiswa` without
  `--skip-remote`). Wiswa creates and updates project badges (QA pipeline, Coverage, Latest Release,
  and tool badges like mypy, uv, Ruff, pytest, pre-commit, and Prettier) on GitLab projects.
  Duplicates are avoided by matching on badge name; user-added badges with different names are
  preserved.

### Changed

- Jsonnet GitLab defaults no longer force `container_registry_access_level: 'disabled'`; project
  setup now relies on the GitLab server default when applying remote settings.
- Generated `yarn gen-docs` and `yarn gen-manpage` scripts always include
  `sphinx-build --fail-on-warning`, regardless of `sphinx_fail_on_warning`; ReadTheDocs
  `sphinx.fail_on_warning` still follows that flag.
- GitHub API error handling during repository setup is improved: each failed step logs a short,
  readable warning (HTTP status plus body or GitHub's JSON `message` when available, without a
  traceback), and the rest of the setup still runs instead of stopping at the first error.
- GitHub Actions workflows that attach draft releases (AppImage, Flatpak, PyInstaller, publish, Snap)
  pin `softprops/action-gh-release` to v3.0.0.
- CONTRIBUTING explains that `man/wiswa.1` and other `man/` output must come from `yarn gen-manpage`,
  not manual edits.
- Bundled `.claude/rules/python.md` is emitted from
  `wiswa/templates/claude/rules/python.md.j2` instead of `wiswa/static/claude/rules/python.md`;
  YAPF-related bullets follow `want_yapf`, and the rule is still omitted for stubs-only or
  non-Python projects.
- CLI: `wiswa` command help shows a single-line imperative summary instead of a multi-line
  description with a `Raises` section (Click command docstrings stay one line).
- Generated Flatpak workflow names the bundle, GitHub Actions artifact, attestation subject, and
  draft release attachment as `{flathub}-{version}-{arch}.flatpak`, using the Flathub app id
  (`publishing.flathub`) as-is, with `version` from `pyproject.toml`, instead of a single
  `{project_name}.flatpak` for every arch and build.
- Generated Flatpak workflow `push.paths` includes the Flatpak manifest (`{flathub}.yml`) so edits to
  the manifest trigger CI without touching Python sources.
- Default Jekyll `pages_config` excludes `CHANGELOG.md` so GitHub Pages does not treat it as site
  content; merge with `exclude+:` still appends project-specific paths.
- Default `modules` uses `primary_module_qualified` so packaging and CI path filters follow the real
  package tree; workflow `paths` globs use slashes, not dots.
- Hatch defaults: `sdist` `include` lists unique top-level package directories (for example `aps`,
  plus `tests` when enabled); `wheel` `packages` use filesystem paths, and namespace-style projects
  (`primary_module_qualified` != `primary_module` with a dotted qualified name) list only those
  top-level directories in `packages` (for example `["aps"]`).
- Commitizen `remove_path_prefixes` and `__init__.py` `version_files` entries use the qualified
  package path; generated coverage and Ruff paths target `__main__.py` and `main.py` under that
  tree.
- Wiswa places templated `__init__.py`, `py.typed`, and static `main.py` / `__main__.py` under
  `primary_module_qualified`; post-processing picks the man page stem from the last segment of the
  qualified name.
- Generated Claude agent docs, the CI skill template, Sphinx `index.rst`, and `tests/test_main.py`
  use the qualified name for imports and slash-separated paths for directories.
- CLI: without `--debug`, failures end with a short message and `click.Abort` raised with
  `from None` so Python does not print chained exception context or a full traceback; with
  `--debug`, the original exception is re-raised for a normal traceback.
- Jsonnet merge with `uses_user_defaults: true` treats a missing user-level `defaults.jsonnet` as an
  empty object instead of failing with `FileNotFoundError`.
- README and Sphinx docs recommend a global Wiswa install (`uv tool` or `pipx`) or adding Wiswa as
  a project development dependency.
- Generated README and Sphinx `docs/badges.rst` badge order and shields match post-processing:
  Dependabot after CI badges; `want_codeql`, `want_tests`, and privacy flags gate CodeQL, Tests, and
  Coveralls; documentation badge honours `want_docs`; Python badges include uv/Poetry, optional
  PyPI badges for common dependencies, pytest when tests are enabled and not stubs-only, Ruff,
  Downloads, Stargazers, `pre-commit`, and Prettier; custom project badges list negative priority
  entries first.
- Post-process README Python badges: removed pydocstyle; pytest, `pre-commit`, and Prettier shields
  match the Sphinx templates (including label text and targets).
- Ruff `COM812` rule is now always included in the ignore list for Python projects, instead of being
  conditional on `want_yapf`. The rule conflicts with formatters regardless of which formatter is
  used.
- Wiswa CLI progress spinner now uses `rich.status.Status` on a `rich.console.Console` bound to
  stderr instead of `yaspin`; spinner names come from `rich.spinner.SPINNERS`, keeping the
  weighted random dots-heavy pool. `yaspin` is no longer a runtime dependency.
- Generated Publish workflow's wait-for-workflows step and Release workflow's gate step treat gating
  workflows as optional: a missing run for the commit (for example because the workflow's `on:`
  filters exclude tag pushes) or a `skipped` / `neutral` conclusion is no longer waited on; the
  loop still fails fast on `failure`, `cancelled`, `timed_out`, `startup_failure`, or
  `action_required`, and only genuinely in-progress runs are waited on. This fixes the Publish job
  timing out after 30 minutes when gating workflows do not run for tag pushes.
- Generated Release workflow always runs its body, records the `workflow_run` trigger decision in
  a `guard` step output, deletes prior Release runs on the same commit that concluded `skipped`,
  `cancelled`, or `neutral`, and self-cancels when it did not publish so a later invocation
  removes it. This keeps the release history free of non-publishing runs without requiring manual
  cleanup.
- Wiswa CLI progress now renders a full live display instead of a single spinner line when stderr
  is a TTY (or `WISWA_PROGRESS=1` is set) and neither `--debug` nor `--quiet` is passed:
  - A bold NFO-style block-letter `wiswa` banner drawn with Unicode box characters
    (`█`, `║`, `╗`, and similar), using the terminal's default foreground colour so it reads on
    both light and dark backgrounds.
  - The project URL `https://github.com/Tatsh/wiswa` right-aligned beneath the banner.
  - A seven-task checklist using Unicode ballot boxes: `☐` for pending or running tasks, green
    `☑` for completed tasks, and dim strike-through `☒` for skipped tasks. The tasks are
    evaluate settings, evaluate project, write templated files, download Yarn, copy static files,
    post-process, and configure remote.
  - A spinner line below the checklist that shows the latest status message (for example,
    ``Running `yarn install` ...``).
  - `--quiet`, `--debug`, and the `WISWA_PROGRESS=1` override keep their existing behaviour: the
    display is disabled when stderr is not a TTY (unless `WISWA_PROGRESS=1` is set), when
    `--debug` is used, or when `--quiet` is passed.

### Removed

- Jsonnet `using_beads` and the optional Beads issue-tracker section in generated `AGENTS.md`.
- Jsonnet `primary_module_implicit_namespace`; namespace-style layout is inferred when
  `primary_module_qualified` differs from `primary_module` and contains a dot (documented on
  `primary_module` and `primary_module_qualified`).
- `pyright` script from generated `package.json` for Python projects; `want_pyright` no longer adds
  a `pyright: 'yarn pyright'` entry. The `want_ty` conditional remains.
- Unused runtime dependency `aiofiles`.
- Pydocstyle badge from generated README and Sphinx HTML badge lists.

### Fixed

- Post-processing `_subprocess_log_run` no longer expects an extra positional argv tuple after
  `cmd`; callers pass the executable and arguments only in `cmd`, fixing an `IndexError`
  during uv, Poetry, ruff, Prettier, and related subprocess steps.
- Post-processing emits Prettier `format` / `check-formatting` commands with `--ignore-unknown`
  before the path (and an explicit `.` target) when rewriting `package.json` after dropping YAPF.
- CLI: handle `click.Abort` before `RuntimeError` in the async main path (`click.Abort` subclasses
  `RuntimeError`, so aborts were previously treated as runtime failures).
- Pytest autouse fixture `recover_stale_process_cwd` resets the process working directory when it
  no longer exists (fixing `FileNotFoundError` from `monkeypatch.chdir` under aggressive `tmp_path`
  retention). Included in this repository and in the generated `tests/conftest.py` template.
- `docs/badges.rst` template no longer inserts an extra blank line between `.. image::` blocks when
  optional badges are omitted (for example private projects without Downloads or Stargazers).
- `docs/badges.rst` template no longer stacks extra blank lines before Bluesky/Mastodon badges: the
  second custom-badge loop uses `{% endfor -%}`, the spare newline after Prettier is removed, and the
  blank line between Bluesky and Mastodon `{% if %}` blocks is dropped so spacing matches other
  badges.
- Flatpak manifest: use `build-options.build-args: ['--share=network']` so `flatpak-builder` allows
  PyPI during the module build (the `network: true` key is not a valid `BuilderOptions` field and
  was ignored). Uv projects install uv with `pip3 install --prefix=/app uv`, then run
  `/app/bin/uv pip install --prefix=/app .` (a bare `pip3 install uv` targets the user site and
  breaks `python3 -m uv` under the SDK). Poetry projects use `pip3 install --prefix=/app .`.
- Jsonnet always emits `tool.hatch.build.targets` for uv-managed projects. It was previously skipped
  when `primary_module` matched the hyphen-normalised `project_name` (for example `yapf-gitlab` →
  `yapf_gitlab`), so only `stubs_only` or a customised `primary_module` received Hatch sdist/wheel
  settings.

## [0.2.0] - 2026-04-06

### Added

- Post-processing restores `uv.lock` from `HEAD` when it is the only path differing from the last
  commit (for example after `uv lock --upgrade` without any tracked manifest edit). This avoids
  noisy lock-only diffs from ambient resolution (rolling `exclude-newer` cutoffs, index churn, and
  similar).
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
  - Backward-compatible alias `saves_requirements_txt` is preserved.
- Wiswa CLI progress uses `yaspin` on stderr with weighted random CLI spinners (dots-style
  animations are more likely than other styles), shows a `Starting up.` message before long-running
  work, ends progress labels with ellipses, and shows post-processing subprocess commands in the
  progress line (shell command in backticks with a trailing ellipsis).
- `clear_resolved_defaults_cache()` on `wiswa.mcp` and `clear_resolution_caches()` on
  `wiswa.utils.versions` for tests and long-lived processes that need fresh Jsonnet defaults or
  version-resolution caches.
- With `--skip-postprocess`, Python projects still apply the same `pyproject.toml` and
  `package.json` manifest edits as full post-processing (including pruning empty nested tables) so
  Jsonnet output does not leave empty `[tool]` sections.
- Python: skip generating `tests/test_main.py` when `tests/` already contains other `test_*.py`
  files (existing projects keep their own test layout).
- Jsonnet `using_beads` (default `false`) for Beads-related defaults.
- Post-processing rewrites existing `CHANGELOG.md` boilerplate links from GitHub when an HTTP
  session is available: Keep a Changelog uses the latest `olivierlacan/keep-a-changelog` release tag
  mapped to `keepachangelog.com/en/...`, and Semantic Versioning uses `semver/semver` mapped to
  `semver.org/spec/...`. Pinned fallbacks are `https://keepachangelog.com/en/1.1.1/` and
  `https://semver.org/spec/v2.0.0.html` when there is no session or resolution fails.
- New projects receive the same resolved Keep a Changelog and SemVer intro URLs when templates are
  rendered (`resolve_changelog_boilerplate_urls`), not only after post-processing.
- The Markdown Claude rule ships from `wiswa/templates/claude/rules/markdown.md.j2` instead of a
  static file under `wiswa/static/claude/rules/`. The GitHub Pages (Jekyll) / Liquid bullet is
  emitted only when `using_github` is true.
- Template output uses a shared `_write_rendered_template` coroutine so empty renders delete the
  target path consistently; Python-only Claude agent templates no longer use `continue` when
  skipping non-Python projects.
- Coverage `omit` lists now include `**/*.j2` in generated `pyproject.toml` defaults so Jinja
  templates are not measured as Python.
- Generated Sphinx `conf.py` now uses the standard-library `tomllib` module instead of `tomlkit`
  when the project's minimum Python version is 3.11 or higher. The `tomlkit` docs dependency is only
  included for projects that still support Python < 3.11.
- Expanded default Claude Code permissions in `defaults.libsonnet`: package manager commands (uv or
  Poetry based on `package_manager` setting), `cspell` / `markdownlint-cli2` / `prettier` yarn
  scripts, C/C++ tools (`cmake`, `clang-format`, `vcpkg`), `WebFetch` domains, and temp file
  read/write permissions. `gh` and `glab` API permissions are now conditional on platform settings.
- `get_github_release_latest_tag` writes successful tag results to a JSON file under the Wiswa user
  cache directory (via `platformdirs`) and falls back to that file when the GitHub API returns HTTP
  403 or 429 (for example rate limits without a token). Persistence failures are logged at debug
  level and do not block resolution.
- New runtime dependency: `platformdirs`.
- Split QA workflows for all project types (Python, TypeScript, C/C++) into granular parallel jobs
  (ruff, mypy, format, eslint, prettier, markdownlint, and spelling) using native GitHub Actions
  path filters instead of `dorny/paths-filter`.
- Path filters on the TypeScript tests workflow.
- Publish workflows (NPM, PyPI, LuaRocks, WinGet) wait for QA and test workflows to succeed before
  publishing.
- NPM and LuaRocks publish workflows create a draft GitHub release.
- Python, TypeScript, and Lua projects get a release workflow that publishes the draft GitHub
  release after all workflows succeed.
- `uv lock` runs with `--upgrade` during post-processing so all packages (including transitive
  dependencies) are resolved to their highest possible versions.
- British English spelling rules in generated templates (Copilot `general.instructions.md`, Cursor
  `general.mdc`, Claude `copy-editor.md`) are conditional on the `cspell_language` setting. When
  `cspell_language` is `en-US`, en-GB rules are excluded. Cursor `general.mdc` is a Jinja2
  template, and `cspell_language` is a derived Jsonnet field.
- `gitlab_ci` in `defaults.libsonnet` defaults to an empty object; `project.jsonnet` checks
  non-emptiness instead of using `std.objectHas`, so users do not need to define `gitlab_ci` when
  `using_gitlab` is true.
- Regenerated template layout uses `claude/`, `cursor/`, and `github/` segments under
  `wiswa/templates/` instead of dotted directories (`.claude`, `.cursor`, `.github`) in the
  template tree.
- Static AI language rules ship as Markdown under `wiswa/static/claude/rules/`; bundled Cursor
  `.mdc` rule copies under `wiswa/static/.cursor/rules/` are removed.
- Post-processing removes legacy Cursor rule and GitHub Copilot instruction paths from generated
  projects when consolidating on the new layout.
- Jsonnet `uses_user_defaults` (default `false`); user-level `defaults.jsonnet` merges when the
  project file contains the literal `uses_user_defaults: true`.

### Deprecated

- `saves_requirements_txt` setting. Use `export_requirements` instead.

### Removed

- `-u` / `--user-defaults` CLI flags. User-level `defaults.jsonnet` merges when `.wiswa.jsonnet`
  contains the literal `uses_user_defaults: true` (regex scan, then Jsonnet evaluation). Enabling
  that behaviour only inside user `defaults.jsonnet`, without the literal in the project file, is
  not supported.

### Changed

- Generated VS Code extension defaults for Python: uv projects recommend
  `ms-python.vscode-python-envs` instead of `donjayamanne.python-environment-manager`; Poetry
  projects keep the environment manager and Poetry extensions and list
  `ms-python.vscode-python-envs` under `unwantedRecommendations` only in that layout.
- Wiswa raises the `fastmcp` dependency floor to `>=3.2.0`.
- `npmMinimalAgeGate` for npm registry fetches and for GitHub `githubLatestReleaseTag` age filtering
  now resolves in order: merged settings `yarnrc.npmMinimalAgeGate`, a numeric `npmMinimalAgeGate`
  field in `.wiswa.jsonnet`, repository then home `.yarnrc.yml`, `~/.npmrc` (`min-release-age` in
  days), then the 10080-minute default. Jsonnet natives use the merge-aware and snippet-aware value.
- Jsonnet defaults replace `want_claude` and `want_claude_agents` with `want_ai`, which gates
  `AGENTS.md`, `CLAUDE.md`, and the `.claude/` tree. Removed `want_copilot` and `want_cursor`;
  editor artefacts follow the consolidated template layout.
- CLI `--skip-jsonnet` help text: it skips only `project.jsonnet` manifest output; evaluating merged
  settings from `.wiswa.jsonnet` still runs Jsonnet (0.1.0 help said `Skip Jsonnet evaluation.`).
- Default `github_username` in shipped Jsonnet defaults resolves from the GitHub CLI (`gh`) when
  authenticated, then from `remote.origin.url` in `.git/config` for GitHub remotes, before falling
  back to `unknown` (0.1.0 shipped a static `unknown` default).
  - `remote.origin.url` values are trimmed, and whitespace-only values are ignored.
  - Duplicate git `config` paths reached via worktree layout (for example when `commondir` is `.`)
    are de-duplicated after `Path.resolve()`.
- `--quiet` (`-q`) suppresses the final `Done.` line as well as the progress spinner; `--help` and
  the man page describe this behaviour. Post-processing passes `--quiet` through to Ruff when not in
  debug mode, Yarn install and format capture subprocess stdout/stderr, and failed command errors
  use the shell command string.
- `get_github_release_latest_tag` no longer truncates action tags to the major version (e.g. `v7`
  instead of `v7.0.0`), returning full semver tags instead. This fixes compatibility with
  repositories like `astral-sh/setup-uv` that only publish immutable full version tags.
- Version resolution reads uv's user `uv.toml` via `platformdirs.user_config_path('uv')` instead of
  assuming `~/.config` on all platforms. The HTTP session cache and user `defaults.jsonnet` paths
  use `platformdirs` with application name `wiswa` and `appauthor=False`.
- PyInstaller workflow template no longer excludes `windows-11-arm` from the build matrix based on
  the `niquests` dependency. Windows ARM64 builds are always included for non-private projects.
- Poetry commands receive `--quiet` when debug mode is off, matching uv commands.
- Post-processing still runs root `yarn` install before other Yarn steps, then runs concurrently:
  legacy AI artefact cleanup, Prettier then markdownlint-cli2 (sequential inside one task), language
  format (YAPF or Ruff, or clang-format), `yarn dict:update`, and incidental `uv.lock` revert when
  applicable. After the project-type step, README badge refresh and changelog link refresh still run
  concurrently.
- C/C++ post-processing expands glob tokens in `clang_format_args` on disk before invoking
  `clang-format` (no shell). Restoring `uv.lock` from `HEAD` when it is the only drift now logs at
  debug level.
- Post-processing also restores `uv.lock` from `HEAD` when other tracked paths differ, if
  `git diff --no-color -a HEAD -- uv.lock` changes only the `exclude-newer` line under `[options]`
  (for example a rolling cut-off in user `uv.toml` alongside real template edits). The same `HEAD`
  baseline is used as `git restore --source=HEAD`; untracked files no longer block this step, and
  the previous working-tree-vs-index diff could be empty after staging.
- Generated `package.json` scripts, workflow templates, and agent instructions prefer long-form CLI
  flags (Prettier, YAPF, clang-format, GitHub CLI, Sphinx, npm global installs, Poetry export, and
  related tools) where applicable.
- Jsonnet defaults no longer define `copilot.intro`; generated `AGENTS.md` drops the optional
  Overview section from that field.
- Regen agent no longer requires a `copilot` key in `.wiswa.jsonnet`.

### Fixed

- With `cspell_pre_commit_hook` false, Jsonnet defaults no longer append an empty pre-commit
  repository stanza or keep `cspell` in `ci.skip`; the cspell hook and skip entry are fully
  omitted.
- Incidental `uv.lock` restore from `HEAD` runs `git restore` / `git checkout` with `core.hooksPath`
  set to the null device so pre-commit and other hooks cannot fail the operation (for example when
  `.pre-commit-config.yaml` is unstaged).
- Templates that render to empty content now auto-delete the output file instead of writing a
  near-empty file, using template-driven conditional rendering instead of hardcoded filtering.
- The `gitlab_ci` field is now optional when `using_gitlab` is true, preventing a crash when
  projects override `using_gitlab` without providing a `.gitlab-ci.yml` configuration.
- `get_npm_latest_package_version` now filters out unpublished npm versions (versions present in the
  registry `time` map but absent from the `versions` map), fixing incorrect version resolution for
  packages with unpublished versions such as `pyright-to-gitlab-ci`.
- Bundled Jsonnet defaults failed to load on Python 3.10 and 3.11 in the CLI and MCP server when
  `importlib.resources.as_file()` was used on the package directory (multiplexed path); resolution
  now anchors on `defaults.libsonnet` and uses its parent as the library path.
- PyInstaller workflow passes `--collect-data yaspin` so frozen binaries bundle `yaspin` package
  data (for example `spinners.json`).
- Regen agent template splits Jinja branches so a closing `endif` directive is not emitted
  immediately before Markdown code fences when `trim_blocks` is enabled, fixing broken shell blocks
  after regen.

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

[unreleased]: https://github.com/Tatsh/wiswa/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/Tatsh/wiswa/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/Tatsh/wiswa/compare/v0.2.3...v0.3.0
[0.2.3]: https://github.com/Tatsh/wiswa/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/Tatsh/wiswa/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Tatsh/wiswa/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Tatsh/wiswa/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Tatsh/wiswa/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/Tatsh/wiswa/releases/tag/v0.0.1
