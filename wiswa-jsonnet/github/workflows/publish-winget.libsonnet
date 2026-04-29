local check_workflows = import 'github/workflows/_check-workflows.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local optional_workflows = std.set(
    ['Prettier', 'QA', 'Spelling', 'markdownlint'] +
    (if settings.want_tests then ['Tests'] else [])
  );
  local required_workflows = std.set(settings.github.workflows.release_gate_workflows);
  local base_check_job = check_workflows.job(required_workflows, optional_workflows);
  // GitHub Actions doesn't allow `secrets.X` in a job-level `if`. Surface the
  // existence of WINGET_TOKEN as an output of the `check` job so `update-winget`
  // can be gated on it; if the secret is empty the publish job is skipped.
  local check_secret_step = {
    id: 'check_secret',
    name: 'Check WINGET_TOKEN is set',
    env: {
      WINGET_TOKEN: '${{ secrets.WINGET_TOKEN }}',
    },
    run: |||
      if [[ -n "$WINGET_TOKEN" ]]; then
        echo 'has_winget_token=true' >> "$GITHUB_OUTPUT"
      else
        echo 'has_winget_token=false' >> "$GITHUB_OUTPUT"
        echo '::warning::WINGET_TOKEN secret is empty; the update-winget job will be skipped.'
      fi
    |||,
  };
  {
    jobs: {
      check: base_check_job {
        outputs: {
          has_winget_token: '${{ steps.check_secret.outputs.has_winget_token }}',
        },
        // checkout (from base) then check_secret then the wait-for-workflows step.
        steps: [base_check_job.steps[0], check_secret_step] +
               base_check_job.steps[1:],
      },
      'update-winget': {
        'if': "needs.check.outputs.has_winget_token == 'true'",
        needs: ['check'],
        'runs-on': 'windows-latest',
        steps: [
          {
            uses: 'vedantmgoyal9/winget-releaser@main',
            with: {
              identifier: settings.github.workflows.publish_winget.identifier,
              'max-versions-to-keep': settings.github.workflows.publish_winget.max_versions_to_keep,
              token: '${{ secrets.WINGET_TOKEN }}',
            },
          },
        ],
      },
    },
    name: 'Publish to WinGet',
    permissions: {
      contents: 'read',
    },
    on: {
      release: {
        types: [
          'released',
        ],
      },
    },
  }
