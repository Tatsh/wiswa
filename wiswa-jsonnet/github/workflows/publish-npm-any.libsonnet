local cache_yarn = import 'github/workflows/_cache-yarn.libsonnet';
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
        needs: ['check'],
        permissions: {
          contents: 'write',
          'id-token': 'write',
        },
        'runs-on': settings.github.workflows.publish_npm_any.runs_on,
        steps: [
          {
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
          {
            name: 'Setup Node.js',
            uses: 'actions/setup-node@' + utils.githubLatestActionTag('actions', 'setup-node'),
            with: {
              'node-version': settings.github.workflows.publish_npm_any.node_version,
              'registry-url': settings.github.workflows.publish_npm_any.registry_url,
            },
          },
          {
            name: 'Update npm',
            run: 'npm install --global npm@latest',
          },
          cache_yarn,
          {
            name: 'Install dependencies',
            run: 'yarn',
          },
          {
            name: 'Build',
            run: 'yarn tsc',
          },
          {
            name: 'Publish to NPM',
            run: 'yarn npm publish',
            env: {
              NODE_AUTH_TOKEN: '${{ secrets.NODE_AUTH_TOKEN || secrets.GITHUB_TOKEN }}',
            },
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
    on: {
      push: {
        tags: [
          'v*',
        ],
      },
    },
    permissions: {
      contents: 'write',
      'id-token': 'write',
    },
  }
