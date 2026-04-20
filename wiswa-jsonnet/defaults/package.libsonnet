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
  local python_npm_dev_deps(settings) = if settings.want_pyright then {
    pyright: utils.latestNpmPackageVersionCaret('pyright'),
  } else {},
  // tr arguments need to be quoted or Yarn will not handle it correctly.
  local dictionary_update = "rm -f .vscode/dictionary.txt && cspell lint --no-progress --no-summary --unique --words-only | tr '[:upper:]' '[:lower:]' | sort -u > .vscode/dictionary.txt",
  local python_test_scripts(run_cmd) = {
    test: '%s pytest' % run_cmd,
    'test:cov': 'yarn test --cov . --cov-branch --cov-report html --cov-report term-missing:skip-covered',
  },
  local python_scripts(settings) =
    local run_cmd = if settings.package_manager == 'uv' then 'uv run' else 'poetry run';
    local fmt_check = if settings.want_yapf then '%s yapf --diff --parallel --recursive .' % run_cmd
    else '%s ruff format --check .' % run_cmd;
    local fmt_apply = if settings.want_yapf then '%s yapf --in-place --parallel --recursive .' % run_cmd
    else '%s ruff format .' % run_cmd;
    local qa_pyright = if settings.github.workflows.qa.allow_pyright_failure then
      '{ yarn pyright || true; }' else 'yarn pyright';
    local qa_ty = if settings.github.workflows.qa.allow_ty_failure then
      '{ uv run ty check || true; }' else 'uv run ty check';
    local qa_steps = ['yarn mypy .']
                     + (if settings.want_pyright then [qa_pyright] else [])
                     + (if settings.want_ty then [qa_ty] else [])
                     + ['yarn ruff .', 'yarn check-spelling', 'yarn check-formatting'];
    {
      'check-formatting': 'prettier --check . && %s && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2' % fmt_check,
      'check-spelling': 'cspell --no-progress',
      'dict:update': dictionary_update,
      format: 'prettier --write . && %s && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2 --fix' % fmt_apply,
      mypy: '%s mypy' % run_cmd,
      qa: std.join(' && ', qa_steps),
      regen: '%s wiswa' % run_cmd,
      ruff: '%s ruff check' % run_cmd,
      'ruff:fix': '%s ruff check --fix' % run_cmd,
    } + (
      if settings.want_tests then python_test_scripts(run_cmd) else {}
    )
    + (if settings.want_ty then { ty: '%s ty check' % run_cmd } else {}),
  local c_cpp_scripts(settings) = {
    build: 'cmake --preset=default -DBUILD_DOCS=ON && cmake --build build',
    'check-formatting': 'clang-format --dry-run %s && prettier --check . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2' % settings.clang_format_args,
    'check-spelling': 'cspell --no-progress .',
    'dict:update': dictionary_update,
    format: 'clang-format -i %s && prettier --write . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2 --fix' % settings.clang_format_args,
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
    'check-formatting': 'prettier --check . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2',
    'check-spelling': 'cspell --no-progress',
    'dict:update': dictionary_update,
    format: 'prettier --write . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2 --fix',
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
      files: ['**'],
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
    } + if settings.project_type == 'python' then python_npm_dev_deps(settings) else
      {} + if settings.project_type == 'typescript' then top.typescript_dev_deps(settings) else {},
    // GitHub's default `ubuntu-latest` runner images ship Node 20. Declaring it here lets
    // yarn/npm warn or refuse to install packages (for example cspell >=10 which requires
    // Node 22) that would break on that runtime.
    engines: { node: '>=20' },
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
        // This is here so package.json is not treated specially.
        {
          files: ['*.json.dist', 'package.json'],
          options: {
            parser: 'json',
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
      'check-formatting': 'prettier --check . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2',
      'check-spelling': 'cspell --no-progress',
      'dict:update': dictionary_update,
      format: 'prettier --write . && markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2 --fix',
    } + if settings.project_type == 'python' then python_scripts(settings)
    else if settings.project_type == 'c++' || settings.project_type == 'c' then c_cpp_scripts(settings)
    else if settings.project_type == 'typescript' then top.typescript_scripts(settings)
    else {},
  } + (if settings.private then { private: true } else {}),
}
