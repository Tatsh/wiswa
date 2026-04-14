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
        'if': |||
          github.event.workflow_run.conclusion == 'success' &&
          github.event.workflow_run.head_branch &&
          startsWith(github.event.workflow_run.head_branch, 'v')
        |||,
        'runs-on': 'ubuntu-latest',
        steps: [
          {
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
          {
            id: 'check',
            name: 'Check all workflows succeeded',
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
                status=$(gh run list --workflow "$workflow" --commit "$sha" --json conclusion --jq '.[0].conclusion')
                if [[ "$status" == 'failure' || "$status" == 'cancelled' ]]; then
                  echo "::error::Workflow '$workflow' ${status}."
                  exit 1
                elif [[ "$status" != 'success' ]]; then
                  echo "Workflow '$workflow' still pending, skipping."
                  all_success=false
                fi
              done
              if [[ "$all_success" != 'true' ]]; then
                echo 'Not all workflows have completed yet.'
                exit 0
              fi
              echo "All workflows succeeded for ${tag}."
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
