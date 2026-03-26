function(settings) {
  jobs: {
    cleanup: {
      'runs-on': 'ubuntu-latest',
      steps: [
        {
          uses: 'actions/checkout@' + (import 'utils.libsonnet').githubLatestActionTag('actions', 'checkout'),
        },
        {
          env: {
            GH_TOKEN: '${{ secrets.GITHUB_TOKEN }}',
          },
          name: 'Delete old caches',
          run: |||
            gh cache list --json id,createdAt -q '.[] | select((now - (.createdAt | sub("\\.[0-9]+"; "") | fromdateiso8601)) > 43200) | .key' | xargs -r -L1 gh cache delete
          |||,
        },
        {
          env: {
            GH_TOKEN: '${{ secrets.GITHUB_TOKEN }}',
            REPO: '${{ github.repository }}',
          },
          name: 'Delete old artifacts',
          run: |||
            gh api "repos/$REPO/actions/artifacts" --paginate -q '.artifacts[] | select((now - (.created_at | sub("\\.[0-9]+"; "") | fromdateiso8601)) > 43200) | .id' | xargs -r -I{} gh api -X DELETE "repos/$REPO/actions/artifacts/{}"
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
  permissions: {
    actions: 'write',
    contents: 'read',
  },
}
