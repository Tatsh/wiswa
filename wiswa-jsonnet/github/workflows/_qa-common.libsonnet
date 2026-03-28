local cache_yarn = import 'github/workflows/_cache-yarn.libsonnet';
local utils = import 'utils.libsonnet';

{
  local checkout = {
    uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
  },
  local yarn_steps = [
    cache_yarn,
    {
      name: 'Install dependencies (Yarn)',
      run: 'yarn',
    },
  ],
  local on_trigger(settings) = {
    pull_request: {
      branches: [settings.default_branch],
    },
    push: {
      branches: [settings.default_branch],
    },
  },
  local permissions = { contents: 'read' },

  checkout: checkout,
  yarn_steps: yarn_steps,
  on_trigger: on_trigger,
  permissions: permissions,

  prettier(settings): {
    jobs: {
      prettier: {
        'runs-on': settings.qa_runs_on,
        steps: [checkout] + yarn_steps + [
          {
            name: 'Check formatting (Prettier)',
            run: 'yarn prettier -c .',
          },
        ],
      },
    },
    name: 'Prettier',
    on: on_trigger(settings) + {
      pull_request+: {
        paths: [
          '**/*.css',
          '**/*.html',
          '**/*.json',
          '**/*.md',
          '**/*.mdc',
          '**/*.scss',
          '**/*.toml',
          '**/*.xml',
          '**/*.yaml',
          '**/*.yml',
          '.github/workflows/prettier.yml',
          '.prettierignore',
        ],
      },
      push+: {
        paths: [
          '**/*.css',
          '**/*.html',
          '**/*.json',
          '**/*.md',
          '**/*.mdc',
          '**/*.scss',
          '**/*.toml',
          '**/*.xml',
          '**/*.yaml',
          '**/*.yml',
          '.github/workflows/prettier.yml',
          '.prettierignore',
        ],
      },
    },
    permissions: permissions,
  },

  markdownlint(settings): {
    jobs: {
      markdownlint: {
        'runs-on': settings.qa_runs_on,
        steps: [checkout] + yarn_steps + [
          {
            name: 'Check formatting (markdownlint)',
            run: 'yarn markdownlint-cli2 --config package.json --configPointer /markdownlint-cli2',
          },
        ],
      },
    },
    name: 'markdownlint',
    on: on_trigger(settings) + {
      pull_request+: {
        paths: ['**/*.md', '**/*.mdc', '.github/workflows/markdownlint.yml'],
      },
      push+: {
        paths: ['**/*.md', '**/*.mdc', '.github/workflows/markdownlint.yml'],
      },
    },
    permissions: permissions,
  },

  spelling(settings): {
    jobs: {
      spelling: {
        'runs-on': settings.qa_runs_on,
        steps: [checkout] + yarn_steps + [
          {
            name: 'Check spelling',
            run: 'yarn check-spelling',
          },
        ],
      },
    },
    name: 'Spelling',
    on: on_trigger(settings),
    permissions: permissions,
  },
}
