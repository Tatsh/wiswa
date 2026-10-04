local common = import 'github/workflows/_qa-common.libsonnet';

function(settings)
  local cpp_paths = ['**/*.c', '**/*.cc', '**/*.cpp', '**/*.h', '**/*.hpp', '**/*.mm', '.github/workflows/clang-format.yml', '.pre-commit-config.yaml'];
  {
    jobs: {
      'clang-format': {
        'runs-on': settings.qa_runs_on,
        steps: [
          common.checkout,
          // The runner image ships an older clang-format that formats some constructs differently.
          // Run the version the pre-commit hook pins so CI and local checks agree.
          {
            name: 'Check formatting (clang-format)',
            run: |||
              version=$(yq '.repos[] | select(.repo == "https://github.com/pre-commit/mirrors-clang-format") | .rev' .pre-commit-config.yaml)
              if [[ -z "$version" || "$version" == 'null' ]]; then
                echo '::error::No mirrors-clang-format hook in .pre-commit-config.yaml.'
                exit 1
              fi
              pipx run --spec "clang-format==${version#v}" clang-format --version
              pipx run --spec "clang-format==${version#v}" clang-format --dry-run --Werror %s
            ||| % settings.clang_format_args,
            shell: 'bash',
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
  }
