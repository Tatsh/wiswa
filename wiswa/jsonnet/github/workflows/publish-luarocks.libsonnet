local check_workflows = import 'github/workflows/_check-workflows.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local optional_workflows = std.set(
    ['Prettier', 'QA', 'Spelling', 'markdownlint'] +
    (if settings.want_tests then ['Tests'] else [])
  );
  local required_workflows = std.set(settings.github.workflows.release_gate_workflows);
  {
    jobs: {
      check: check_workflows.job(required_workflows, optional_workflows),
      publish: {
        [if settings.github.workflows.release_environment != '' then 'environment']:
          settings.github.workflows.release_environment,
        needs: ['check'],
        permissions: {
          contents: 'write',
        },
        'runs-on': 'ubuntu-latest',
        steps: [
          utils.checkout(),
          {
            uses: 'leafo/gh-actions-lua@' + utils.githubLatestActionSha('leafo', 'gh-actions-lua'),
            with: {
              luaVersion: '5.1',
            },
          },
          {
            uses: 'leafo/gh-actions-luarocks@' + utils.githubLatestActionSha('leafo', 'gh-actions-luarocks'),
          },
          {
            env: {
              LUAROCKS_API_KEY: '${{ secrets.LUAROCKS_API_KEY }}',
            },
            name: 'Upload package',
            run: 'luarocks upload --api-key="$LUAROCKS_API_KEY" *.rockspec',
          },
          utils.ghDraftReleaseStep(),
        ],
      },
    },
    name: 'Publish',
    permissions: {},
    on: {
      push: {
        tags: [
          'v*',
        ],
      },
    },
  }
