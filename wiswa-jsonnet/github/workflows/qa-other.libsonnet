local common = import 'github/workflows/_qa-common.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local is_c_cpp = settings.project_type == 'c' || settings.project_type == 'c++';
  local cpp_paths = ['**/*.c', '**/*.cpp', '**/*.h', '**/*.hpp', '.github/workflows/qa.yml'];
  local apt_steps = if std.length(settings.github.workflows.qa.apt_packages) > 0 then [
    {
      name: 'Install dependencies',
      run: 'sudo apt-get update && sudo apt-get install -y ' + std.join(' ', settings.github.workflows.qa.apt_packages),
    },
  ] else [];
  {
    '.github/workflows/qa.yml': utils.manifestYaml(
      if is_c_cpp then {
        jobs: {
          'clang-format': {
            'runs-on': settings.qa_runs_on,
            steps: [
              common.checkout,
              {
                name: 'Check formatting (clang-format)',
                run: 'clang-format -n %s' % settings.clang_format_args,
              },
            ],
          },
        },
        name: 'QA',
        on: common.on_trigger(settings) + {
          pull_request+: { paths: cpp_paths },
          push+: { paths: cpp_paths },
        },
        permissions: common.permissions,
      } else {
        // Empty QA for project types with no language-specific linting
        jobs: {},
        name: 'QA',
        on: common.on_trigger(settings),
        permissions: common.permissions,
      }
    ),
    '.github/workflows/prettier.yml': utils.manifestYaml(common.prettier(settings)),
    '.github/workflows/markdownlint.yml': utils.manifestYaml(common.markdownlint(settings)),
    '.github/workflows/spelling.yml': utils.manifestYaml(common.spelling(settings)),
  }
