local utils = import 'utils.libsonnet';

local cpp_exts = [
  '**/*.cpp',
  '**/*.c++',
  '**/*.cxx',
  '**/*.hpp',
  '**/*.hh',
  '**/*.h++',
  '**/*.hxx',
  '**/*.c',
  '**/*.cc',
  '**/*.h',
];

function(settings)
  {
    jobs: {
      analyze: {
        name: 'Analyze',
        permissions: {
          actions: 'read',
          contents: 'read',
          'security-events': 'write',
        },
        'runs-on': settings.github.codeql.runs_on,
        steps: [
          {
            name: 'Checkout repository',
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
        ] + (if std.length(settings.github.workflows.codeql.apt_packages) > 0 then [{
               name: 'Install dependencies',
               run: 'sudo apt-get update && sudo apt-get install -y ' + std.join(' ', settings.github.workflows.codeql.apt_packages),
             }] else []) + [
          {
            name: 'Initialize CodeQL',
            uses: 'github/codeql-action/init@' + utils.githubLatestActionTag('github', 'codeql-action'),
            with: {
              languages: '${{ matrix.language }}',
            },
          },
          {
            name: 'Perform CodeQL Analysis',
            uses: 'github/codeql-action/analyze@' + utils.githubLatestActionTag('github', 'codeql-action'),
            with: {
              category: '/language:${{matrix.language}}',
            },
          },
        ],
        strategy: {
          'fail-fast': false,
          matrix: {
            language: settings.github.codeql.languages,
          },
        },
      },
    },
    name: 'CodeQL',
    local path_filters = if settings.project_type == 'python' then {
      paths: ['**/*.py', '**/*.pyi'],
    } else if settings.project_type == 'c' then {
      paths: ['**/*.c', '**/*.h'],
    } else if settings.project_type == 'c++' then {
      paths: cpp_exts,
    } else if settings.project_type == 'typescript' then {
      paths: ['**/*.ts', '**/*.tsx', '**/*.js', '**/*.jsx'],
    } else if settings.project_type == 'xcode' then {
      paths: ['**/*.swift'] + cpp_exts,
    } else {},
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
  }
