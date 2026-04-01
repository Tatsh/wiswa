local utils = import 'utils.libsonnet';

/**
 * @file defaults/pre-commit-config/poetry-plugin-export.libsonnet
 * @namespace pre_commit_config::poetry_plugin_export
 * @brief Poetry export plugin hook configuration for `.pre-commit-config.yaml`.
 * @sa [poetry-plugin-export GitHub Repository](https://github.com/python-poetry/poetry-plugin-export/)
 */
{
  /**
   * @brief Generate the poetry export plugin hook configuration based on settings.
   * @param settings Object containing configuration settings that may influence the generated
   * hooks.
   * @returns An object containing the hooks to be added to the pre-commit configuration.
   *
   * Options are read from ``settings.export_requirements`` and translated to
   * Poetry equivalents where possible.  uv-only flags are silently ignored.
   */
  get(settings):: {
    local er = settings.export_requirements,
    local group_list =
      (if !er.no_dev then ['dev'] else [])
      + (if er.all_groups then
           (if settings.want_docs then ['docs'] else [])
           + (if settings.want_tests then ['tests'] else [])
         else er.group),
    local with_groups = std.join(',', group_list),
    hooks: [
      {
        args:
          (if er.all_extras then ['--all-extras']
           else std.flatMap(function(e) ['--extras=%s' % e], er.extra))
          + ['-f', er.format, '-o', er.output_filename]
          + (if std.length(with_groups) > 0 then ['--with=%s' % with_groups] else [])
          + (if er.only_dev then ['--only=dev'] else [])
          + std.flatMap(function(g) ['--only=%s' % g], er.only_group)
          + std.flatMap(function(g) ['--without=%s' % g], er.no_group)
          + (if er.no_hashes || !er.with_hashes then ['--without-hashes'] else []),
        id: 'poetry-export',
      },
    ],
    repo: 'https://github.com/python-poetry/poetry-plugin-export',
    rev: utils.githubLatestReleaseTag('python-poetry', 'poetry-plugin-export'),
  },
}
