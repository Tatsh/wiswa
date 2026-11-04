local utils = import 'utils.libsonnet';

local actions_exts = [
  '.github/workflows/*.yml',
  '.github/workflows/*.yaml',
  '**/action.yml',
  '**/action.yaml',
];
local cpp_exts = [
  '**/*.cpp',
  '**/*.cxx',
  '**/*.hpp',
  '**/*.hh',
  '**/*.hxx',
  '**/*.c',
  '**/*.cc',
  '**/*.h',
];

function(settings)
  local scoped = std.length(settings.static_analysis_paths) > 0 &&
                 (std.member(settings.github.codeql.languages, 'c-cpp') ||
                  std.member(settings.github.codeql.languages, 'cpp'));
  {
    concurrency: utils.ciConcurrency,
    jobs: {
      analyze: (if std.length(settings.github.codeql.env) > 0 then {
                  env: settings.github.codeql.env,
                } else {}) + {
        name: 'Analyze',
        permissions: {
          actions: 'read',
          contents: 'read',
          'security-events': 'write',
        },
        'runs-on': settings.github.codeql.runs_on,
        steps: [
          utils.checkout({ name: 'Checkout repository' }),
        ] + (if std.length(settings.github.workflows.codeql.apt_packages) > 0 then [{
               name: 'Install dependencies',
               run: 'sudo apt-get update && sudo apt-get install -y ' + std.join(' ', settings.github.workflows.codeql.apt_packages),
             }] else []) + [
          {
            name: 'Initialize CodeQL',
            uses: 'github/codeql-action/init@' + utils.githubLatestActionSha('github', 'codeql-action'),
            with: {
              'build-mode': settings.github.codeql.build_mode,
              languages: '${{ matrix.language }}',
            },
          },
          {
            name: 'Perform CodeQL Analysis',
            uses: 'github/codeql-action/analyze@' + utils.githubLatestActionSha('github', 'codeql-action'),
            with: {
              category: '/language:${{matrix.language}}',
            } + if scoped then { upload: false, output: '${{ runner.temp }}/codeql-sarif' } else {},
          },
        ] + (if scoped then [
               {
                 name: 'Restrict native findings to project sources',
                 'if': "matrix.language == 'c-cpp' || matrix.language == 'cpp'",
                 run: 'python3 .github/scripts/static-analysis.py --sarif "$RUNNER_TEMP/codeql-sarif"',
               },
               {
                 name: 'Upload CodeQL results',
                 uses: 'github/codeql-action/upload-sarif@' + utils.githubLatestActionSha('github', 'codeql-action'),
                 with: {
                   sarif_file: '${{ runner.temp }}/codeql-sarif',
                   category: '/language:${{matrix.language}}',
                 },
               },
             ] else []),
        strategy: {
          'fail-fast': false,
          matrix: {
            language: settings.github.codeql.languages,
          },
        },
      },
    },
    name: if settings.github.codeql.languages == ['actions'] then 'CodeQL Actions' else 'CodeQL',
    local languages = settings.github.codeql.languages,
    local lang_filters = if std.member(languages, 'python') then {
      paths: ['**/*.py', '**/*.pyi'],
    } else {},
    local cpp_filters = if std.member(languages, 'c-cpp') then {
      paths: cpp_exts,
    } else {},
    local js_filters = if std.member(languages, 'javascript-typescript') then {
      paths: ['**/*.ts', '**/*.tsx', '**/*.js', '**/*.jsx'],
    } else {},
    local with_actions = if std.member(settings.github.codeql.languages, 'actions')
    then { paths+: actions_exts }
    else {},
    local paths = std.get(lang_filters, 'paths', []) + std.get(cpp_filters, 'paths', []) +
                  std.get(js_filters, 'paths', []) + std.get(with_actions, 'paths', []),
    local path_filters = if std.length(paths) > 0 then { paths: paths } else {},
    on: {
      pull_request: {
        branches: [
          settings.default_branch,
        ],
      } + path_filters,
      push: {
        branches: [
          settings.default_branch,
        ],
      } + path_filters,
      schedule: [
        {
          cron: '15 4 * * 3',
        },
      ],
    },
    permissions: {},
  }
