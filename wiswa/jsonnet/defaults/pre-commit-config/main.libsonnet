local utils = import 'utils.libsonnet';

/**
 * @file defaults/pre-commit-config/main.libsonnet
 * @namespace pre_commit_config::main
 * @brief Main configuration for `.pre-commit-config.yaml` with various hooks.
 * @sa [pre-commit Hooks](https://pre-commit.com/hooks.html)
 */
{
  /**
   * @brief Generate the main pre-commit hook configuration based on settings.
   * @param settings Object containing configuration settings that may influence the generated
   * hooks.
   * @returns An object containing the hooks to be added to the pre-commit configuration.
   */
  get(settings):: {
    hooks: [
      {
        exclude: 'yarn-\\d+.*\\.cjs$',
        id: 'check-added-large-files',
      },
      {
        id: 'check-ast',
      },
      {
        id: 'check-builtin-literals',
      },
      {
        id: 'check-case-conflict',
      },
      {
        id: 'check-executables-have-shebangs',
      },
      {
        id: 'check-merge-conflict',
      },
      {
        id: 'check-shebang-scripts-are-executable',
      } + (if settings.project_type == 'typescript' then { exclude: 'src/index\\.ts$' } else {}),
      {
        id: 'check-symlinks',
      },
      {
        id: 'check-toml',
      },
      {
        id: 'debug-statements',
      },
      {
        id: 'destroyed-symlinks',
      },
      {
        id: 'detect-aws-credentials',
      },
      {
        id: 'detect-private-key',
      },
      {
        exclude: '^vcpkg.*\\.json$',
        id: 'end-of-file-fixer',
      },
      {
        files: '^(\\.(docker|eslint|prettier)ignore|CODEOWNERS|\\.gitattributes)$',
        id: 'file-contents-sorter',
      },
      {
        id: 'fix-byte-order-marker',
      },
      {
        id: 'mixed-line-ending',
      },
    ],
    /** Repository. */
    repo: 'https://github.com/pre-commit/pre-commit-hooks',
    /** Revision. */
    rev: utils.githubLatestReleaseTag('pre-commit', 'pre-commit-hooks'),
  },
}
