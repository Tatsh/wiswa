local cache_yarn = import 'github/workflows/_cache-yarn.libsonnet';
local utils = import 'utils.libsonnet';

{
  local checkout = utils.checkout(),
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
    concurrency: utils.ciConcurrency,
    jobs: {
      prettier: {
        name: 'Prettier',
        'runs-on': settings.qa_runs_on,
        steps: [checkout] + yarn_steps + [
          {
            name: 'Check formatting (Prettier)',
            run: 'yarn prettier --check .',
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
    concurrency: utils.ciConcurrency,
    jobs: {
      markdownlint: {
        name: 'markdownlint',
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
    concurrency: utils.ciConcurrency,
    jobs: {
      spelling: {
        name: 'Spelling',
        'runs-on': settings.qa_runs_on,
        // Run the cspell version and dictionaries the project locks, the same ones dict:update uses.
        // cspell-action bundles its own, and the two disagree on words such as "worktree". The issue
        // template prints each unknown word as a workflow command, which GitHub shows as an
        // annotation on the file and line.
        steps: [checkout] + yarn_steps + [
          {
            name: 'Check spelling',
            run: |||
              # shellcheck disable=SC2016 # cspell expands the template variables, not the shell.
              yarn check-spelling --issue-template '::error file=$filename,line=$row,col=$col::Unknown word ($text)'
            |||,
          },
        ],
      },
    },
    name: 'Spelling',
    on: on_trigger(settings),
    permissions: permissions,
  },
}
