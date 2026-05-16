local utils = import 'utils.libsonnet';

/**
 * @file defaults/pre-commit-config/ruff.libsonnet
 * @namespace pre_commit_config::ruff
 * @brief Run Ruff. For `.pre-commit-config.yaml`.
 */
function(settings) {
  hooks: [
    {
      args: ['--fix'],
      id: 'ruff-check',
    },
  ] + (if !settings.want_yapf then [
         {
           id: 'ruff-format',
         },
       ] else []),
  repo: 'https://github.com/astral-sh/ruff-pre-commit',
  rev: utils.githubLatestReleaseTag('astral-sh', 'ruff-pre-commit'),
}
