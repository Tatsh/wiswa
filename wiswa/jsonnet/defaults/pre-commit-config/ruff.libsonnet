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
  // Derived from the same PyPI lookup as the dev dependency, so the hook and the project enforce
  // the same rule set rather than drifting apart on separate schedules. A hook ahead of the project
  // applies rules the installed Ruff does not implement, failing the commit while local QA passes.
  rev: 'v' + utils.latestPypiPackageVersion('ruff'),
}
