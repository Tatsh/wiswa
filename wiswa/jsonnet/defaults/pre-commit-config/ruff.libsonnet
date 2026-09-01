local utils = import 'utils.libsonnet';

/**
 * @file defaults/pre-commit-config/ruff.libsonnet
 * @namespace pre_commit_config::ruff
 * @brief Run Ruff. For `.pre-commit-config.yaml`.
 */
function(settings) {
  // The version the project itself pins. Asking PyPI for the newest release instead lets the hook
  // run a Ruff the project cannot install: `uv` honours `exclude-newer`, so a release published
  // inside that window resolves for the hook and not for the lock file, and every rule added in
  // between fails the commit while local QA passes.
  local declared = if std.objectHas(settings.python_deps.dev, 'ruff') then
    settings.python_deps.dev.ruff
  else null,
  // A dependency may be written as a bare specifier or as an object carrying one. An array of
  // them names no single release, so there is nothing there to pin a hook to.
  local specifier = if std.isString(declared) then declared
  else if std.isObject(declared) && std.objectHas(declared, 'version') then declared.version
  else '',
  // Take the first constraint of a range: it is the oldest Ruff the project accepts, and a hook
  // behind the project is harmless where one ahead of it is not.
  local pinned = local floor = std.lstripChars(std.split(specifier, ',')[0], '^~=<> ');
                if std.length(floor) > 0 then floor else utils.latestPypiPackageVersion('ruff'),
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
