local common = import 'github/workflows/_qa-common.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local ts_paths = [
    '**/*.cjs',
    '**/*.js',
    '**/*.jsx',
    '**/*.mjs',
    '**/*.ts',
    '**/*.tsx',
    '.github/workflows/qa.yml',
    'package.json',
    'tsconfig.json',
  ];
  local on_ts = common.on_trigger(settings) + {
    pull_request+: { paths: ts_paths },
    push+: { paths: ts_paths },
  };
  local apt_steps = if std.length(settings.github.workflows.qa.apt_packages) > 0 then [
    {
      name: 'Install dependencies',
      run: 'sudo apt-get update && sudo apt-get install -y ' + std.join(' ', settings.github.workflows.qa.apt_packages),
    },
  ] else [];
  {
    '.github/workflows/qa.yml': utils.manifestYaml({
      jobs: {
        eslint: {
          'runs-on': settings.qa_runs_on,
          steps: [common.checkout] + apt_steps + common.yarn_steps + [
            {
              name: 'ESLint',
              run: 'yarn eslint',
            },
          ],
        },
      },
      name: 'QA',
      on: on_ts,
      permissions: common.permissions,
    }),
    '.github/workflows/prettier.yml': utils.manifestYaml(common.prettier(settings)),
    '.github/workflows/markdownlint.yml': utils.manifestYaml(common.markdownlint(settings)),
    '.github/workflows/spelling.yml': utils.manifestYaml(common.spelling(settings)),
  }
