/**
 * @file utils.libsonnet
 * @namespace utils
 * @brief A collection of utility functions for manipulating settings.
 */
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
   *            `{version, python}` objects.
   * @returns An array of PEP 508 dependency strings.
   * @pt string, (string | object | array)
   * @rv string[]
   */
  formatPep508Deps(name, val)::
    if std.isArray(val) then
      [
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
      name: x.name,
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
   * @param host The PyPI-compatible host to query. Defaults to `pypi.org`.
   * @param python Minimum Python version to require compatibility with (e.g. `'3.10'`). Empty
   *   string disables filtering.
   * @returns The latest version string prefixed with `^`.
   * @pt string
   * @pt string
   * @pt string
   * @rv string
   */
  latestPypiPackageVersionCaret(package, host='pypi.org', python='')::
    '^' + self.latestPypiPackageVersion(package, host, python),
  /**
   * @brief Get the latest version of a PyPI package, prefixed with `>=`.
   *
   * Requires a native function `latestPypiPackageVersion` to be defined in the Jsonnet environment.
   *
   * @param package The PyPI package name.
   * @param host The PyPI-compatible host to query. Defaults to `pypi.org`.
   * @param python Minimum Python version to require compatibility with (e.g. `'3.10'`). Empty
   *   string disables filtering.
   * @returns The latest version string prefixed with `>=`.
   * @pt string
   * @pt string
   * @pt string
   * @rv string
   */
  latestPypiPackageVersionGe(package, host='pypi.org', python='')::
    '>=' + self.latestPypiPackageVersion(package, host, python),
  /**
   * @brief Get the latest version of a PyPI package, prefixed with a tilde (~).
   *
   * Requires a native function `latestPypiPackageVersion` to be defined in the Jsonnet environment.
   *
   * @param package The PyPI package name.
   * @param host The PyPI-compatible host to query. Defaults to `pypi.org`.
   * @param python Minimum Python version to require compatibility with (e.g. `'3.10'`). Empty
   *   string disables filtering.
   * @returns The latest version string prefixed with `~`.
   * @pt string
   * @pt string
   * @pt string
   * @rv string
   */
  latestPypiPackageVersionTilde(package, host='pypi.org', python='')::
    '~' + self.latestPypiPackageVersion(package, host, python),
  /**
   * @brief Get the latest version of a PyPI package.
   *
   * Requires a native function `latestPypiPackageVersion` to be defined in the Jsonnet environment.
   *
   * @param package The PyPI package name.
   * @param host The PyPI-compatible host to query. Defaults to `pypi.org`.
   * @param python Minimum Python version to require compatibility with (e.g. `'3.10'`). Empty
   *   string disables filtering.
   * @returns The latest version string.
   * @pt string
   * @pt string
   * @pt string
   * @rv string
   */
  latestPypiPackageVersion(package, host='pypi.org', python='')::
    std.native('latestPypiPackageVersion')(package, host, python),
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
