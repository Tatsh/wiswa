local package = import 'defaults/package.libsonnet';
local pre_commit_configs = {
  cff: [import 'defaults/pre-commit-config/cff.libsonnet'],
  github: [import 'defaults/pre-commit-config/github.libsonnet'],
};
local python_deps = import 'defaults/python-deps.libsonnet';
local vscode_settings = import 'defaults/vscode/settings.libsonnet';
local utils = import 'utils.libsonnet';

/**
 * @brief Default settings for project generation.
 * @file defaults.libsonnet
 * @namespace defaults
 */
{
  local default_deps = python_deps(
    self.want_main,
    self.want_yapf,
    self.stubs_only,
    self.project_name,
    self.want_coveralls,
    self.want_sqlfluff,
    self.supported_python_versions[0],
  ),
  local is_uv = self.package_manager == 'uv',
  local github = if settings.using_github then pre_commit_configs.github else [],
  local cff = if settings.want_cff then pre_commit_configs.cff else [],
  local local_hooks = import 'defaults/pre-commit-config/local.libsonnet',
  local cspell_hooks = if settings.cspell_pre_commit_hook then [import 'defaults/pre-commit-config/cspell.libsonnet'] else [],
  local rtd = import 'defaults/readthedocs.libsonnet',
  local settings = self,

  /** @brief Package manager. Valid values: poetry, uv. */
  package_manager: 'uv',
  /**
   * @brief Custom package index sources.
   *
   * Each entry is an object with ``name``, ``url``, and optional ``priority`` fields.
   * Translated to ``[[tool.poetry.source]]`` for Poetry or ``[[tool.uv.index]]`` for uv.
   * Entries without a ``url`` (e.g. ``{name: 'PyPI', priority: 'primary'}``) are kept for
   * Poetry but omitted for uv.
   * @var object[]
   */
  package_sources: [],
  /** @brief Project type. Valid values: python, typescript, xcode, c, c++, generic. */
  project_type: 'python',
  /**
   * @brief Yarn version to use.
   * @var string
   */
  yarn_version: utils.latestYarnVersion(),
  /** @brief License. */
  license: 'MIT',
  /** @brief Version. */
  version: '0.0.0',
  /** @brief If the project should not ignore the `/dist/` directory. */
  keep_dist: false,
  /**
   * @brief If the project is published on PyPI.
   * @var boolean
   */
  using_pypi: self.project_type == 'python',
  /**
   * @brief Configuration for exporting requirements from the lock file.
   *
   * When ``enabled`` is true a pre-commit hook is added (local ``uv export``
   * for uv, ``poetry-plugin-export`` for Poetry) and the export runs during
   * post-processing. All fields map directly to ``uv export`` flags;
   * Poetry-only equivalents are translated automatically.
   */
  export_requirements: {
    /** @brief Whether to run the export step and add a pre-commit hook. */
    enabled: false,
    /** @brief Output format (``requirements.txt``, ``pylock.toml``, ``cyclonedx1.5``). */
    format: 'requirements.txt',
    /** @brief Path to write the exported file. Derived from ``format`` when not overridden. */
    output_filename: if self.format == 'pylock.toml' then 'pylock.toml'
    else if self.format == 'cyclonedx1.5' then 'cyclonedx.json'
    else 'requirements.txt',
    /** @brief Include all optional dependencies. */
    all_extras: false,
    /** @brief Include dependencies from all dependency groups. */
    all_groups: false,
    /** @brief Export the entire workspace. */
    all_packages: false,
    /** @brief Include optional dependencies from these extra names. */
    extra: [],
    /** @brief Do not update the lock file before exporting. */
    frozen: false,
    /** @brief Include dependencies from these dependency groups. */
    group: [],
    /** @brief Assert that the lock file will remain unchanged. */
    locked: false,
    /** @brief Exclude comment annotations indicating the source of each package. */
    no_annotate: false,
    /** @brief Ignore the default dependency groups. */
    no_default_groups: false,
    /** @brief Disable the development dependency group. */
    no_dev: false,
    /** @brief Export editable dependencies as non-editable. */
    no_editable: false,
    /** @brief Do not include local path dependencies. */
    no_emit_local: false,
    /** @brief Do not emit these packages. */
    no_emit_package: [],
    /** @brief Do not emit the current project. */
    no_emit_project: true,
    /** @brief Do not emit any workspace members. */
    no_emit_workspace: false,
    /** @brief Exclude these optional dependencies when ``all_extras`` is set. */
    no_extra: [],
    /** @brief Disable these dependency groups. */
    no_group: [],
    /** @brief Omit hashes in the generated output. */
    no_hashes: false,
    /** @brief Exclude the comment header. */
    no_header: false,
    /** @brief Only include the development dependency group. */
    only_dev: false,
    /** @brief Only include dependencies from these groups. */
    only_group: [],
    /** @brief Export dependencies for these specific workspace packages. */
    package: [],
    /** @brief Prune these packages from the dependency tree. */
    prune: [],
    /** @brief Export dependencies for a PEP 723 script instead of the project. */
    script: '',
    /** @brief Include hashes (default true; set to false to pass --no-hashes). */
    with_hashes: true,
  },
  /** @brief Backward-compatible alias for ``export_requirements.enabled``. */
  saves_requirements_txt: self.export_requirements.enabled,
  /** @brief If the project is private (not published). */
  private: false,
  /**
   * @brief Supported platforms for the project, "all", string, or an array of strings.
   *
   * Values: "windows", "linux", "macos", "ios", "all".
   */
  supported_platforms: 'all',

  /**
   * @brief GitHub username (``gh`` when logged in, else owner from ``remote.origin`` in
   * ``.git/config``, else ``unknown``).
   */
  github_username: utils.githubCliUsername(),
  /**
   * @brief Project name on GitHub.
   * @var string
   */
  github_project_name: std.strReplace(std.strReplace(self.project_name, '@', ''), '/', '-'),
  /** @brief Default Git branch name (on the hosting provider). */
  default_branch: 'master',
  /**
   * @brief HTML repository URI of the hosting provider.
   * @var URL
   */
  repository_uri: utils.gitHubRepositoryUri(self.github.username, self.github_project_name),
  /**
   * @brief Documentation URI.
   * @var URL
   */
  documentation_uri: utils.readTheDocsUri(self.github_project_name),
  /**
   * @brief Directory name (generally what `git` would clone to without a specified output
   * directory).
   * @var string
   */
  directory_name: std.strReplace(std.strReplace(self.project_name, '@', ''), '/', '-'),
  /**
   * @brief Homepage URI. Defaults to GitHub Pages.
   * @var URL
   */
  homepage: self.github.pages_uri,
  /**
   * These keywords are used to set the `keywords` field in `pyproject.toml` and the `keywords`
   * field in `package.json`. They are also used to set the keywords for a project on GitHub.
   * @brief Project keywords.
   * @var string[]
   */
  keywords: [],
  /** @brief Project description. */
  description: 'No description.',
  /**
   * @brief Array of modules (Python packages) in the project.
   * @var string[]
   */
  modules: [self.primary_module_qualified],
  /** @brief PyInstaller configuration. */
  pyinstaller: {
    /**
     * @brief Extra arguments to PyInstaller. Arguments will not be escaped.
     * @var string[]
     */
    extra_args: [],
    /**
     * @brief Array of script names to exclude from macOS.
     * @var string[]
     */
    macos_exclusions: [],
    /**
     * @brief Array of script names to exclude from Windows.
     * @var string[]
     */
    windows_exclusions: [],
    /**
     * @brief If non-empty, only build these script names (overrides exclusions).
     * @var string[]
     */
    include_only: [],
    /**
     * @brief Packages to pass as `--collect-data` arguments.
     * @var string[]
     */
    collect_data: [],
    /**
     * @brief Packages to pass as `--collect-submodules` arguments.
     * @var string[]
     */
    collect_submodules: [],
    /**
     * @brief Packages to pass as `--copy-metadata` arguments.
     * @var string[]
     */
    copy_metadata: [],
    /**
     * @brief Modules to pass as `--hidden-import` arguments.
     * @var string[]
     */
    hidden_imports: ['colorlog'],
    /**
     * @brief Extra test commands to run on each built binary (e.g. subcommands).
     *
     * Each entry is appended after the binary path. For example, `['add-cdda-times --help']`
     * produces `./dist/binary add-cdda-times --help` in addition to the default `--help` test.
     * @var string[]
     */
    test_commands: [],
    /**
     * @brief Extra arguments to `uv sync` or `poetry install`.
     * @var string[]
     */
    uv_sync_args: [],
    /** @brief vcpkg configuration for building native dependencies. */
    vcpkg: {
      /** @brief Whether vcpkg setup steps are generated. */
      enabled: false,
      /**
       * @brief Dictionary of matrix.os values to vcpkg target configurations.
       *
       * Each value is an object with `triplet` (string) and `packages` (string[]).
       */
      targets: {},
    },
  },
  /** @brief AppImage configuration (for Python only). */
  appimage: {
    /**
     * @brief Array of script names to exclude from Linux.
     * @var string[]
     */
    exclusions: [],
    /**
     * @brief If non-empty, only build these script names (overrides exclusions).
     * @var string[]
     */
    include_only: [],
    /** @brief Dictionary of script names to icon URIs. */
    icons: {},
    /**
     * @brief Array of AppImage categories.
     * @var string[]
     * @sa https://specifications.freedesktop.org/menu-spec/latest/apa.html for valid values.
     */
    categories: ['Utility'],
    /** @brief Python version to use for the AppImage. */
    python_version: '3.13',
    /** @brief If the application is a terminal application. */
    terminal: true,
    /**
     * @brief Extra test commands to run on each built binary (e.g. subcommands).
     * @var string[]
     */
    test_commands: [],
    /**
     * @brief Extra arguments to `uv sync` or `poetry install`.
     * @var string[]
     */
    uv_sync_args: [],
    /**
     * @brief Regex filter for `uv export` output to add optional deps to requirements.txt.
     *
     * If non-empty, runs `uv export | grep -E '<filter>'` and appends matches.
     */
    requirements_filter: '',
  },
  /**
   * @brief If the project should upload coverage to Coveralls.
   * @var boolean
   */
  want_coveralls: self.using_github && !self.stubs_only && !self.private,
  /** @brief If the cspell pre-commit hook should be included. */
  cspell_pre_commit_hook: true,
  /** @brief If the project will use SQLFluff. */
  want_sqlfluff: false,
  /** @brief If the project will publish to WinGet using GitHub Actions (C/C++ only). */
  want_winget: true,

  /**
   * @brief Social media configuration (for badges).
   *
   * If a URI is provided, a badge will be generated for it. For GitHub and Mastodon, the username
   * is sufficient to generate the URI.
   */
  social: {
    /** @brief Bluesky username. */
    bsky: '',
    /** @brief Mastodon configuration. */
    mastodon: {
      /** @brief Mastodon account ID. */
      id: '',
      /** @brief Mastodon instance domain. */
      domain: 'hostux.social',
    },
    /** @brief YouTube configuration. */
    youtube: {
      /** @brief YouTube channel name displayed in badge. */
      text: 'YouTube',
      /** @brief YouTube channel URI. */
      uri: '',
    },
    /** @brief Patreon username. */
    patreon: '',
    /** @brief Cash App $Cashtag. */
    cashapp: '',
    /** @brief Slashdot username. */
    slashdot: '',
    /** @brief Calendly configuration. */
    calendly: {
      /** @brief Calendly username displayed in badge. */
      text: 'Calendly',
      /** @brief Calendly URI. */
      uri: '',
    },
    /** @brief Buy Me a Coffee username. */
    buymeacoffee: '',
    /** @brief Libera Chat IRC nick. */
    libera_irc: '',
    /**
     * @brief Array of custom badges (Markdown strings).
     * @var string[]
     */
    custom_badges: [],
  },
  /**
   * @brief Array of custom project badges displayed before the social section.
   *
   * Each entry is an object with the following keys:
   * - `anchor` (string): Markdown anchor text, e.g. `[![alt](image_url)]`.
   * - `href` (string): Link target URL.
   * - `priority` (int): Sort key (default 0). Lower values appear first.
   *
   * @var { anchor: string, href: string, priority: int }[]
   */
  custom_project_badges: [],

  // General settings
  /**
   * @brief Code owners for the project.
   *
   * Dictionary of string to string. The value is usually the GitHub or GitLab username but this is
   * host-dependent.
   */
  codeowners: {
    '*': '@%s' % settings.github_username,
  },
  /** @brief Supported versions for the security policy (table in `SECURITY.md`). */
  security_policy_supported_versions: { '0.0.x': ':white_check_mark:' },
  /** @brief Additional text to add to the end of `SECURITY.md`. */
  security_addendum: '',
  /**
   * @brief If the project uses Django.
   * @var boolean
   */
  using_django: self.project_type == 'python' && 'django' in self.python_deps.main,
  /**
   * @brief If the project uses Django REST Framework.
   * @var boolean
   */
  using_drf: self.project_type == 'python' && 'djangorestframework' in self.python_deps.main,
  /**
   * @brief If the project is hosted on GitHub.
   * @var boolean
   */
  using_github: std.member(self.repository_uri, 'github.com'),
  /**
   * @brief If the project is hosted on GitLab.
   * @var boolean
   */
  using_gitlab: std.member(self.repository_uri, 'gitlab.com'),
  /** @brief GitLab CI configuration object; manifest as `.gitlab-ci.yml` when non-empty. */
  gitlab_ci: {},
  /** @brief If the project hosts documentation on ReadTheDocs. */
  using_readthedocs: true,
  /** @brief If the project consists of only Python typing stubs. */
  stubs_only: false,
  /** @brief If the project should have a `CITATION.cff` file. */
  want_cff: true,
  /**
   * @brief If the project should include ``AGENTS.md``, ``CLAUDE.md``, and the ``.claude/`` tree.
   * @var boolean
   */
  want_ai: true,
  /**
   * @brief If using beads with AI tooling. All this does is add the Beads instructions to ``AGENTS.md``.
   * @var boolean
   */
  using_beads: false,
  /**
   * @brief If user-level ``defaults.jsonnet`` is merged with project settings.
   * @details Wiswa reads a ``uses_user_defaults: true`` literal only from ``.wiswa.jsonnet`` to
   *     enable merging; the flag cannot be enabled from user ``defaults.jsonnet`` alone.
   * @var boolean
   */
  uses_user_defaults: false,
  /** @brief JSON object written to ``.claude/settings.local.json.dist`` when ``want_ai`` is true. */
  claude_settings_local: {
    /** @brief Permissions dictionary. */
    permissions: {
      /**
       * @brief Allowed commands.
       * @var string[]
       */
      allow: (if settings.using_github then ['Bash(gh api *)'] else []) + (
               if settings.using_gitlab then ['Bash(glab api *)'] else []
             ) + [
               'Bash(mkdir --parents .wiswa-ci)',
               'Bash(mkdir -p .wiswa-ci)',
               'Bash(mkdir .wiswa-ci)',
               'Bash(mktemp *)',
             ] + (if settings.project_type == 'python' then (
                    if settings.package_manager == 'uv' then [
                      'Bash(uv add *)',
                      'Bash(uv audit *)',
                      'Bash(uv cache *)',
                      'Bash(uv export *)',
                      'Bash(uv lock *)',
                      'Bash(uv pip *)',
                      'Bash(uv remove *)',
                      'Bash(uv run mypy *)',
                      'Bash(uv run pytest *)',
                      'Bash(uv run ruff *)',
                      'Bash(uv run sphinx-build *)',
                      'Bash(uv run wiswa *)',
                      'Bash(uv run yapf *)',
                      'Bash(uv run yarn pyright *)',
                      'Bash(uv sync *)',
                      'Bash(uv tree *)',
                      'Bash(uv venv *)',
                      'Bash(uv version *)',
                    ] else [
                      'Bash(poetry about *)',
                      'Bash(poetry add *)',
                      'Bash(poetry cache *)',
                      'Bash(poetry check *)',
                      'Bash(poetry debug *)',
                      'Bash(poetry env *)',
                      'Bash(poetry export *)',
                      'Bash(poetry help *)',
                      'Bash(poetry install *)',
                      'Bash(poetry list *)',
                      'Bash(poetry lock *)',
                      'Bash(poetry remove *)',
                      'Bash(poetry run mypy *)',
                      'Bash(poetry run pytest *)',
                      'Bash(poetry run ruff *)',
                      'Bash(poetry run sphinx-build *)',
                      'Bash(poetry run wiswa *)',
                      'Bash(poetry run yapf *)',
                      'Bash(poetry run yarn pyright *)',
                      'Bash(poetry search *)',
                      'Bash(poetry show *)',
                      'Bash(poetry sync *)',
                      'Bash(poetry up *)',
                      'Bash(poetry update *)',
                      'Bash(poetry version *)',
                    ]
                  ) + [
                    'Bash(yarn mypy *)',
                    'Bash(yarn pyright *)',
                    'Bash(yarn ruff *)',
                    'Bash(yarn ruff:fix *)',
                    'Bash(yarn test *)',
                    'Bash(yarn test:cov *)',
                    'Read(~/.cache/mypy/**)',
                    'Read(~/.cache/uv/**)',
                    'WebFetch(domain:pypi.org)',
                    'WebFetch(domain:readthedocs.io)',
                    'Write(~/.cache/mypy/**)',
                    'Write(~/.cache/uv/**)',
                  ]) + [
               'Bash(rm --force ./.vscode/dictionary.txt)',
               'Bash(rm -f ./.vscode/dictionary.txt)',
               'Bash(rm ./.vscode/dictionary.txt)',
               'Bash(yarn check-formatting *)',
               'Bash(yarn check-spelling *)',
               'Bash(yarn cspell *)',
               'Bash(yarn dict:update *)',
               'Bash(yarn format *)',
               'Bash(yarn gen-docs *)',
               'Bash(yarn gen-manpage *)',
               'Bash(yarn markdownlint-cli2 *)',
               'Bash(yarn prettier *)',
               'Bash(yarn qa *)',
               'Bash(yarn regen *)',
               'Edit(/.vscode/dictionary.txt)',
               'Edit(/.wiswa-ci/**)',
               'Read(/.vscode/dictionary.txt)',
               'Read(/.wiswa-ci/**)',
               'Update(/.vscode/dictionary.txt)',
               'WebFetch(domain:npmjs.com)',
             ] + (if settings.project_type == 'c' || settings.project_type == 'c++' then [
                    'Bash(cmake *)',
                    'Bash(clang-format *)',
                    'Bash(vcpkg *)',
                  ] else []) +
             (if settings.using_github then ['WebFetch(domain:api.github.com)'] else []) +
             (if settings.using_gitlab then ['WebFetch(domain:gitlab.com)'] else []),
    },
  },
  /**
   * @brief If the project should have a CodeQL configuration.
   * @var boolean
   */
  want_codeql: !self.stubs_only && self.using_github,
  /** @brief If Git commits and tags should be GPG-signed. */
  want_gpg: true,
  /** @brief If the project will generate documentation. */
  want_docs: true,
  /**
   * @brief If Sphinx runs should treat warnings as errors (``yarn gen-docs``, ``yarn gen-manpage``,
   *     and ReadTheDocs ``sphinx.fail_on_warning``).
   * @var boolean
   */
  sphinx_fail_on_warning: true,
  /** @brief If ``yarn.lock`` should be deleted before running Yarn during post-processing. */
  regenerate_yarn_lock: true,
  /** @brief If the project should have a main module (for CLI). */
  want_main: false,
  /** @brief If the project has multiple entry points (CLI commands). */
  has_multiple_entry_points: false,
  /**
   * @brief If the project will have manual pages.
   * @var boolean
   */
  want_man: self.want_main,
  /**
   * @brief If the project will have a Snapcraft configuration.
   * @var boolean
   */
  want_snap: self.project_type != 'xcode' && self.want_main && !self.private,
  /**
   * @brief If the project will have a Flatpak configuration.
   * @var boolean
   */
  want_flatpak: self.project_type != 'xcode' && self.want_main && !self.private && self.publishing.flathub != '',
  /**
   * @brief If the project will have tests.
   * @var boolean
   */
  want_tests: !self.stubs_only,
  /**
   * @brief If the project will use YAPF for formatting.
   *
   * YAPF only supports up to Python 3.11 as of the time of writing, so this is only true if the
   * project supports Python 3.10 or 3.11.
   * @var boolean
   */
  want_yapf: std.contains(self.supported_python_versions, '3.10') ||
             std.contains(self.supported_python_versions, '3.11'),
  /**
   * @brief Copyright year of the project.
   *
   * The default setting requires that a native callback `year()` be registered.
   *
   * @var int
   */
  year: utils.year(),

  // Detailed settings
  /** @brief Line width for code formatting. */
  line_width: 100,
  /** @brief Depth of the Python package index (for Pyright and Pylance). */
  python_package_index_depth: 100,

  // Tab sizes
  /** @brief Tab size for C/C++ files. */
  c_cpp_tab_size: 4,
  /** @brief Tab size for Python files. */
  python_tab_size: 4,
  /** @brief Tab size for reStructuredText files. */
  rst_tab_size: 3,
  /** @brief Tab size for shell scripts. */
  shell_tab_size: 4,
  /** @brief Default tab size. */
  tab_size: 2,

  // Shared
  /**
   * @brief Array of authors.
   * @sa [What is a CITATION.cff file?](https://citation-file-format.github.io/#/what-is-a-citation-cff-file)
   * @var object[]
   *
   * <dl class="section default-value">
   * <dt>Structure</dt>
   * <dd>
   * @code
   * [
   *   {
   *     'family-names': string; // Usually a last name.
   *     'given-names':  string; // Usually a first name.
   *     email: string;
   *     name?: string; // This field is optional and will be generated if not provided.
   *   },
   *   ...
   * ]
   * @endcode
   * </dd>
   * </dl>
   */
  authors: [
    {
      'family-names': 'Not',
      'given-names': 'Filled In',
      email: 'not-filled-in@email.com',
      name: '%s %s' % [self['given-names'], self['family-names']],
    },
  ],
  /** @brief The cspell language setting, derived from `package_json.cspell.language`. */
  cspell_language: self.package_json.cspell.language,
  /** @brief Project name. */
  project_name: 'not-a-project-name',
  /**
   * @brief Project name on PyPI.
   * @var string
   */
  pypi_project_name: self.project_name,
  /**
   * @brief Repository name (on any hosting provider).
   * @var string
   */
  repository_name: std.strReplace(std.strReplace(self.project_name, '@', ''), '/', '-'),
  /**
   * @brief Array of shared ignore patterns.
   * @var string[]
   */
  shared_ignore: import 'defaults/shared-ignore.libsonnet',
  /**
   * @brief Pre-commit configuration.
   *
   * <h3>Structure</h3>
   *
   * ```csharp
   * {
   *   default_install_hook_types: string[];
   *   repos: {
   *     hooks: {
   *       id: string;
   *       name: string;
   *     }[];
   *     repo: string;
   *     rev?: string;
   *   }[];
   * }
   * ```
   */
  pre_commit_config: {
    /**
     * @brief Array of default pre-commit hook types to install.
     * @var string[]
     */
    default_install_hook_types: [
      'pre-commit',
      'pre-push',
      'post-checkout',
      'post-merge',
    ],
    local yapf_precommit = if settings.want_yapf then
      [import 'defaults/pre-commit-config/yapf.libsonnet']
    else [],
    local poetry_plugin_export = if settings.project_type == 'python' && settings.export_requirements.enabled && !is_uv then
      [(import 'defaults/pre-commit-config/poetry-plugin-export.libsonnet').get(settings)]
    else [],
    local pkg_mgr_hooks = if is_uv then [import 'defaults/pre-commit-config/uv.libsonnet']
    else [import 'defaults/pre-commit-config/poetry.libsonnet'],
    local precommit_python_repos = if settings.project_type == 'python' then
      pkg_mgr_hooks + poetry_plugin_export + yapf_precommit else [],
    local precommit_c_cpp_repos = if settings.project_type == 'c' || settings.project_type == 'c++' then [
      import 'defaults/pre-commit-config/clang-format.libsonnet',
    ] else [],
    /**
     * @brief Array of pre-commit repositories.
     * @var object[]
     *
     * <h3>Structure</h3>
     *
     * ```csharp
     * {
     *   hooks: {
     *     id: string;
     *     name: string;
     *   }[];
     *   repo: string;
     *   rev?: string;
     * }[];
     * ```
     */
    repos: [(import 'defaults/pre-commit-config/main.libsonnet').get(settings)] +
           precommit_python_repos + precommit_c_cpp_repos + github + cff + [local_hooks.get(settings)] + cspell_hooks,
  } + (if !settings.private then {
         ci: {
           skip: [
             'check-jsonschema',
           ] + (if settings.cspell_pre_commit_hook then ['cspell'] else []) + [
             'detect-aws-credentials',
             'fix-formatting-markdown',
             'fix-formatting-prettier',
           ] + (if settings.project_type == 'python' then ['fix-ruff'] else []) + [
             'yarn-check-lock',
           ],
         },
       } else {}),
  /** @brief Visual Studio Code configuration. */
  vscode: {
    /** @brief C/C++ configuration for Visual Studio Code. */
    c_cpp: import 'defaults/vscode/c_cpp_properties.libsonnet',
    /** @brief Array of VS Code extensions. */
    extensions: (import 'defaults/vscode/extensions.libsonnet').get(settings),
    /** @brief VS Code launch configuration. */
    launch: (import 'defaults/vscode/launch.libsonnet').get(settings),
    /** @brief VS Code settings. */
    settings: vscode_settings.get(settings),
  },
  /** @brief ReadTheDocs configuration. */
  readthedocs: rtd {
    build+: {
      jobs+: {
        post_install: if is_uv then [
          'pip install uv',
          'UV_PROJECT_ENVIRONMENT="$READTHEDOCS_VIRTUALENV_PATH" uv sync --group docs --inexact --all-extras --no-dev',
        ] else rtd.build.jobs.post_install,
      },
    },
    sphinx+: {
      fail_on_warning: settings.sphinx_fail_on_warning,
    },
  },

  // GitHub
  /** @brief GitHub settings. */
  github: {
    /** @brief CodeQL configuration. */
    codeql: {
      /** @brief Array of languages for CodeQL analysis. */
      languages: (if settings.project_type == 'python' then ['python', 'actions']
                  else if settings.project_type == 'typescript' then ['javascript-typescript', 'actions']
                  else if settings.project_type == 'c' || settings.project_type == 'c++' then ['c-cpp', 'actions']
                  else ['actions']),
      /** @brief Operating system for CodeQL runs on GitHub runners. */
      runs_on: if settings.project_type != 'xcode' then settings.tests_run_on else 'macos-latest',
    },
    /** @brief Dependabot configuration. */
    dependabot: (import 'defaults/dependabot.libsonnet').updates(settings),
    /** @brief Funding configuration. */
    funding: {
      /** @brief GitHub username. */
      github: settings.github_username,
    },
    /** @brief GitHub Pages configuration. */
    pages_config: import 'defaults/_config.libsonnet',
    /** @brief GitHub Pages URI. */
    pages_uri: 'https://%s.github.io/%s/' % [
      std.asciiLower(settings.github_username),
      settings.github_project_name,
    ],
    /** @brief If releases should be immutable (prevent asset modification after publish). */
    immutable_releases: true,
    /** @brief If GitHub Pages is using Jekyll. */
    pages_using_jekyll: true,
    /** @brief GitHub username. */
    username: settings.github_username,
    /**
     * @brief Names of GitHub repository or organisation secrets used for binary signing.
     *
     * These are the secret variable names configured in GitHub, not the actual secret values.
     */
    secret_vars: {
      /** @brief Windows Authenticode signing secret variable names. */
      windows: {
        /** @brief Name of the secret containing the base64-encoded PFX file. */
        signing_certificate: 'WINDOWS_SIGNING_CERTIFICATE',
        /** @brief Name of the secret containing the PFX password. */
        signing_password: 'WINDOWS_SIGNING_PASSWORD',
        /** @brief Name of the secret containing the RFC 3161 timestamp server URL (optional). */
        timestamp_url: 'WINDOWS_TIMESTAMP_URL',
      },
      /** @brief macOS code signing and notarisation secret variable names. */
      apple: {
        /** @brief Name of the secret containing the base64-encoded .p12 file. */
        signing_certificate: 'APPLE_SIGNING_CERTIFICATE',
        /** @brief Name of the secret containing the .p12 password. */
        signing_password: 'APPLE_SIGNING_PASSWORD',
        /** @brief Name of the secret containing the code-signing identity string. */
        signing_identity: 'APPLE_SIGNING_IDENTITY',
        /** @brief Name of the secret containing the Apple ID email used for notarisation. */
        apple_id: 'APPLE_ID',
        /** @brief Name of the secret containing the app-specific password. */
        app_specific_password: 'APPLE_APP_SPECIFIC_PASSWORD',
        /** @brief Name of the secret containing the Team ID. */
        team_id: 'APPLE_TEAM_ID',
      },
    },
    /** @brief GitHub Actions workflows configuration. */
    workflows: {
      /** @brief AppImage generation settings. */
      appimage: {
        /**
         * List of packages to install with APT.
         * @var string[]
         */
        apt_packages: [],
      },
      codeql: {
        /**
         * List of packages to install with APT.
         * @var string[]
         */
        apt_packages: [],
      },
      /** @brief NPM publishing settings. */
      publish_npm_any: {
        /** @brief Node version to use for the build. */
        node_version: '24',
        /** @brief Operating system. */
        runs_on: 'ubuntu-latest',
        /** @brief Registry URI. */
        registry_url: 'https://registry.npmjs.org/',
      },
      /** @brief PyPI publishing settings. */
      publish_pypi_any: {
        /** @brief Python version to use for the build. */
        python_version: '3.13',
        /** @brief Operating system. */
        runs_on: 'ubuntu-latest',
      },
      /** @brief WinGet publishing settings. */
      publish_winget: {
        /**
         * Package identifier.
         * @var string
         */
        identifier: '%s.%s' % [settings.github_username, settings.github_project_name],
        /** @brief Maximum number of versions to keep published. */
        max_versions_to_keep: 3,
      },
      /** @brief QA task settings. */
      qa: {
        /**
         * List of packages to install with APT.
         * @var string[]
         */
        apt_packages: [],
      },
      /** @brief Tests running settings. */
      tests: {
        /**
         * List of packages to install with APT.
         * @var string[]
         */
        apt_packages: [],
      },
    },
  },
  /** @brief Operating system for `qa.yml` runs on GitHub runners. */
  qa_runs_on: self.tests_run_on,
  /** @brief Operating system for `tests.yml` on GitHub runners. */
  tests_run_on: 'ubuntu-latest',

  // .cz.json
  /** @brief Commitizen configuration. */
  local cz = import 'defaults/cz.libsonnet',
  cz: cz.get(settings),

  // CITATION.cff
  /** @brief `CITATION.cff` output. */
  citation: {
    /** @brief CITATION.cff version. */
    'cff-version': '1.2.0',
    /**
     * @brief Date when the software was released.
     *
     * Requires a native function `isodate()` to be defined in the Jsonnet environment that returns
     * the current date in ISO 8601 format (YYYY-MM-DD).
     */
    'date-released': utils.isodate(),
    /**
     * @brief Array of authors.
     * @sa [What is a CITATION.cff file?](https://citation-file-format.github.io/#/what-is-a-citation-cff-file)
     **/
    authors: utils.citationAuthors(settings.authors),
    /** @brief Message to display when citing the software. */
    message: 'If you use this software, please cite it as below.',
    /** @brief Title of the software. */
    title: settings.project_name,
    /** @brief Version of the software. */
    version: settings.version,
  },

  // Git
  /**
   * @brief Array of `.gitattributes` entries.
   * @var string[]
   */
  gitattributes: [
    '* text=auto eol=lf',
    '*.lock binary',
    '/.yarn/**/*.cjs binary',
  ],
  local cpp_ignore = if self.project_type == 'c++' || self.project_type == 'c' then [
    '*.info',
    '/build/',
    '/CMakeUserPresets.json',
    '/vcpkg_installed/',
  ] else [],
  local claude_ignore = if self.want_ai then [
    '/.claude/settings.json',
    '/.claude/settings.local.json',
  ] else [],
  local python_ignore = if self.project_type == 'python' then [
    '.venv/',
    '/docs/_build/',
    '/man/_static/',
    '/mypy-report*/',
    '__pycache__/',
    'cobertura.xml',
    'coverage.xml',
    'htmlcov/',
    'mypy-report.xml',
  ] else [],
  local typescript_ignore = if self.project_type == 'typescript' then ['/coverage/'] else [],
  /** @brief Array of .gitignore entries. */
  gitignore: std.set(self.shared_ignore + python_ignore + cpp_ignore + typescript_ignore +
                     claude_ignore + if !self.keep_dist then ['/dist/'] else []),

  // C/C++ only
  local clang_format = import 'defaults/clang-format.libsonnet',
  local cmake_user_presets = import 'defaults/cmake-user-presets.libsonnet',
  local vcpkg = import 'defaults/vcpkg.libsonnet',
  local vcpkg_config = import 'defaults/vcpkg-config.libsonnet',
  vcpkg_root: '/home/tatsh/dev/vcpkg',
  /** @brief Clang format configuration. */
  clang_format: clang_format.get(self.line_width, self.c_cpp_tab_size),
  /** @brief Arguments (file globs) passed to clang-format. */
  clang_format_args: 'src/*.cpp src/*.h',
  /** @brief CMake presets. */
  cmake_presets: import 'defaults/cmake-presets.libsonnet',
  /** @brief CMake user presets. */
  cmake_user_presets: cmake_user_presets.get(self.vcpkg_root),
  /** @brief vcpkg package metadata. */
  vcpkg: vcpkg.get(settings),
  /** @brief vcpkg configuration. */
  vcpkg_config: vcpkg_config,
  cmake: {
    shared_deps: [],
    googletest_version: '1.17.0',
    uses_ecm: false,
    uses_qt: false,
    want_feature_summary: true,
    want_cpack: true,
  },
  cxx_standard: 23,

  // Python only
  local pyproject = import 'defaults/pyproject.libsonnet',
  /** @brief Array of supported Python versions. */
  supported_python_versions: ['3.%d' % i for i in std.range(10, 14)],
  /** @brief If true, add upper boundary to Python version requirement. */
  python_dep_upper_boundary: false,
  /**
   * @brief Import name for the Python tree Wiswa manages (dots become nested directories).
   *
   * For PEP 420 namespace layouts, set this to the top-level namespace directory only (no dots)
   * and set ``primary_module_qualified`` to the full dotted import path.
   */
  primary_module: std.strReplace(self.project_name, '-', '_'),
  /**
   * @brief Fully qualified import name for the on-disk package (dots between segments).
   *
   * Defaults to ``primary_module``. Namespace-style layouts are inferred when this value differs
   * from ``primary_module`` and contains at least one ``.`` (e.g. ``vendor`` and
   * ``vendor.product.service``).
   */
  primary_module_qualified: self.primary_module,
  /**
   * @brief Python dependencies in Poetry-style syntax.
   *
   * Users add project-specific deps with `python_deps+: { main+: { colorlog: '^6.0' } }`.
   * Values may be version strings (`^1.0`), objects (`{ extras: ['x'], version: '^1.0' }`),
   * or arrays of `{ version, python }` objects for marker-conditional deps.
   * Wiswa converts these to the correct format for the chosen package manager.
   */
  python_deps: if self.project_type == 'python' then
    local has_poetry = std.objectHasAll(self.pyproject.tool, 'poetry');
    local poetry_obj = if has_poetry then self.pyproject.tool.poetry else {};
    local poetry_deps_obj = if has_poetry && std.objectHas(poetry_obj, 'dependencies')
    then poetry_obj.dependencies
    else {};
    local is_optional_dep(v) = std.isObject(v) && std.objectHas(v, 'optional') && v.optional;
    local legacy_main = if is_uv then {
      [k]: poetry_deps_obj[k]
      for k in std.objectFields(poetry_deps_obj)
      if k != 'python' && !is_optional_dep(poetry_deps_obj[k])
    } else {};
    local poetry_group = if has_poetry && std.objectHas(poetry_obj, 'group')
    then poetry_obj.group
    else {};
    local poetry_group_deps(name) =
      if std.objectHas(poetry_group, name) && std.objectHas(poetry_group[name], 'dependencies')
      then poetry_group[name].dependencies
      else {};
    local legacy_group(name) = if is_uv then poetry_group_deps(name) else {};
    default_deps {
      main+: legacy_main,
      dev+: legacy_group('dev'),
      docs+: legacy_group('docs'),
      tests+: legacy_group('tests'),
    }
  else {
    main: {},
    dev: {},
    docs: {},
    tests: {},
  },
  /** @brief Python project configuration (`pyproject.toml`). */
  pyproject: pyproject {
    local primary_module_qualified_path = std.join('/', std.split(settings.primary_module_qualified, '.')),
    local hatch_wheel_top_level_only =
      settings.primary_module_qualified != settings.primary_module
      && std.length(std.findSubstr('.', settings.primary_module_qualified)) > 0,
    local poetry_package_includes = std.set([std.split(m, '.')[0] for m in settings.modules]),
    local python_req = if settings.python_dep_upper_boundary then ('>=%s,<3.%d' % [
                                                                     settings.supported_python_versions[0],
                                                                     std.parseInt(
                                                                       settings.supported_python_versions[
                                                                         std.length(settings.supported_python_versions) - 1][2:]
                                                                     ) + 1,
                                                                   ])
    else ('>=%s,<4.0' % settings.supported_python_versions[0]),
    local py_deps = settings.python_deps,
    local to_pep508(group) = std.sort(
      std.flatMap(function(k) utils.formatPep508Deps(k, group[k]), std.objectFields(group))
    ),
    local has_poetry = std.objectHasAll(self.tool, 'poetry'),
    local poetry_obj = if has_poetry then self.tool.poetry else {},
    local poetry_deps_obj = if has_poetry && std.objectHas(poetry_obj, 'dependencies')
    then poetry_obj.dependencies
    else {},
    local is_optional_dep(v) = std.isObject(v) && std.objectHas(v, 'optional') && v.optional,
    local legacy_poetry_optional_deps =
      if is_uv then
        { [k]: poetry_deps_obj[k] for k in std.objectFields(poetry_deps_obj) if is_optional_dep(poetry_deps_obj[k]) }
      else {},
    local poetry_extras = if has_poetry && std.objectHas(poetry_obj, 'extras') then poetry_obj.extras else {},
    local poetry_plugins = if has_poetry && std.objectHas(poetry_obj, 'plugins') then poetry_obj.plugins else {},
    project+: {
      authors: utils.pyprojectAuthors(settings.authors),
      classifiers: utils.pyprojectClassifiers(settings),
      description: settings.description,
      keywords: settings.keywords,
      name: settings.project_name,
      version: settings.version,
      license: settings.license,
      scripts: if settings.want_main then {
                 [settings.project_name]: '%s.main:main' % settings.primary_module_qualified,
               } else {},
      urls: {
        homepage: settings.homepage,
        documentation: settings.documentation_uri,
        Issues: (if settings.using_github then '%s/issues' else '%s/-/issues') % settings.repository_uri,
        repository: settings.repository_uri,
      },
    } + if is_uv then {
      dependencies: std.set(to_pep508(py_deps.main)),
      'requires-python': python_req,
      dynamic:: super.dynamic,
    } + (if is_uv && std.length(std.objectFields(poetry_plugins)) > 0 then {
           'entry-points': poetry_plugins,
         } else {}) + (if std.length(std.objectFields(poetry_extras)) > 0 then {
                         'optional-dependencies': {
                           [extra]: std.set(std.flatMap(
                             function(dep_name)
                               if std.objectHas(legacy_poetry_optional_deps, dep_name) then
                                 utils.formatPep508Deps(dep_name, legacy_poetry_optional_deps[dep_name])
                               else
                                 [dep_name],
                             poetry_extras[extra]
                           ))
                           for extra in std.objectFields(poetry_extras)
                         },
                       } else {}) else {},
    [if is_uv then 'dependency-groups']: {
                                           dev: std.set(to_pep508(py_deps.dev)),
                                         } + (if settings.want_docs then {
                                                docs: std.set(to_pep508(py_deps.docs)),
                                              } else {})
                                         + (if settings.want_tests then {
                                              tests: std.set(to_pep508(py_deps.tests)),
                                            } else {}),
    tool+: {
             commitizen+: {
               remove_path_prefixes: std.set(pyproject.tool.commitizen.remove_path_prefixes + [
                 primary_module_qualified_path,
               ]),
               version_files: std.set(pyproject.tool.commitizen.version_files +
                                      (if !settings.stubs_only then [
                                         '%s/__init__.py' % primary_module_qualified_path,
                                       ] else []) +
                                      (if !settings.stubs_only then [
                                         'docs/badges.rst',
                                         'docs/index.rst',
                                       ] else []) +
                                      (if settings.want_snap then [
                                         'snapcraft.yaml',
                                       ] else []) +
                                      (if utils.wantFlatpakOutputs(settings) then [
                                         '%s.yml' % settings.publishing.flathub,
                                       ] else [])),
             },
             coverage+: {
               report+: {
                 omit: std.set(pyproject.tool.coverage.report.omit + (
                   if settings.want_main then ['%s/__main__.py' % primary_module_qualified_path] else []
                 )),
               },
               run+: {
                 omit: std.set(pyproject.tool.coverage.run.omit + (
                   if settings.want_main then ['%s/__main__.py' % primary_module_qualified_path] else []
                 )),
               },
             },
             mypy+: { python_version: settings.supported_python_versions[0] },
             local poetry_include = (if settings.want_docs && settings.want_man then ['man'] else []) +
                                    (if settings.want_tests then [{ path: 'tests', format: 'sdist' }] else []),
             [if !is_uv then 'poetry']+: {
               packages: [{ include: x } for x in poetry_package_includes],
               dependencies: {
                 python: python_req,
               } + py_deps.main,
               local docs_section = if settings.want_docs then { docs: { optional: true, dependencies: py_deps.docs } } else {},
               local tests_section = if settings.want_tests then { tests: { optional: true, dependencies: py_deps.tests } } else {},
               group+: {
                 dev+: {
                   dependencies: py_deps.dev,
                 },
                 docs+: {
                   dependencies: py_deps.docs,
                 },
                 tests+: {
                   dependencies: py_deps.tests,
                 },
               } + docs_section + tests_section,
             } + (if std.length(poetry_include) > 0 then { include: poetry_include } else {}),
             pyright+: {
                         include: ['./%s' % [r] for r in poetry_package_includes] + if settings.want_tests then [
                           './tests',
                         ] else [],
                         pythonVersion: settings.supported_python_versions[0],
                       } + (if settings.stubs_only then { reportImplicitOverride: 'none' } else {})
                       + (if is_uv then { venv: '.venv', venvPath: '.' } else {}),
             ruff+: {
               lint+: if settings.stubs_only then {
                 ignore: std.set(pyproject.tool.ruff.lint.ignore + [
                   'A002',
                   'E303',
                   'FBT001',
                   'I001',
                   'N',
                   'S',
                   'T201',
                   'TID252',
                 ]),
               } else (if settings.want_main then {
                         'per-file-ignores': {
                           ['%s/main.py' % primary_module_qualified_path]: ['PLR0913'],
                         },
                       }
                       else {}),
               'target-version': 'py3%s' % settings.supported_python_versions[0][2:],
             },
             [if is_uv && (settings.stubs_only || std.strReplace(settings.project_name, '-', '_') != settings.primary_module) then 'hatch']: {
               build: {
                 targets: {
                   sdist: {
                     include: std.set([std.split(m, '.')[0] for m in settings.modules]) +
                              (if settings.want_tests then ['tests'] else []),
                   },
                   wheel: {
                     packages: if hatch_wheel_top_level_only then
                       std.set([std.split(m, '.')[0] for m in settings.modules])
                     else
                       [utils.moduleImportToPath(m) for m in settings.modules],
                   },
                 },
               },
             },
           } + (if settings.want_sqlfluff then { sqlfluff: import 'defaults/sqlfluff.libsonnet' } else {})
           + (if is_uv then { poetry:: super.poetry }
                            + (if std.length(settings.package_sources) > 0 then {
                                 uv+: {
                                   index: [
                                     { name: s.name, url: s.url }
                                     + (if std.objectHas(s, 'priority') && s.priority == 'default' then { default: true } else {})
                                     for s in settings.package_sources
                                     if std.objectHas(s, 'url')
                                   ],
                                 },
                               } else {})
              else { uv:: super.uv }
                   + (if !is_uv && std.length(settings.package_sources) > 0 then {
                        poetry+: { source: settings.package_sources },
                      } else {})),
    'build-system': if is_uv then {
      requires: ['hatchling'],
      'build-backend': 'hatchling.build',
    } else {
      requires: ['poetry-core'],
      'build-backend': 'poetry.core.masonry.api',
    },
  },
  /** @brief Sphinx documentation configuration. */
  docs_conf: (import 'defaults/docs_conf.libsonnet') + {
    config+: {
      html_theme_options+: {
        edit_uri: '/tree/%s/docs' % settings.default_branch,
        repo_name: settings.directory_name,
        repo_url: settings.repository_uri,
        site_url: settings.documentation_uri,
      },
    },
  },
  /** @brief Ruff configuration for test files (`pyproject.toml` inside `tests`). */
  tests_pyproject: import 'defaults/pyproject-tests.libsonnet',

  // TypeScript only
  local tsconfig = import 'defaults/tsconfig.libsonnet',
  /** @brief TypeScript configuration. */
  tsconfig: tsconfig,
  /** @brief ESLint configuration. */
  eslint: [
    {
      rules: {
        '@typescript-eslint/no-unused-vars': [
          'error',
          {
            argsIgnorePattern: '^_',
            caughtErrorsIgnorePattern: '^_',
            destructuredArrayIgnorePattern: '^_',
            varsIgnorePattern: '^_',
          },
        ],
      },
    },
  ],
  /** @brief If ESLint tasks should be added on non-TypeScript projects. */
  force_eslint: self.project_type == 'typescript',

  // package.json only
  /** @brief Configuration for `package.json`. */
  package_json: package.get(self) + {
    contributors: ['%s <%s>' % [x.name, x.email] for x in settings.authors],
    homepage: settings.homepage,
    keywords: settings.keywords,
    license: settings.license,
    name: std.asciiLower(settings.project_name),
    packageManager: 'yarn@%s' % settings.yarn_version,
    repository: {
      type: 'git',
      url: if settings.using_github then utils.gitHubGitSshUri(settings.github_username, settings.github_project_name) else '%s.git' % settings.repository_uri,
    },
    version: settings.version,
  } + {
    local run_cmd = if is_uv then 'uv run' else 'poetry run',
    local sphinx_fail_flag = if settings.sphinx_fail_on_warning then ' --fail-on-warning' else '',
    scripts+: if settings.want_docs && settings.project_type == 'python' then {
      'gen-docs': '%s sphinx-build --fresh-env%s --builder html --doctree-dir docs/_build/doctrees --define language=en docs docs/_build/html' % [run_cmd, sphinx_fail_flag],
    } + if settings.want_man && settings.project_type == 'python' then {
      'gen-manpage': '%s sphinx-build --fresh-env%s --builder man --doctree-dir docs/_build/doctrees --define language=en docs man' % [run_cmd, sphinx_fail_flag],
    } else {}
    else {},
  },

  // Publishing
  /** @brief Publishing configuration. */
  publishing: {
    /** @brief App Store app identifier. */
    appstore: '',
    /** @brief Chrome Web Store app identifier. */
    chrome: '',  // chromewebstore
    /** @brief F-Droid app identifier. */
    fdroid: '',
    /** @brief Flathub app identifier. */
    flathub: '',
    /** @brief NuGet package identifier. */
    nuget: '',
    /** @brief Snapcraft app identifier. */
    snapcraft: '',
  },

  local cpp_prettierignore = if self.project_type == 'c++' || self.project_type == 'c' then
    cpp_ignore + ['*.c', '*.cpp', '*.h', '*.in'] else [],
  /**
   * @brief Array of patterns to ignore for Prettier.
   * @var string[]
   */
  prettierignore: std.set(self.shared_ignore +
                          [
                            '*.1',
                            '*.j2',
                            '*.jsonnet',
                            '*.libsonnet',
                            '*.libsonnet',
                            '*.lock',
                            'pylock*.toml',
                            '.eslintignore',
                            '.shellcheckrc',
                            '/.yarn/**/*.cjs',
                            '/dist/',
                          ] +
                          cpp_prettierignore + python_ignore),

  /**
   * @brief Yarn configuration used to generate `.yarnrc.yml`.
   *
   * The default disables telemetry, uses 'node-modules' as the node linker, and sets the Yarn
   * version to the one specified in the settings. It also adds plugin
   * `plugin-prettier-after-all-installed.cjs`.
   *
   * <h3>Structure</h3>
   *
   * ```csharp
   * {
   *   enableTelemetry?: boolean;
   *   nodeLinker?: 'node-modules' | 'pnp';
   *   npmMinimalAgeGate?: number;
   *   plugins?: { path: string }[];
   *   yarnPath: string;
   * }
   * ```
   */
  yarnrc: (import 'defaults/yarnrc.libsonnet') + {
    yarnPath: '.yarn/releases/yarn-%s.cjs' % settings.yarn_version,
  },

  /**
   * @brief Array of configuration lines.
   * @var string[]
   */
  luacheck: [],

  /**
   * @brief Array of additional APT packages to install in the Snapcraft Python part.
   * @var string[]
   */
  snap_python_build_packages: [],
  snap_python_stage_packages: [],
  local python_part = if settings.project_type == 'python' then {
    [settings.project_name]: {
      plugin: if is_uv then 'python' else 'poetry',
      source: '.',
      'build-packages': settings.snap_python_build_packages,
      'stage-packages': settings.snap_python_stage_packages,
    } + (if is_uv then { 'python-packages': ['.'] } else {}),
  } else {},
  /** @brief Snapcraft configuration. */
  snapcraft: {
    /**
     * This section defines the commands that will be available to users after installing the Snap,
     * as well as the permissions (plugs) required for those commands.
     * @brief Generate the `apps` section of `snapcraft.yaml` based on the provided settings.
     * @sa https://documentation.ubuntu.com/snapcraft/stable/reference/project-file/snapcraft-yaml/
     */
    apps: {
      [settings.project_name]: {
        command: 'bin/%s' % settings.project_name,
        plugs: ['home', 'network', 'network-bind'],
      },
    },
    /**
     * @brief Base.
     * @sa https://documentation.ubuntu.com/snapcraft/stable/reference/bases/
    */
    base: 'core24',
    /** @brief Confinement. One of: `['classic', 'devmode', 'strict']`.
     * @sa https://documentation.ubuntu.com/snapcraft/stable/reference/confinement/
     */
    confinement: 'strict',
    /**
     * @brief Package description.
     * @var string
     */
    description: settings.description,
    /**
     * @brief Package grade.
     * @var string
     */
    grade: if settings.private then 'devel' else 'stable',
    /**
     * @brief Package name.
     * @var string
     */
    name: settings.project_name,
    /** @brief Parts. */
    parts: python_part,
    /** @brief Platforms supported. */
    platforms: {
      /** @brief x86-64 settings. */
      amd64: {
        /** @brief Builds on this platform. */
        'build-on': 'amd64',
      },
      /** @brief arm64 settings. */
      arm64: {
        /** @brief Builds on this platform. */
        'build-on': 'arm64',
      },
    },
    /** @brief Source code URL. */
    'source-code': settings.repository_uri,
    /**
     * @brief A short description of the project. Maximum length 78 characters. Should not end in a
     * full stop.
     * @var string
     */
    summary: settings.description,
    /** @brief Title displayed in the Snap Store. */
    title: settings.project_name,
    /**
     * @brief Package version.
     * @var string
     */
    version: settings.version,
    /** @brief Project website. */
    website: settings.homepage,
  } + (if settings.using_github then {
         contact: '%s/issues' % settings.repository_uri,
         issues: '%s/issues' % settings.repository_uri,
         license: settings.license,
       } + (if settings.social.buymeacoffee != '' then {
              donation: 'https://buymeacoffee.com/%s' % settings.social.buymeacoffee,
            } else {}) else {}),

  /** @brief Flatpak manifest configuration. */
  flatpak: {
    'app-id': settings.publishing.flathub,
    command: settings.project_name,
    'finish-args': [
      '--share=ipc',
      '--share=network',
      '--socket=fallback-x11',
      '--socket=wayland',
    ],
    modules: [
      {
        name: settings.project_name,
        buildsystem: 'simple',
        'build-commands': [
          'pip3 install --no-index --find-links=. --prefix=/app .',
        ],
        sources: [
          {
            type: 'dir',
            path: '.',
          },
        ],
      },
    ],
    runtime: 'org.freedesktop.Platform',
    'runtime-version': '24.08',
    sdk: 'org.freedesktop.Sdk',
  },
}
