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
   * If `settings.want_docs` and `settings.want_tests` are both true, the hook will include the
   * groups `dev`, `docs`, and `tests`. If only `settings.want_docs` is true, it will include `dev`
   * and `docs`. If only `settings.want_tests` is true, it will include `dev` and `tests`. The base
   * case is to include only the `dev` group.
   */
  get(settings):: {
    local with_groups = if settings.want_docs && settings.want_tests then 'dev,docs,tests' else
      if settings.want_docs then 'dev,docs' else
        if settings.want_tests then 'dev,tests' else 'dev',
    hooks: [
      {
        args: [
          '--all-extras',
          '-f',
          'requirements.txt',
          '-o',
          'requirements.txt',
          '--with=%s' % with_groups,
          '--without-hashes',
        ],
        id: 'poetry-export',
      },
    ],
    repo: 'https://github.com/python-poetry/poetry-plugin-export',
    rev: utils.githubLatestReleaseTag('python-poetry', 'poetry-plugin-export'),
  },
}
