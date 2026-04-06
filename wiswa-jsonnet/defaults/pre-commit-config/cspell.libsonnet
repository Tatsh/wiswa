local utils = import 'utils.libsonnet';

/**
 * @file defaults/pre-commit-config/cspell.libsonnet
 * @namespace pre_commit_config::cspell
 * @brief cspell hook configuration for `.pre-commit-config.yaml`.
 */
{
  /** @brief Hooks. */
  hooks: [
    {
      id: 'cspell',
    },
  ],
  /** @brief Repository. */
  repo: 'https://github.com/streetsidesoftware/cspell-cli',
  /** @brief Revision. */
  rev: utils.githubLatestReleaseTag('streetsidesoftware', 'cspell-cli', npmMinReleaseAge=true),
}
