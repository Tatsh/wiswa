local utils = import 'utils.libsonnet';

{
  /**
   * Generate a job that waits for the given workflows to succeed.
   * @param required_workflows Array of workflow names that must register a run for the commit
   *        and complete successfully. A workflow with no run yet is treated as pending and the
   *        loop retries; a missing run that never appears within the timeout fails the gate.
   * @param optional_workflows Array of workflow names that may or may not run for the commit.
   *        A workflow with no run is silently skipped.
   * @returns A job object suitable for inclusion in a workflow's `jobs` field.
   */
  job(required_workflows, optional_workflows): {
    permissions: {
      actions: 'read',
      contents: 'read',
    },
    'runs-on': 'ubuntu-latest',
    steps: [
      utils.checkout(),
      {
        id: 'check',
        name: 'Wait for workflows',
        env: {
          GH_TOKEN: '${{ github.token }}',
          COMMIT_SHA: '${{ github.sha }}',
        },
        run: |||
          sha="$COMMIT_SHA"
          required_workflows=(%(required)s)
          optional_workflows=(%(optional)s)
          process_workflow() {
            local workflow="$1" treat_missing="$2"
            local run status conclusion
            run=$(gh run list --workflow "$workflow" --commit "$sha" --json status,conclusion --jq '.[0]') || run=''
            if [[ -z "$run" || "$run" == 'null' ]]; then
              if [[ "$treat_missing" == 'pending' ]]; then
                echo "Required workflow '$workflow' has not registered a run yet; waiting."
                return 2
              fi
              echo "Optional workflow '$workflow' did not run for this commit; skipping."
              return 0
            fi
            status=$(echo "$run" | jq -r '.status') || status=''
            conclusion=$(echo "$run" | jq -r '.conclusion') || conclusion=''
            case "$conclusion" in
              failure|cancelled|timed_out|startup_failure|action_required)
                echo "::error::Workflow '$workflow' ${conclusion}."
                return 1
                ;;
              success|skipped|neutral)
                return 0
                ;;
              *)
                if [[ "$status" == 'completed' ]]; then
                  echo "::error::Workflow '$workflow' completed with unexpected conclusion '${conclusion}'."
                  return 1
                fi
                echo "Workflow '$workflow' still pending (status=${status})."
                return 2
                ;;
            esac
          }
          for i in $(seq 1 30); do
            all_done=true
            for workflow in "${required_workflows[@]}"; do
              rc=0
              process_workflow "$workflow" pending || rc=$?
              [[ $rc -eq 1 ]] && exit 1
              [[ $rc -eq 2 ]] && all_done=false
            done
            for workflow in "${optional_workflows[@]}"; do
              rc=0
              process_workflow "$workflow" skip || rc=$?
              [[ $rc -eq 1 ]] && exit 1
              [[ $rc -eq 2 ]] && all_done=false
            done
            if [[ "$all_done" == 'true' ]]; then
              echo 'All required workflows succeeded.'
              exit 0
            fi
            echo "Waiting 60s for workflows to complete (attempt ${i}/30)..."
            sleep 60
          done
          echo '::error::Timed out waiting for workflows.'
          exit 1
        ||| % {
          required: std.join(' ', ["'" + w + "'" for w in required_workflows]),
          optional: std.join(' ', ["'" + w + "'" for w in optional_workflows]),
        },
      },
    ],
  },
}
