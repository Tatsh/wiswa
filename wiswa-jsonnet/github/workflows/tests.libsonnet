local utils = import 'utils.libsonnet';

function(settings)
  local is_uv = settings.package_manager == 'uv';
  {
    jobs: {
      test: {
        env: {
          GITHUB_TOKEN: '${{ secrets.GITHUB_TOKEN }}',
        },
        'runs-on': settings.tests_run_on,
        steps: [
          {
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
        ] + (if is_uv then [{
               name: 'Install uv',
               uses: 'astral-sh/setup-uv@' + utils.githubLatestActionTag('astral-sh', 'setup-uv'),
             }] else [{
               name: 'Install Poetry',
               run: 'pipx install poetry',
             }]) + (if std.length(settings.github.workflows.tests.apt_packages) > 0 then [{
                      name: 'Install dependencies',
                      run: 'sudo apt-get update && sudo apt-get install -y ' + std.join(' ', settings.github.workflows.tests.apt_packages),
                    }] else []) + [
          {
            name: 'Set up Python ${{ matrix.python-version }}',
            uses: 'actions/setup-python@' + utils.githubLatestActionTag('actions', 'setup-python'),
            with: {
              'python-version': '${{ matrix.python-version }}',
            } + if !is_uv then { cache: 'poetry' } else {},
          },
          {
            name: if is_uv then 'Install dependencies (uv)' else 'Install dependencies (Poetry)',
            run: if is_uv then 'uv sync --group tests --all-extras' else 'poetry install --with=tests --all-extras',
          },
          {
            name: 'Install pytest-action dependencies',
            run: if is_uv then 'uv pip install pytest-md pytest-emoji'
            else 'poetry run pip install pytest-md pytest-emoji',
          },
          {
            name: 'Install dependencies (Yarn)',
            run: 'yarn',
          },
          {
            name: 'Run tests',
            uses: 'pavelzw/pytest-action@' + utils.githubLatestActionTag('pavelzw', 'pytest-action'),
            with: {
              'click-to-expand': true,
              'custom-arguments': '--cov . --cov-branch --cov-report term-missing:skip-covered --cov-report xml',
              'custom-pytest': 'yarn test',
              'job-summary': true,
              'report-title': 'Test Report',
              emoji: true,
              verbose: true,
            },
          },
        ] + (if settings.want_coveralls then [{
               name: 'Coverage',
               'if': "github.event_name != 'pull_request'",
               uses: 'coverallsapp/github-action@' + utils.githubLatestActionTag('coverallsapp', 'github-action'),
               with: {
                 file: 'coverage.xml',
               },
             }] else []),
        strategy: {
          matrix: {
            'python-version': settings.supported_python_versions,
          },
        },
      },
    },
    name: 'Tests',
    on: {
      pull_request: {
        branches: [
          settings.default_branch,
        ],
        paths: [
          '**/*.py',
          '**/*.pyi',
          '.github/workflows/tests.yml',
          'pyproject.toml',
          'uv.lock',
          'poetry.lock',
          'tests/**',
        ],
      },
      push: {
        branches: [
          settings.default_branch,
        ],
        paths: [
          '**/*.py',
          '**/*.pyi',
          '.github/workflows/tests.yml',
          'pyproject.toml',
          'uv.lock',
          'poetry.lock',
          'tests/**',
        ],
      },
    },
    permissions: {
      contents: 'read',
    },
  }
