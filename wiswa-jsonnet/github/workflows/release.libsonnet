local utils = import 'utils.libsonnet';

function(settings)
  local has_pyinstaller = (settings.want_main || settings.has_multiple_entry_points) &&
                          (settings.supported_platforms == 'all' ||
                           std.member(settings.supported_platforms, 'windows') ||
                           std.member(settings.supported_platforms, 'macos'));
  local watched_workflows = std.set(
    ['QA', 'Prettier', 'Spelling', 'markdownlint'] +
    (if settings.want_tests then ['Tests'] else []) +
    (if !settings.private then ['Publish'] else []) +
    (if settings.want_appimage then ['AppImage'] else []) +
    (if utils.wantFlatpakOutputs(settings) then ['Flatpak'] else []) +
    (if has_pyinstaller then ['PyInstaller'] else []) +
    (if settings.want_snap then ['Snap'] else []) +
    settings.github.workflows.release_gate_workflows
  );
  {
    jobs: {
      'publish-release': {
        'runs-on': 'ubuntu-latest',
        steps: [
          {
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
          {
            id: 'guard',
            name: 'Check trigger conditions',
            env: {
              HEAD_BRANCH: '${{ github.event.workflow_run.head_branch }}',
              TRIGGER_CONCLUSION: '${{ github.event.workflow_run.conclusion }}',
            },
            run: |||
              if [[ "$TRIGGER_CONCLUSION" != 'success' ]]; then
                echo "Triggering workflow concluded with '${TRIGGER_CONCLUSION}', nothing to do."
                echo 'proceed=false' >> "$GITHUB_OUTPUT"
                exit 0
              fi
              if [[ -z "$HEAD_BRANCH" || "$HEAD_BRANCH" != v* ]]; then
                echo "Head branch '${HEAD_BRANCH}' is not a release tag, nothing to do."
                echo 'proceed=false' >> "$GITHUB_OUTPUT"
                exit 0
              fi
              echo 'proceed=true' >> "$GITHUB_OUTPUT"
            |||,
          },
          {
            id: 'check',
            'if': "steps.guard.outputs.proceed == 'true'",
            name: 'Check all required workflows succeeded',
            env: {
              GH_TOKEN: '${{ github.token }}',
              HEAD_BRANCH: '${{ github.event.workflow_run.head_branch }}',
              HEAD_SHA: '${{ github.event.workflow_run.head_sha }}',
            },
            run: |||
              tag="$HEAD_BRANCH"
              sha="$HEAD_SHA"
              all_success=true
              for workflow in %(workflows)s; do
                run=$(gh run list --workflow "$workflow" --commit "$sha" --json status,conclusion --jq '.[0]')
                if [[ -z "$run" || "$run" == 'null' ]]; then
                  echo "Workflow '$workflow' did not run for this commit; treating as optional."
                  continue
                fi
                status=$(echo "$run" | jq -r '.status')
                conclusion=$(echo "$run" | jq -r '.conclusion')
                case "$conclusion" in
                  failure|cancelled|timed_out|startup_failure|action_required)
                    echo "::error::Workflow '$workflow' ${conclusion}."
                    exit 1
                    ;;
                  success|skipped|neutral)
                    ;;
                  *)
                    if [[ "$status" == 'completed' ]]; then
                      echo "::error::Workflow '$workflow' completed with unexpected conclusion '${conclusion}'."
                      exit 1
                    fi
                    echo "Workflow '$workflow' still pending (status=${status})."
                    all_success=false
                    ;;
                esac
              done
              if [[ "$all_success" != 'true' ]]; then
                echo 'Not all workflows have completed yet.'
                exit 0
              fi
              echo "All required workflows succeeded for ${tag}."
              echo "tag=${tag}" >> "$GITHUB_ENV"
              echo "ready=true" >> "$GITHUB_OUTPUT"
            ||| % { workflows: std.join(' ', watched_workflows) },
          },
          {
            'if': "steps.check.outputs.ready == 'true'",
            name: 'Publish release',
            env: {
              GH_TOKEN: '${{ github.token }}',
            },
            run: 'gh release edit "$tag" --draft=false',
          },
          {
            'if': 'always()',
            name: 'Delete prior non-publishing Release runs',
            env: {
              GH_TOKEN: '${{ github.token }}',
              REPO: '${{ github.repository }}',
              RUN_ID: '${{ github.run_id }}',
              HEAD_SHA: '${{ github.event.workflow_run.head_sha }}',
            },
            run: |||
              sha="$HEAD_SHA"
              gh run list --repo "$REPO" --workflow 'Release' --commit "$sha" \
                --json databaseId,status,conclusion --limit 100 \
                | jq -r --arg self "$RUN_ID" \
                    '.[] | select((.databaseId|tostring) != $self) | select(.status == "completed" and (.conclusion == "skipped" or .conclusion == "cancelled" or .conclusion == "neutral")) | .databaseId' \
                | while read -r id; do
                    [[ -z "$id" ]] && continue
                    echo "Deleting prior Release run ${id}."
                    gh run delete --repo "$REPO" "$id" || true
                  done
            |||,
          },
          {
            'if': "steps.guard.outputs.proceed != 'true' || steps.check.outputs.ready != 'true'",
            name: 'Cancel this run so it can be cleaned up',
            env: {
              GH_TOKEN: '${{ github.token }}',
              REPO: '${{ github.repository }}',
              RUN_ID: '${{ github.run_id }}',
            },
            run: |||
              echo 'This run did not publish; cancelling so a later run can remove it.'
              gh run cancel --repo "$REPO" "$RUN_ID" || true
              sleep 30
            |||,
          },
        ],
      },
    },
    name: 'Release',
    on: {
      workflow_run: {
        types: ['completed'],
        workflows: watched_workflows,
      },
    },
    permissions: {
      contents: 'write',
    },
  }
