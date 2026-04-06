local utils = import 'utils.libsonnet';

{
  /**
   * Generate a job that waits for the given workflows to succeed.
   * @param watched_workflows Array of workflow names to wait for.
   * @returns A job object suitable for inclusion in a workflow's `jobs` field.
   */
  job(watched_workflows): {
    'runs-on': 'ubuntu-latest',
    steps: [
      {
        uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
      },
      {
        id: 'check',
        name: 'Wait for workflows',
        env: {
          GH_TOKEN: '${{ github.token }}',
          COMMIT_SHA: '${{ github.sha }}',
        },
        run: |||
          sha="$COMMIT_SHA"
          for i in $(seq 1 30); do
            all_done=true
            for workflow in %(workflows)s; do
              status=$(gh run list --workflow "$workflow" --commit "$sha" --json conclusion --jq '.[0].conclusion')
              if [[ "$status" == 'failure' || "$status" == 'cancelled' ]]; then
                echo "::error::Workflow '$workflow' ${status}."
                exit 1
              elif [[ "$status" != 'success' ]]; then
                echo "Workflow '$workflow' still pending."
                all_done=false
              fi
            done
            if [[ "$all_done" == 'true' ]]; then
              echo 'All workflows succeeded.'
              exit 0
            fi
            echo "Waiting 60s for workflows to complete (attempt ${i}/30)..."
            sleep 60
          done
          echo '::error::Timed out waiting for workflows.'
          exit 1
        ||| % { workflows: std.join(' ', watched_workflows) },
      },
    ],
  },
}
