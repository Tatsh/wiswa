/**
 * @file yarnrc.libsonnet
 * @namespace yarnrc
 * @brief Default settings for `.yarnrc.yml`.
 */
{
  /** @brief Enable/disable hardened mode. If enabled, breaks Dependabot updates. */
  enableHardenedMode: false,
  /** @brief Enable/disable telemetry collection. */
  enableTelemetry: false,
  /** @brief Node linker to use. */
  nodeLinker: 'node-modules',
  /** @brief Access to use when publishing to the registry. */
  npmPublishAccess: 'public',
  /** @brief Whether to attach a provenance statement when publishing packages to the registry. */
  npmPublishProvenance: true,
  /**
   * @brief List of plugins to load.
   * @var object[]
   */
  plugins: [
    {
      path: '.yarn/plugins/plugin-prettier-after-all-installed.cjs',
    },
  ],
}
