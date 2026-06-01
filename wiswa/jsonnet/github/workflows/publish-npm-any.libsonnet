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
          'id-token': 'write',
          packages: 'write',
        },
        'runs-on': settings.github.workflows.publish_npm_any.runs_on,
        steps: [
          utils.checkout(),
          {
            name: 'Setup Node.js',
            uses: 'actions/setup-node@' + utils.githubLatestActionSha('actions', 'setup-node'),
            with: {
              'node-version': settings.github.workflows.publish_npm_any.node_version,
              'registry-url': settings.github.workflows.publish_npm_any.registry_url,
            },
          },
          {
            name: 'Update npm',
            run: 'npm install --global npm@latest',
          },
          {
            name: 'Install dependencies',
            run: 'yarn',
          },
          {
            name: 'Build',
            run: settings.github.workflows.publish_npm_any.build_command,
          },
          {
            name: 'Publish to NPM',
            run: 'yarn npm publish',
            env: {
              NODE_AUTH_TOKEN: '${{ secrets.NODE_AUTH_TOKEN || secrets.GITHUB_TOKEN }}',
            },
          },
          utils.ghDraftReleaseStep(),
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
    permissions: {},
  }
