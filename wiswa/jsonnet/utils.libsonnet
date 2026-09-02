/**
 * @file utils.libsonnet
 * @namespace utils
 * @brief A collection of utility functions for manipulating settings.
 */
local utils = import 'utils.libsonnet';

{
  /**
   * @brief Map a dotted Python import name to a filesystem path (slashes between segments).
   * @param module Import name (e.g. ``vendor.product.service``).
   * @returns Relative POSIX path segments (e.g. ``vendor/product/service``).
   */
  moduleImportToPath(module)::
    std.join('/', std.split(module, '.')),

  /**
   * @brief Check if a PEP 508 dependency array contains a given package name.
   * @param deps An array of PEP 508 dependency strings (e.g. `["django>=5.2", "click>=8.0"]`).
   * @param name The package name to search for.
   * @returns True if the package is found in the array.
   * @pt string[], string
   * @rv boolean
   */
  hasDep(deps, name)::
    std.length(std.filter(function(d) std.startsWith(d, name), deps)) > 0,

  /**
   * @brief Check if a platform family is supported, whatever architecture is named.
   *
   * An entry may carry an architecture (``macos-arm64``), which supports that architecture alone.
   * The bare family name (``macos``) supports every architecture of it.
   * @param supported ``'all'``, a platform name, or an array of them.
   * @param family Platform family to look for (e.g. ``macos``).
   * @returns True if the family is supported on at least one architecture.
   * @pt string|string[], string
   * @rv boolean
   */
  supportsPlatform(supported, family)::
    supported == 'all' ||
    std.length(std.filter(
      function(p) p == family || std.startsWith(p, family + '-'),
      if std.isString(supported) then [supported] else supported
    )) > 0,

  /**
   * @brief Convert a Poetry-style version specifier to a PEP 508 specifier.
   *
   * `^X.Y.Z` becomes `>=X.Y.Z`, `~X.Y.Z` becomes `~=X.Y.Z`, and all other specifiers are
   * returned unchanged.
   *
   * @param ver A Poetry-style version string (e.g. `^1.2.3`, `~1.2`, `>=1.0,<2`).
   * @returns A PEP 508-compatible version specifier.
   * @pt string
   * @rv string
   */
  poetryVerToPep508(ver)::
    if std.startsWith(ver, '^') then '>=' + ver[1:]
    else if std.startsWith(ver, '~') then '~=' + ver[1:]
    else if std.length(ver) > 0 && std.member('0123456789', ver[0]) then '==' + ver
    else ver,

  /**
   * @brief Format a single dependency entry as a PEP 508 string.
   *
   * Handles plain version strings, objects with `extras` and `version` fields, and arrays of
   * version/marker objects (for multi-constraint deps like sphinx).
   *
   * @param name The package name.
   * @param val The version specifier: a string, an object `{extras, version}`, or an array of
   *            `{version, python}` or `{version, markers}` objects (the latter for an arbitrary
   *            PEP 508 marker).
   * @returns An array of PEP 508 dependency strings.
   * @pt string, (string | object | array)
   * @rv string[]
   */
  formatPep508Deps(name, val)::
    if std.isArray(val) then
      [
        if std.objectHas(entry, 'markers') then
          '%s%s; %s' % [name, self.poetryVerToPep508(entry.version), entry.markers]
        else
          '%s%s; python_version %s "%s"' % [
            name,
            self.poetryVerToPep508(entry.version),
            if std.startsWith(entry.python, '>=') then '>=' else '<',
            entry.python[std.length(if std.startsWith(entry.python, '>=') then '>=' else '<'):],
          ]
        for entry in val
      ]
    else if std.isObject(val) then
      local extrasPart = if std.objectHas(val, 'extras') && std.length(val.extras) > 0
      then '[%s]' % std.join(',', val.extras)
      else '';
      local platformPart = if std.objectHas(val, 'platform')
      then "; sys_platform == '%s'" % val.platform
      else '';
      ['%s%s%s%s' % [name, extrasPart, self.poetryVerToPep508(val.version), platformPart]]
    else
      ['%s%s' % [name, self.poetryVerToPep508(val)]],

  /**
   * @brief Convert an object to a TOML form with no indentation.
   * @param value The object to convert to TOML.
   * @returns The TOML representation of the object.
   * @rv string
   */
  manifestToml(value)::
    std.manifestTomlEx(value, ''),

  /**
   * @brief Convert an array to a string with each element on a new line.
   * @param value The array to convert.
   * @returns A string with each element on a new line.
   * @rv string
   */
  manifestLines(value)::
    std.join('\n', std.set(value)),


  /**
   * @brief Convert an object to a YAML form with indented arrays and unquoted keys.
   * @param value The object to convert to YAML.
   * @returns The YAML representation of the object.
   * @rv string
   */
  manifestYaml(value)::
    std.manifestYamlDoc(value, true, false),

  /**
   * @brief Get an author's full name, joining the given and family names when absent.
   * @param author An author object.
   * @returns The author's full name.
   * @pt object
   * @rv string
   */
  authorName(author)::
    if std.objectHas(author, 'name') then
      author.name
    else
      '%s %s' % [author['given-names'], author['family-names']],

  /**
   * @brief Convert an array of authors to a format suitable for citation metadata.
   * @param authors The array of author objects.
   * @returns An array of objects with `family-names` and `given-names` fields.
   */
  citationAuthors(authors)::
    [{
      'family-names': x['family-names'],
      'given-names': x['given-names'],
    } for x in authors],

  /**
   * @brief Generate a Git SSH URI for a GitHub repository.
   * @param github_username The GitHub username.
   * @param project_name The project name.
   * @returns A Git SSH URI (string).
   * @pt string, string
   * @rv string
   */
  gitHubGitSshUri(github_username, project_name)::
    'git@github.com:%s/%s.git' % [
      github_username,
      std.strReplace(std.strReplace(project_name, '@', ''), '/', '-'),
    ],

  /**
   * @brief Generate a readthedocs.org URI for a project.
   * @param project_name The project name.
   * @returns A readthedocs.org URI (string).
   * @pt string
   * @rv string
   */
  readTheDocsUri(project_name):: 'https://%s.readthedocs.org' % project_name,

  /**
   * @brief Generate a GitHub repository URI.
   * @param github_username The GitHub username.
   * @param project_name The project name.
   * @returns A GitHub repository URI (string).
   * @pt string, string
   * @rv string
   */
  gitHubRepositoryUri(github_username, project_name)::
    'https://github.com/%s/%s' % [
      github_username,
      std.strReplace(std.strReplace(project_name, '@', ''), '/', '-'),
    ],

  /**
   * @brief Generate a GitHub Pages URI.
   *
   * A repository named ``<username>.github.io`` is the user or organisation site, which GitHub
   * serves from the domain root. Every other repository is a project site served from a path
   * beneath it.
   *
   * @param github_username The GitHub username.
   * @param project_name The project name.
   * @returns A GitHub Pages URI (string).
   * @pt string, string
   * @rv string
   */
  gitHubPagesUri(github_username, project_name)::
    local user = std.asciiLower(github_username);
    if std.asciiLower(project_name) == '%s.github.io' % user then
      'https://%s.github.io/' % user
    else
      'https://%s.github.io/%s/' % [user, project_name],

  /**
   * @brief Extract the host from an ``http`` or ``https`` repository URI.
   * @param uri A repository URL such as ``https://gitlab.example.com/group/project``.
   * @returns The hostname, or empty string if the URI does not look like ``http(s)://host/...``.
   */
  repositoryUriHost(uri)::
    local parts = std.split(uri, '/');
    if std.length(parts) >= 3 && (parts[0] == 'https:' || parts[0] == 'http:') then
      parts[2]
    else
      '',

  /**
   * @brief Convert an array of authors to a format suitable for pyproject.toml.
   * @param authors The array of author objects.
   * @returns An array of objects with `name` and `email` fields.
   * @pt string[]
   * @rv object[]
   */
  pyprojectAuthors(authors)::
    [{
      name: $.authorName(x),
      email: x.email,
    } for x in authors],

  /**
   * @brief Generate a GitLab CI configuration.
   * @param settings The settings object.
   * @returns A GitLab CI configuration object.
   * @rv object
   */
  gitLabCi(settings):: {},

  /**
   * @brief Generate a sorted unique list of PyPI classifiers.
   * @param settings The settings object.
   * @param classifiers Additional classifiers to include.
   * @returns A sorted unique array of classifier strings.
   * @pt object, string[]
   * @rv string[]
   */
  pyprojectClassifiers(settings, classifiers=[])::
    std.set(classifiers + [
      'Development Status :: 4 - Beta',
      'Intended Audience :: Developers',
      'Programming Language :: Python',
      if settings.stubs_only then 'Typing :: Stubs Only' else 'Typing :: Typed',
    ] + [
      ('Programming Language :: Python :: %s' % i)
      for i in settings.supported_python_versions
    ]),
  /**
   * @brief Get the latest version of an npm package.
   *
   * Requires a native function `latestNpmPackageVersion` to be defined in the Jsonnet environment.
   * The returned version is automatically constrained by the project-wide `node_engine` setting
   * (default `>=20.0`), filtering out package versions whose own `engines.node` demands a newer
   * Node major.
   *
   * @param package The npm package name.
   * @returns The latest version string.
   * @pt string
   * @rv string
   */
  latestNpmPackageVersion(package):: std.native('latestNpmPackageVersion')(package),
  /**
   * @brief Get the latest version of an npm package, prefixed with a caret (^).
   *
   * Requires a native function `latestNpmPackageVersion` to be defined in the Jsonnet environment.
   * The returned version is automatically constrained by the project-wide `node_engine` setting
   * (default `>=20.0`), filtering out package versions whose own `engines.node` demands a newer
   * Node major.
   *
   * @param package The npm package name.
   * @returns The latest version string prefixed with `^`.
   * @pt string
   * @rv string
   */
  latestNpmPackageVersionCaret(package):: '^' + self.latestNpmPackageVersion(package),
  /**
   * @brief Get the latest version of a PyPI package, prefixed with a caret (^).
   *
   * Requires a native function `latestPypiPackageVersion` to be defined in the Jsonnet environment.
   *
   * @param package The PyPI package name.
   * @param h The PyPI-compatible host to query. Defaults to `pypi.org`.
   * @param py Minimum Python version to require compatibility with (e.g. `'3.10'`). Empty
   *   string disables filtering.
   * @returns The latest version string prefixed with `^`.
   * @pt string
   * @pt string
   * @pt string
   * @rv string
   */
  latestPypiPackageVersionCaret(package, h='pypi.org', py='')::
    '^' + self.latestPypiPackageVersion(package, h, py),
  /**
   * @brief Get the latest version of a PyPI package, prefixed with `>=`.
   *
   * Requires a native function `latestPypiPackageVersion` to be defined in the Jsonnet environment.
   *
   * @param package The PyPI package name.
   * @param h The PyPI-compatible host to query. Defaults to `pypi.org`.
   * @param py Minimum Python version to require compatibility with (e.g. `'3.10'`). Empty
   *   string disables filtering.
   * @returns The latest version string prefixed with `>=`.
   * @pt string
   * @pt string
   * @pt string
   * @rv string
   */
  latestPypiPackageVersionGe(package, h='pypi.org', py='')::
    '>=' + self.latestPypiPackageVersion(package, h, py),
  /**
   * @brief Get the latest version of a PyPI package, prefixed with a tilde (~).
   *
   * Requires a native function `latestPypiPackageVersion` to be defined in the Jsonnet environment.
   *
   * @param package The PyPI package name.
   * @param h The PyPI-compatible host to query. Defaults to `pypi.org`.
   * @param py Minimum Python version to require compatibility with (e.g. `'3.10'`). Empty
   *   string disables filtering.
   * @returns The latest version string prefixed with `~`.
   * @pt string
   * @pt string
   * @pt string
   * @rv string
   */
  latestPypiPackageVersionTilde(package, h='pypi.org', py='')::
    '~' + self.latestPypiPackageVersion(package, h, py),
  /**
   * @brief Get the latest version of a PyPI package.
   *
   * Requires a native function `latestPypiPackageVersion` to be defined in the Jsonnet environment.
   *
   * @param package The PyPI package name.
   * @param h The PyPI-compatible host to query. Defaults to `pypi.org`.
   * @param py Minimum Python version to require compatibility with (e.g. `'3.10'`). Empty
   *   string disables filtering.
   * @returns The latest version string.
   * @pt string
   * @pt string
   * @pt string
   * @rv string
   */
  latestPypiPackageVersion(package, h='pypi.org', py='')::
    std.native('latestPypiPackageVersion')(package, h, py),
  /**
   * @brief Resolve the latest action tag for a GitHub repository to its commit SHA.
   *
   * Requires a native function `githubLatestActionSha` to be defined in the Jsonnet environment.
   *
   * @param owner The repository owner.
   * @param repo The repository name.
   * @returns The 40-character hexadecimal commit SHA the latest action tag resolves to.
   * @pt string, string
   * @rv string
   */
  githubLatestActionSha(owner, repo):: std.native('githubLatestActionSha')(owner, repo),
  /**
   * @brief A hardened `actions/checkout` step that does not persist credentials.
   *
   * Credentials are not written to `.git/config`, so they cannot leak through build artifacts. A
   * nested `with` in `extra` is merged on top of the default `persist-credentials: false`.
   *
   * @param extra Additional fields merged into the generated step.
   * @returns A GitHub Actions step object pinning `actions/checkout` to a commit SHA.
   * @pt object
   * @rv object
   */
  checkout(extra={}):: {
    uses: 'actions/checkout@' + utils.githubLatestActionSha('actions', 'checkout'),
  } + extra + {
    with: { 'persist-credentials': false } +
          (if std.objectHas(extra, 'with') then extra.with else {}),
  },
  /**
   * @brief The permissions a build job needs to attest the artifacts it produces.
   *
   * `actions/attest` signs with a workflow OIDC token (`id-token: write`) and writes the resulting
   * provenance to the attestations API (`attestations: write`). These belong on the job that runs
   * the attestation, not on the workflow: a workflow-level grant hands the same token to every
   * other job, which zizmor reports as `excessive-permissions`. `contents` stays read-only because
   * the build only checks the repository out; the release writer requests write for itself.
   *
   * @param settings The settings object.
   * @returns A GitHub Actions permissions object.
   * @pt object
   * @rv object
   */
  attestPermissions(settings):: (if settings.private then { actions: 'write' } else {}) + {
    attestations: 'write',
    contents: 'read',
    'id-token': 'write',
  },
  /**
   * @brief A job that attaches a workflow's build artifacts to the draft release for the tag.
   *
   * GitHub enforces tag uniqueness only for published releases, so `gh release create --draft`
   * succeeds even when a draft already exists for the tag and cannot be used to detect one. Left
   * unguarded, every job that calls it creates its own draft and the assets end up split across
   * them. This job is therefore the single release writer for its workflow: the build jobs only
   * publish artifacts, and one small job collects them afterwards.
   *
   * The `concurrency` group is deliberately shared by every workflow in the repository, so the
   * release writers across `AppImage`, `Publish`, `Snap`, and the rest run one at a time and the
   * `view`-then-`create` check cannot race. `queue: max` is required: the default behaviour cancels
   * a pending job when another enters the group, which would silently drop a workflow's assets.
   * Because the job holds the lock only while downloading and uploading, the build matrices that
   * feed it still run in parallel.
   *
   * The tag is read from the `GITHUB_REF_NAME` environment variable to avoid interpolating a
   * GitHub Actions expression into the shell. `GH_REPO` is set explicitly so `gh` never invokes
   * `git` to detect the repository, which fails in container jobs where the workspace is owned by
   * a different user.
   *
   * @param needs Names of the jobs producing the artifacts.
   * @param pattern Artifact name pattern to collect. All matches are merged into one directory.
   *                When empty no artifacts are downloaded and only the draft release is ensured,
   *                which is what projects that publish no release assets need.
   * @returns A GitHub Actions job object.
   * @pt array, string
   * @rv object
   */
  releaseAssetsJob(needs, pattern=''):: {
    concurrency: {
      group: 'release-assets-${{ github.ref }}',
      queue: 'max',
    },
    'if': "github.ref_type == 'tag'",
    needs: needs,
    permissions: {
      contents: 'write',
    },
    'runs-on': 'ubuntu-latest',
    steps: (if pattern != '' then [{
              name: 'Download build artifacts',
              uses: 'actions/download-artifact@' +
                    utils.githubLatestActionSha('actions', 'download-artifact'),
              with: {
                'merge-multiple': true,
                path: '_release_assets',
                pattern: pattern,
              },
            }] else []) + [
      {
        name: 'Create or update draft release',
        env: {
          GH_REPO: '${{ github.repository }}',
          GH_TOKEN: '${{ github.token }}',
        },
        shell: 'bash',
        run: |||
          gh release view "$GITHUB_REF_NAME" >/dev/null 2>&1 ||
            gh release create "$GITHUB_REF_NAME" --draft --notes ''
          shopt -s nullglob
          assets=(_release_assets/*)
          if [ -z "${assets[0]-}" ]; then
            echo 'No build artifacts to attach.'
            exit 0
          fi
          gh release upload "$GITHUB_REF_NAME" "${assets[@]}" --clobber
        |||,
      },
    ],
  },
  /**
   * @brief Get the latest action tag for a GitHub repository.
   *
   * Requires a native function `githubLatestActionTag` to be defined in the Jsonnet environment.
   *
   * @param owner The repository owner.
   * @param repo The repository name.
   * @returns The latest action tag (string).
   * @pt string, string
   * @rv string
   */
  githubLatestActionTag(owner, repo):: std.native('githubLatestActionTag')(owner, repo),
  /**
   * @brief Resolve a Git ref (branch, tag, or full SHA) to its commit SHA on GitHub.
   *
   * Requires a native function `githubRefCommitSha` to be defined in the Jsonnet environment.
   *
   * @param owner The repository owner.
   * @param repo The repository name.
   * @param ref The Git ref to resolve (branch name, tag name, or full commit SHA).
   * @returns The 40-character hexadecimal commit SHA the ref resolves to.
   * @pt string, string, string
   * @rv string
   */
  githubRefCommitSha(owner, repo, ref)::
    std.native('githubRefCommitSha')(owner, repo, ref),
  /**
   * @brief Get the latest release tag for a GitHub repository.
   *
   * Requires a native function `githubLatestReleaseTag` to be defined in the Jsonnet environment.
   *
   * @param owner The repository owner.
   * @param repo The repository name.
   * @param npmMinReleaseAge When true, skip GitHub releases newer than the resolved
   * ``npmMinimalAgeGate`` (minutes): merged settings ``yarnrc``, then ``.wiswa.jsonnet`` text,
   * then repo or home ``.yarnrc.yml`` (minutes), then ``~/.npmrc`` ``min-release-age`` (days),
   * then the 10080 default.
   * @returns The latest release tag (string).
   * @pt string, string, boolean
   * @rv string
   */
  githubLatestReleaseTag(owner, repo, npmMinReleaseAge=false)::
    std.native('githubLatestReleaseTag')(owner, repo, npmMinReleaseAge),
  /**
   * @brief Get the latest tag for a GitHub repository.
   *
   * Requires a native function `githubLatestTag` to be defined in the Jsonnet environment.
   *
   * @param owner The repository owner.
   * @param repo The repository name.
   * @returns The latest tag (string).
   * @pt string, string
   * @rv string
   */
  githubLatestTag(owner, repo):: std.native('githubLatestTag')(owner, repo),
  /**
   * @brief Get the latest version of a vcpkg port.
   *
   * Requires a native function `latestVcpkgPortVersion` to be defined in the Jsonnet environment.
   * A non-zero port version is appended as `#N`, so the result is usable directly as a
   * `version>=` constraint in `vcpkg.json`.
   *
   * @param port The vcpkg port name.
   * @returns The latest version string, for example `6.29.0` or `6.11.1#1`.
   * @pt string
   * @rv string
   */
  latestVcpkgPortVersion(port):: std.native('latestVcpkgPortVersion')(port),
  /**
   * @brief Get the latest version of Yarn.
   *
   * Requires a native function `latestYarnVersion` to be defined in the Jsonnet environment.
   *
   * @returns The latest Yarn version (string).
   * @rv string
   */
  latestYarnVersion():: std.native('latestYarnVersion')(),
  /**
   * @brief Get the current year.
   * @returns The current year as an integer.
   * @rv int
   */
  year():: std.native('year')(),
  /**
   * @brief Get the current date in ISO format.
   * @returns The current date as a string in ISO format (YYYY-MM-DD).
   * @rv string
   */
  isodate():: std.native('isodate')(),
  /**
   * @brief GitHub login from the ``gh`` CLI when authenticated.
   *
   * Otherwise uses the owner in ``remote.origin.url`` from ``.git/config`` when that URL is on
   * github.com. Otherwise ``unknown``.
   *
   * @returns The GitHub username (string).
   * @rv string
   */
  githubCliUsername():: std.native('githubCliUsername')(),
  /**
   * @brief True when Flatpak manifest and workflows should be emitted (``want_flatpak`` and a
   *     non-empty Flathub app ID in ``publishing.flathub``).
   */
  wantFlatpakOutputs(settings)::
    settings.want_flatpak && std.length(std.stripChars(settings.publishing.flathub, ' \t\n\r')) > 0,
}
