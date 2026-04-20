local common = import 'github/workflows/_qa-common.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local is_c_cpp = settings.project_type == 'c' || settings.project_type == 'c++';
  local cpp_paths = ['**/*.c', '**/*.cc', '**/*.cpp', '**/*.h', '**/*.hpp', '.github/workflows/clang-format.yml'];
  local clang_format_workflow = {
    jobs: {
      'clang-format': {
        'runs-on': settings.qa_runs_on,
        steps: [
          common.checkout,
          {
            name: 'Check formatting (clang-format)',
            run: 'clang-format --dry-run %s' % settings.clang_format_args,
          },
        ],
      },
    },
    name: 'clang-format',
    on: common.on_trigger(settings) + {
      pull_request+: { paths: cpp_paths },
      push+: { paths: cpp_paths },
    },
    permissions: common.permissions,
  };
  {
    '.github/workflows/prettier.yml': utils.manifestYaml(common.prettier(settings)),
    '.github/workflows/markdownlint.yml': utils.manifestYaml(common.markdownlint(settings)),
    '.github/workflows/spelling.yml': utils.manifestYaml(common.spelling(settings)),
  } + (if is_c_cpp then {
         '.github/workflows/clang-format.yml': utils.manifestYaml(clang_format_workflow),
       } else {})
