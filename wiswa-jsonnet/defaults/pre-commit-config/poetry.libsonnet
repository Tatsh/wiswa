local utils = import 'utils.libsonnet';

/**
 * @file defaults/pre-commit-config/poetry.libsonnet
 * @namespace pre_commit_config::poetry
 * @brief Poetry hook configuration for `.pre-commit-config.yaml`.
 * @sa [Poetry](https://python-poetry.org/)
 */
{
  /** @brief Hooks. */
  hooks: [
    {
      id: 'poetry-check',
      stages: [
        'pre-push',
      ],
    },
    {
      id: 'poetry-lock',
      stages: [
        'pre-push',
      ],
    },
    {
      args: [
        '--all-groups',
      ],
      id: 'poetry-install',
    },
  ],
  /** @brief Repository. */
  repo: 'https://github.com/python-poetry/poetry',
  /** @brief Revision. */
  rev: utils.githubLatestReleaseTag('python-poetry', 'poetry'),
}
