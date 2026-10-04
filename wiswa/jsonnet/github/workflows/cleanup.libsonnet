local utils = import 'utils.libsonnet';

function(settings) {
  concurrency: utils.ciConcurrency,
  jobs: {
    cleanup: {
      name: 'Cleanup',
      permissions: {
        actions: 'write',
        contents: 'read',
      },
      'runs-on': 'ubuntu-latest',
      steps: [
        utils.checkout(),
        {
          env: {
            GH_TOKEN: '${{ secrets.GITHUB_TOKEN }}',
          },
          name: 'Delete old caches',
          run: |||
            gh cache list --json id,createdAt --jq '.[] | select((now - (.createdAt | sub("\\.[0-9]+"; "") | fromdateiso8601)) > 43200) | .key' | xargs -r -L1 gh cache delete
          |||,
        },
        {
          env: {
            GH_TOKEN: '${{ secrets.GITHUB_TOKEN }}',
            REPO: '${{ github.repository }}',
          },
          name: 'Delete old artifacts',
          run: |||
            gh api "repos/$REPO/actions/artifacts" --paginate --jq '.artifacts[] | select((now - (.created_at | sub("\\.[0-9]+"; "") | fromdateiso8601)) > 43200) | .id' | xargs -r -I{} gh api --method DELETE "repos/$REPO/actions/artifacts/{}"
          |||,
        },
      ],
    },
  },
  name: 'Cleanup',
  on: {
    schedule: [{ cron: '0 */12 * * *' }],
    workflow_dispatch: {},
  },
  permissions: {},
}
