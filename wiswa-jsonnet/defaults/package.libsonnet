local utils = import 'utils.libsonnet';

/**
 * @file package.libsonnet
 * @namespace package_json
 * @brief Default configuration for `package.json` files.
 */
{
  local c_cpp_overrides = [{
    files: [
      '.clang-format',
    ],
    options: {
      parser: 'yaml',
    },
  }],
  local qt_overrides = [
    {
      files: [
        '*.qrc',
        '*.rc',
        '*.ts',
        '*.ui',
      ],
      options: {
        parser: 'xml',
      },
    },
  ],
  local python_deps = { pyright: utils.latestNpmPackageVersionCaret('pyright') },
  local dictionary_update = "rm -f .vscode/dictionary.txt && cspell --no-progress './**/*' './**/.*' 2>&1 | grep -oP '(?<=Unknown word \\()\\S+(?=\\))' | python -c \"import sys; print('\\n'.join(sorted(set(l.strip().lower() for l in sys.stdin if l.strip()))))\" > .vscode/dictionary.txt",
  local python_test_scripts(run_cmd) = {
    test: '%s pytest' % run_cmd,
    'test:cov': 'yarn test --cov . --cov-branch --cov-report html --cov-report term-missing:skip-covered',
  },
  local python_scripts(settings) = {
    local run_cmd = if settings.package_manager == 'uv' then 'uv run' else 'poetry run',
    local fmt_check = if settings.want_yapf then '%s yapf -prd .' % run_cmd
    else '%s ruff format --check .' % run_cmd,
    local fmt_apply = if settings.want_yapf then '%s yapf -ri .' % run_cmd
    else '%s ruff format .' % run_cmd,
    'check-formatting': 'prettier -c . && %s && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2' % fmt_check,
    'check-spelling': "cspell --no-progress './**/*'  './**/.*'",
    'dict:update': dictionary_update,
    format: 'prettier -w . && %s && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2 --fix' % fmt_apply,
    mypy: '%s mypy' % run_cmd,
    qa: 'yarn mypy . && yarn ruff . && yarn check-spelling && yarn check-formatting',
    regen: '%s wiswa' % run_cmd,
    ruff: '%s ruff check' % run_cmd,
    'ruff:fix': '%s ruff check --fix' % run_cmd,
  } + if settings.want_tests then python_test_scripts(
    if settings.package_manager == 'uv' then 'uv run' else 'poetry run'
  ) else {},
  local c_cpp_scripts(settings) = {
    build: 'cmake --preset=default -DBUILD_DOCS=ON && cmake --build build',
    'check-formatting': 'clang-format -n %s && prettier -c . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2' % settings.clang_format_args,
    'check-spelling': 'cspell --no-progress .',
    'dict:update': dictionary_update,
    format: 'clang-format -i %s && prettier -w . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2 --fix' % settings.clang_format_args,
    qa: 'yarn check-spelling && yarn check-formatting',
  },
  typescript_dev_deps(settings):: {
    '@eslint/js': utils.latestNpmPackageVersionCaret('@eslint/js'),
    '@types/node': utils.latestNpmPackageVersionCaret('@types/node'),
    eslint: utils.latestNpmPackageVersionCaret('eslint'),
    'ts-node': utils.latestNpmPackageVersionCaret('ts-node'),
    typedoc: utils.latestNpmPackageVersionCaret('typedoc'),
    'typescript-eslint': utils.latestNpmPackageVersionCaret('typescript-eslint'),
    typescript: utils.latestNpmPackageVersionCaret('typescript'),
  } + if settings.want_tests then {
    '@types/jest': utils.latestNpmPackageVersionCaret('@types/jest'),
    jest: utils.latestNpmPackageVersionCaret('jest'),
    'ts-jest': utils.latestNpmPackageVersionCaret('ts-jest'),
  } else {},
  typescript_scripts(settings):: {
    'check-formatting': 'prettier -c . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2',
    'check-spelling': "cspell --no-progress './**/*'  './**/.*'",
    'dict:update': dictionary_update,
    format: 'prettier -w . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2 --fix',
    qa: 'eslint && yarn check-spelling && yarn check-formatting',
  } + if settings.want_tests then { test: 'jest' } else {},
  local top = self,

  /**
   * @brief Get the content of `package.json` based on the provided settings.
   * @param settings The project settings object containing configuration options.
   * @returns An object representing the content of `package.json`.
   * @pt object
   * @rv object
   */
  get(settings): {
    local man = if settings.want_man then [
      'man/%s.1' % (
        if std.contains(std.stringChars(settings.project_name), '/') then
          std.split(settings.project_name, '/')[1] else settings.project_name
      ),
    ] else [],
    local prettier_c_cpp = if settings.project_type == 'c++' || settings.project_type == 'c' then c_cpp_overrides else [],
    local prettier_cpp = if settings.cmake.uses_qt then qt_overrides else [],
    cspell: {
      cache: { useCache: true },
      dictionaryDefinitions: [
        {
          name: 'main',
          path: '.vscode/dictionary.txt',
        },
      ],
      enableFileTypes: { '*': true },
      enableGlobDot: true,
      files: ['*'],
      ignorePaths: [
        '*.1',
        '*.har',
        '*.lock',
        '.git/**',
        '.yarn/**/*.cjs',
        '.vscode/extensions.json',
        'dist/**',
        'man/**',
      ] + (if settings.export_requirements.enabled && settings.project_type == 'python' then [
             settings.export_requirements.output_filename,
           ] else []),
      language: 'en-GB',
      languageSettings: [
        {
          dictionaries: ['main'],
          languageId: '*',
        },
      ],
      useGitignore: true,
    },
    description: settings.description,
    devDependencies: {
      '@prettier/plugin-xml': utils.latestNpmPackageVersionCaret('@prettier/plugin-xml'),
      cspell: utils.latestNpmPackageVersionCaret('cspell'),
      'markdownlint-cli2': utils.latestNpmPackageVersionCaret('markdownlint-cli2'),
      prettier: utils.latestNpmPackageVersionCaret('prettier'),
      'prettier-plugin-ini': utils.latestNpmPackageVersionCaret('prettier-plugin-ini'),
      'prettier-plugin-sort-json': utils.latestNpmPackageVersionCaret('prettier-plugin-sort-json'),
      'prettier-plugin-toml': utils.latestNpmPackageVersionCaret('prettier-plugin-toml'),
    } + if settings.project_type == 'python' then python_deps else
      {} + if settings.project_type == 'typescript' then top.typescript_dev_deps(settings) else {},
    files: ['LICENSE.txt', 'README.md'] + man,
    'markdownlint-cli2': {
      config: {
        MD024: {
          siblings_only: true,
        },
        MD033: {
          allowed_elements: ['kbd'],
        },
        default: true,
        'line-length': {
          code_blocks: false,
          line_length: settings.line_width,
          tables: false,
        },
      },
      gitignore: true,
      globs: [
        '**/*.md',
        '**/*.mdc',
      ],
      noBanner: true,
      showFound: true,
    },
    prettier: {
      endOfLine: 'lf',
      iniSpaceAroundEquals: true,
      jsonRecursiveSort: true,
      overrides: [
        {
          files: ['package.json'],
          options: {
            parser: 'json',
          },
        },
        {
          files: ['*.json.dist'],
          options: {
            parser: 'json',
          },
        },
        {
          files: ['*.md'],
          options: {
            parser: 'markdown',
          },
        },
      ] + prettier_c_cpp + prettier_cpp,
      plugins: [
        '@prettier/plugin-xml',
        'prettier-plugin-ini',
        'prettier-plugin-sort-json',
        'prettier-plugin-toml',
      ],
      reorderKeys: true,
      printWidth: settings.line_width,
      singleQuote: true,
    },
    scripts: {
      'check-formatting': 'prettier -c . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2',
      'check-spelling': "cspell --no-progress './**/*'  './**/.*'",
      'dict:update': dictionary_update,
      format: 'prettier -w . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2 --fix',
    } + if settings.project_type == 'python' then python_scripts(settings)
    else if settings.project_type == 'c++' || settings.project_type == 'c' then c_cpp_scripts(settings)
    else if settings.project_type == 'typescript' then top.typescript_scripts(settings)
    else {},
  } + (if settings.private then { private: true } else {}),
}
