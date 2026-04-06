local eslint = import 'defaults/pre-commit-config/eslint.libsonnet';

/**
 * @file defaults/pre-commit-config/local.libsonnet
 * @namespace pre_commit_config::local
 * @brief Local hook configuration for `.pre-commit-config.yaml`.
 */
{
  local python_hooks(settings) = [{
    entry: '%s ruff check --fix --exit-non-zero-on-fix' % (
      if settings.package_manager == 'uv' then 'uv run' else 'poetry run'
    ),
    id: 'fix-ruff',
    language: 'system',
    name: 'check Python files have Ruff fixes applied',
    require_serial: true,
    types_or: [
      'python',
      'pyi',
    ],
  }],
  local uv_export_hook(settings) =
    if settings.package_manager == 'uv' && settings.export_requirements.enabled then
      local er = settings.export_requirements;
      local args = ['uv', 'export']
                   + (if er.format != 'requirements.txt' then ['--format', er.format] else [])
                   + (if er.all_packages then ['--all-packages'] else [])
                   + std.flatMap(function(p) ['--package', p], er.package)
                   + std.flatMap(function(p) ['--prune', p], er.prune)
                   + std.flatMap(function(e) ['--extra', e], er.extra)
                   + (if er.all_extras then ['--all-extras'] else [])
                   + std.flatMap(function(e) ['--no-extra', e], er.no_extra)
                   + (if er.no_dev then ['--no-dev'] else [])
                   + (if er.only_dev then ['--only-dev'] else [])
                   + std.flatMap(function(g) ['--group', g], er.group)
                   + std.flatMap(function(g) ['--no-group', g], er.no_group)
                   + (if er.no_default_groups then ['--no-default-groups'] else [])
                   + std.flatMap(function(g) ['--only-group', g], er.only_group)
                   + (if er.all_groups then ['--all-groups'] else [])
                   + (if er.no_annotate then ['--no-annotate'] else [])
                   + (if er.no_header then ['--no-header'] else [])
                   + (if er.no_editable then ['--no-editable'] else [])
                   + (if er.no_hashes || !er.with_hashes then ['--no-hashes'] else [])
                   + ['--output-file', er.output_filename]
                   + (if er.no_emit_project then ['--no-emit-project'] else [])
                   + (if er.no_emit_workspace then ['--no-emit-workspace'] else [])
                   + (if er.no_emit_local then ['--no-emit-local'] else [])
                   + std.flatMap(function(p) ['--no-emit-package', p], er.no_emit_package)
                   + (if er.locked then ['--locked'] else [])
                   + (if er.frozen then ['--frozen'] else [])
                   + (if er.script != '' then ['--script', er.script] else []);
      [{
        entry: std.join(' ', args),
        files: '^(uv\\.lock|pyproject\\.toml)$',
        id: 'uv-export',
        language: 'system',
        name: 'check %s matches uv.lock' % er.output_filename,
        pass_filenames: false,
      }]
    else [],
  local eslint_hooks = [eslint],
  /**
   * @brief Generate local hook configuration based on settings.
   * @param settings Object containing configuration settings that may influence the generated
   * hooks.
   * @returns An object containing the hooks to be added to the pre-commit configuration.
   */
  get(settings):: {
    hooks: [
      {
        entry: 'yarn install --check-cache --immutable',
        files: '^package\\.json$',
        id: 'yarn-check-lock',
        language: 'system',
        name: 'check yarn.lock is up-to-date',
        pass_filenames: false,
      },
      {
        always_run: true,
        entry: 'yarn install',
        id: 'yarn-install',
        language: 'system',
        name: 'ensure Node packages are installed for this branch',
        pass_filenames: false,
        stages: [
          'post-checkout',
          'post-merge',
        ],
      },
      {
        entry: 'yarn prettier --write',
        exclude: '((requirements|robots).txt|Dockerfile.*|..*ignore|.(coveragerc|gitattributes)|.*.(csv|lock|resource|robot)|pylock.*\\.toml|CODEOWNERS|py.typed)$',
        exclude_types: [
          'binary',
          'dockerfile',
          'pyi',
          'python',
          'rst',
          'plain-text',
          'shell',
        ],
        id: 'fix-formatting-prettier',
        language: 'system',
        name: 'check files are formatted with Prettier',
      },
    ] + (if settings.project_type == 'python' then python_hooks(settings) else []) + uv_export_hook(settings) + (if settings.force_eslint then eslint_hooks else []) + [
      {
        entry: 'yarn markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2 --fix',
        id: 'fix-formatting-markdown',
        language: 'system',
        name: 'check Markdown files are formatted',
        types_or: [
          'markdown',
        ],
      },
    ] + (if settings.cspell_pre_commit_hook then [{
        entry: 'yarn cspell --no-progress --no-must-find-files --no-summary',
        id: 'cspell',
        language: 'node',
        name: 'check spelling',
        types: ['text'],
      }] else []),
    repo: 'local',
  },
}
