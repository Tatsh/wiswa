local utils = import 'utils.libsonnet';

/**
 * @file defaults/pre-commit-config/github.libsonnet
 * @namespace pre_commit_config::github
 * @brief Check schemas for JSON and YAML files. For `.pre-commit-config.yaml`.
 */
{
  /** @brief Hooks. */
  hooks: [
    {
      id: 'check-github-actions',
    },
    {
      id: 'check-github-workflows',
    },
    {
      args: [
        '--schemafile',
        'https://json.schemastore.org/package.json',
      ],
      files: '^package\\.json$',
      id: 'check-jsonschema',
      name: 'validate package.json',
    },
  ],
  /** @brief Repository. */
  repo: 'https://github.com/python-jsonschema/check-jsonschema',
  /** @brief Revision. */
  rev: utils.githubLatestReleaseTag('python-jsonschema', 'check-jsonschema'),
}
