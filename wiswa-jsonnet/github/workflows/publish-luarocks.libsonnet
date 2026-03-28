local check_workflows = import 'github/workflows/_check-workflows.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local watched_workflows = std.sort(
    ['Prettier', 'QA', 'Spelling', 'markdownlint'] +
    (if settings.want_tests then ['Tests'] else [])
  );
  {
    jobs: {
      check: check_workflows.job(watched_workflows),
      publish: {
        needs: ['check'],
        'runs-on': 'ubuntu-latest',
        steps: [
          {
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
          {
            uses: 'leafo/gh-actions-luarocks@' + utils.githubLatestActionTag('leafo', 'gh-actions-luarocks'),
          },
          {
            env: {
              LUAROCKS_API_KEY: '${{ secrets.LUAROCKS_API_KEY }}',
            },
            name: 'Upload package',
            run: 'luarocks upload --api-key="$LUAROCKS_API_KEY" *.rockspec',
          },
          {
            uses: 'softprops/action-gh-release@' + utils.githubLatestActionTag('softprops', 'action-gh-release'),
            with: {
              draft: true,
            },
          },
        ],
      },
    },
    name: 'Publish',
    permissions: {
      contents: 'write',
    },
    on: {
      push: {
        tags: [
          'v*',
        ],
      },
    },
  }
