local cache_yarn = import 'github/workflows/_cache-yarn.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local is_uv = settings.package_manager == 'uv';
  local run_cmd = if is_uv then 'uv run' else 'poetry run';
  local fmt_check_id = if settings.want_yapf then 'yapf' else 'ruff-format';
  local fmt_check_cmd = if settings.want_yapf then '%s yapf -prd .' % run_cmd
  else '%s ruff format --check .' % run_cmd;
  local eslint_ids = if settings.force_eslint then ['eslint'] else [];
  local python_check_ids = ['ruff', 'mypy', fmt_check_id];
  local always_check_ids = eslint_ids + ['prettier', 'markdownlint', 'spelling'];
  local check_ids = python_check_ids + always_check_ids;
  local check_lines = std.join(' &&\n', [
    if std.member(python_check_ids, id) then
      '([ "${{ needs.changes.outputs.python }}" != "true" ] || [ "${{ steps.%s.outcome }}" = "success" ])' % id
    else
      '[ "${{ steps.%s.outcome }}" = "success" ]' % id
    for id in check_ids
  ]);
  {
    jobs: {
      changes: {
        'runs-on': settings.qa_runs_on,
        outputs: {
          python: '${{ steps.filter.outputs.python }}',
        },
        steps: [
          {
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
          {
            id: 'filter',
            uses: 'dorny/paths-filter@' + utils.githubLatestActionTag('dorny', 'paths-filter'),
            with: {
              filters: |||
                python:
                  - '**/*.py'
                  - '**/*.pyi'
                  - '**/*.toml'
              |||,
            },
          },
        ],
      },
      qa: {
        needs: 'changes',
        'runs-on': settings.qa_runs_on,
        steps: [
          {
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
        ] + (if is_uv then [{
               'if': "needs.changes.outputs.python == 'true'",
               name: 'Install uv',
               uses: 'astral-sh/setup-uv@' + utils.githubLatestActionTag('astral-sh', 'setup-uv'),
             }] else [{
               'if': "needs.changes.outputs.python == 'true'",
               name: 'Install Poetry',
               run: 'pipx install poetry',
             }]) + (if std.length(settings.github.workflows.qa.apt_packages) > 0 then [{
                      'if': "needs.changes.outputs.python == 'true'",
                      name: 'Install dependencies',
                      run: 'sudo apt-get update && sudo apt-get install -y ' + std.join(' ', settings.github.workflows.qa.apt_packages),
                    }] else []) + [
          {
            'if': "needs.changes.outputs.python == 'true'",
            name: 'Set up Python ${{ matrix.python-version }}',
            uses: 'actions/setup-python@' + utils.githubLatestActionTag('actions', 'setup-python'),
            with: {
              'python-version': '${{ matrix.python-version }}',
            } + if !is_uv then { cache: 'poetry' } else {},
          },
          {
            'if': "needs.changes.outputs.python == 'true'",
            name: if is_uv then 'Install dependencies (uv)' else 'Install dependencies (Poetry)',
            run: if is_uv then (if settings.want_tests then 'uv sync --group dev --group tests --all-extras'
                                else 'uv sync --group dev --all-extras')
            else (if settings.want_tests then 'poetry install --with=dev,tests --all-extras'
                  else 'poetry install --with=dev --all-extras'),
          },
          cache_yarn,
          {
            name: 'Install dependencies (Yarn)',
            run: 'yarn',
          },
          {
            'continue-on-error': true,
            'if': "needs.changes.outputs.python == 'true'",
            id: 'ruff',
            name: 'Lint with Ruff',
            uses: 'astral-sh/ruff-action@' + utils.githubLatestActionTag('astral-sh', 'ruff-action'),
          },
          {
            'continue-on-error': true,
            'if': "needs.changes.outputs.python == 'true'",
            id: 'mypy',
            name: 'Lint with mypy',
            run: 'yarn mypy .',
          },
        ] + (if settings.force_eslint then [
               {
                 'continue-on-error': true,
                 id: 'eslint',
                 name: 'Lint with ESLint',
                 run: 'yarn eslint',
               },
             ] else []) + [
          {
            'continue-on-error': true,
            id: 'prettier',
            name: 'Check formatting (Prettier)',
            run: 'yarn prettier -c .',
          },
          {
            'continue-on-error': true,
            'if': "needs.changes.outputs.python == 'true'",
            id: fmt_check_id,
            name: if settings.want_yapf then 'Check formatting (YAPF)' else 'Check formatting (Ruff)',
            run: fmt_check_cmd,
          },
          {
            'continue-on-error': true,
            id: 'markdownlint',
            name: 'Check formatting (markdownlint)',
            run: 'yarn markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2',
          },
          {
            'continue-on-error': true,
            id: 'spelling',
            name: 'Check spelling',
            run: 'yarn check-spelling',
          },
          {
            'if': 'always()',
            name: 'Check results',
            run: |||
              %(checks)s
            ||| % { checks: check_lines },
          },
        ],
        strategy: {
          matrix: {
            'python-version': settings.supported_python_versions,
          },
        },
      },
    },
    name: 'QA',
    on: {
      pull_request: {
        branches: [
          settings.default_branch,
        ],
      },
      push: {
        branches: [
          settings.default_branch,
        ],
      },
    },
    permissions: {
      contents: 'read',
    },
  }
