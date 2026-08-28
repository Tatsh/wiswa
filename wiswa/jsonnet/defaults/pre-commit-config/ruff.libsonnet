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
  // Derived from the pinned dev dependency rather than the latest tag, so the hook and the project
  // enforce the same rule set. A newer hook applies rules the pinned Ruff does not implement, which
  // fails the commit while local QA passes.
  rev: 'v' + utils.latestPypiPackageVersion('ruff'),
}
