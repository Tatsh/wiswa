local common = import 'github/workflows/_qa-common.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local is_uv = settings.package_manager == 'uv';
  local run_cmd = if is_uv then 'uv run' else 'poetry run';
  local latest_python =
    settings.supported_python_versions[std.length(settings.supported_python_versions) - 1];
  local python_paths = [
    '**/*.py',
    '**/*.pyi',
    '.github/workflows/qa.yml',
    'pyproject.toml',
    'tests/pyproject.toml',
  ];
  local uv_setup_steps = if is_uv then [
    {
      name: 'Install uv',
      uses: 'astral-sh/setup-uv@' + utils.githubLatestActionTag('astral-sh', 'setup-uv'),
    },
  ] else [
    {
      name: 'Install Poetry',
      run: 'pipx install poetry',
    },
  ];
  local apt_steps = if std.length(settings.github.workflows.qa.apt_packages) > 0 then [
    {
      name: 'Install dependencies',
      run: 'sudo apt-get update && sudo apt-get install -y ' + std.join(' ', settings.github.workflows.qa.apt_packages),
    },
  ] else [];
  local python_setup(version='3.14', matrix=false) = {
    name: if matrix then 'Set up Python ${{ matrix.python-version }}' else 'Set up Python',
    uses: 'actions/setup-python@' + utils.githubLatestActionTag('actions', 'setup-python'),
    with: {
      'python-version': if matrix then '${{ matrix.python-version }}' else version,
    } + if !is_uv then { cache: 'poetry' } else {},
  };
  local install_deps(include_tests=false) = {
    name: if is_uv then 'Install dependencies (uv)' else 'Install dependencies (Poetry)',
    run: if is_uv then (if include_tests then 'uv sync --group dev --group tests --all-extras'
                        else 'uv sync --group dev --all-extras')
    else (if include_tests then 'poetry install --with=dev,tests --all-extras'
          else 'poetry install --with=dev --all-extras'),
  };
  local on_python = common.on_trigger(settings) + {
    pull_request+: { paths: python_paths },
    push+: { paths: python_paths },
  };
  {
    '.github/workflows/qa.yml': utils.manifestYaml({
      jobs: {
        ruff: {
          'runs-on': settings.qa_runs_on,
          steps: [
            common.checkout,
            {
              name: 'Lint with Ruff',
              uses: 'astral-sh/ruff-action@' + utils.githubLatestActionTag('astral-sh', 'ruff-action'),
            },
          ],
        },
        mypy: {
          'runs-on': settings.qa_runs_on,
          steps: [common.checkout] + uv_setup_steps + apt_steps + [
            python_setup(version=latest_python),
            install_deps(include_tests=settings.want_tests),
            {
              name: 'Lint with mypy',
              run: '%s mypy .' % run_cmd,
            },
          ],
        },
        format: {
          'runs-on': settings.qa_runs_on,
          steps: [common.checkout] + uv_setup_steps + apt_steps + [
            python_setup(version=settings.supported_python_versions[0]),
            install_deps(),
            if settings.want_yapf then {
              name: 'Check formatting (YAPF)',
              run: '%s yapf --diff --parallel --recursive .' % run_cmd,
            } else {
              name: 'Check formatting (Ruff)',
              run: '%s ruff format --check .' % run_cmd,
            },
          ],
        },
      } + (if settings.force_eslint then {
             eslint: {
               'runs-on': settings.qa_runs_on,
               steps: [common.checkout] + common.yarn_steps + [
                 {
                   name: 'Lint with ESLint',
                   run: 'yarn eslint',
                 },
               ],
             },
           } else {}),
      name: 'QA',
      on: on_python,
      permissions: common.permissions,
    }),
    '.github/workflows/prettier.yml': utils.manifestYaml(common.prettier(settings)),
    '.github/workflows/markdownlint.yml': utils.manifestYaml(common.markdownlint(settings)),
    '.github/workflows/spelling.yml': utils.manifestYaml(common.spelling(settings)),
  }
