local utils = import 'utils.libsonnet';

/**
 * @file defaults/pre-commit-config/clang-format.libsonnet
 * @namespace pre_commit_config::clang_format
 * @brief clang-format hook configuration for `.pre-commit-config.yaml`.
 */
{
  /** @brief Add `clang-format` hook. */
  hooks: [
    {
      id: 'clang-format',
      types_or: [
        'c',
        'c++',
      ],
    },
  ],
  /** @brief Repository. */
  repo: 'https://github.com/pre-commit/mirrors-clang-format',
  /** @brief Revision. */
  rev: utils.githubLatestReleaseTag('pre-commit', 'mirrors-clang-format'),
}
