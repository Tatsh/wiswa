local utils = import 'utils.libsonnet';

/**
 * @file defaults/pre-commit-config/ruff.libsonnet
 * @namespace pre_commit_config::ruff
 * @brief Run Ruff. For `.pre-commit-config.yaml`.
 */
function(settings) {
  // The version the project itself pins, with whatever specifier it carries stripped off. Asking
  // PyPI for the newest release instead lets the hook run a Ruff the project cannot install: `uv`
  // honours `exclude-newer`, so a release published inside that window resolves for the hook and
  // not for the lock file, and every rule added in between fails the commit while local QA passes.
  local pinned = if std.objectHas(settings.python_deps.dev, 'ruff') then
    std.lstripChars(settings.python_deps.dev.ruff, '^~=<>')
  else utils.latestPypiPackageVersion('ruff'),
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
  rev: 'v' + pinned,
}
