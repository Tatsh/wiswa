local utils = import 'utils.libsonnet';

/**
 * @file defaults/pre-commit-config/uv.libsonnet
 * @namespace pre_commit_config::uv
 * @brief uv hook configuration for `.pre-commit-config.yaml`.
 * @sa [uv](https://docs.astral.sh/uv/)
 */
{
  /** @brief Hooks. */
  hooks: [
    {
      id: 'uv-lock',
      stages: [
        'pre-push',
      ],
    },
    {
      args: [
        '--all-groups',
        '--frozen',
      ],
      id: 'uv-sync',
    },
  ],
  /** @brief Repository. */
  repo: 'https://github.com/astral-sh/uv-pre-commit',
  /** @brief Revision. */
  rev: utils.githubLatestReleaseTag('astral-sh', 'uv'),
}
