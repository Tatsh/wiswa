local utils = import 'utils.libsonnet';

/**
 * @file vcpkg-config.libsonnet
 * @namespace vcpkg_config
 * @brief Default configuration for vcpkg registries.
 */
{
  /** @brief Default vcpkg registry configuration. */
  'default-registry': {
    /**
     * @brief Git commit hash for the baseline of the registry. Resolved at regen time to the commit
     * SHA pointed at by the latest non-pre-release GitHub release of `microsoft/vcpkg` so generated
     * manifests pin a published vcpkg snapshot rather than an arbitrary `master` tip.
     */
    baseline: utils.githubRefCommitSha('microsoft',
                                       'vcpkg',
                                       utils.githubLatestReleaseTag('microsoft', 'vcpkg')),
    /** @brief Type of the registry, e.g., "git". */
    kind: 'git',
    /** @brief URL of the vcpkg registry repository. */
    repository: 'https://github.com/microsoft/vcpkg',
  },
  /** @brief Array of vcpkg registries. */
  registries: [
    {
      /** @brief Type of registry, e.g., "artifact". */
      kind: 'artifact',
      /** @brief Location URL of the registry. */
      location: 'https://github.com/microsoft/vcpkg-ce-catalog/archive/refs/heads/main.zip',
      /** @brief Name of the registry. */
      name: 'microsoft',
    },
  ],
}
