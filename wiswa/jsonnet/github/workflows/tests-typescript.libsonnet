local cache_yarn = import 'github/workflows/_cache-yarn.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local ts_paths = [
    '**/*.cjs',
    '**/*.js',
    '**/*.jsx',
    '**/*.mjs',
    '**/*.ts',
    '**/*.tsx',
    '.github/workflows/tests.yml',
    'package.json',
    'tsconfig.json',
  ];
  {
    jobs: {
      test: {
        'runs-on': settings.tests_run_on,
        steps: [
          {
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
        ] + (if std.length(settings.github.workflows.tests.apt_packages) > 0 then [{
               name: 'Install dependencies',
               run: 'sudo apt-get update && sudo apt-get install -y ' + std.join(' ', settings.github.workflows.tests.apt_packages),
             }] else []) + [
          cache_yarn,
          {
            name: 'Install dependencies (Yarn)',
            run: 'yarn',
          },
          {
            name: 'Tests',
            run: 'yarn vitest run --coverage',
          },
        ] + (if settings.want_coveralls then [{
               name: 'Coveralls',
               'if': "github.event_name != 'pull_request'",
               uses: 'coverallsapp/github-action@' + utils.githubLatestActionTag('coverallsapp', 'github-action'),
             }] else []),
      },
    },
    name: 'Tests',
    on: {
      pull_request: {
        branches: [settings.default_branch],
        paths: ts_paths,
      },
      push: {
        branches: [settings.default_branch],
        paths: ts_paths,
      },
    },
    permissions: {
      contents: 'read',
    },
  }
