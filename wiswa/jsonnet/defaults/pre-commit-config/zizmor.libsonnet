local utils = import 'utils.libsonnet';

/**
 * @file defaults/pre-commit-config/zizmor.libsonnet
 * @namespace pre_commit_config::zizmor
 * @brief Run zizmor, a static analysis tool for GitHub Actions security. For
 * `.pre-commit-config.yaml`.
 */
{
  /** @brief Hooks. */
  hooks: [
    {
      id: 'zizmor',
    },
  ],
  /** @brief Repository. */
  repo: 'https://github.com/zizmorcore/zizmor-pre-commit',
  /** @brief Revision. */
  rev: utils.githubLatestReleaseTag('zizmorcore', 'zizmor-pre-commit'),
}
