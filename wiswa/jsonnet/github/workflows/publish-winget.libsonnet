function(settings)
  {
    jobs: {
      check: {
        'if': "${{ github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.event == 'push' && startsWith(github.event.workflow_run.head_branch, 'v') }}",
        outputs: {
          has_winget_token: '${{ steps.check_secret.outputs.has_winget_token }}',
          tag: '${{ github.event.workflow_run.head_branch }}',
        },
        'runs-on': 'ubuntu-latest',
        steps: [
          {
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
          },
        ],
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
              'release-tag': '${{ needs.check.outputs.tag }}',
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
      workflow_run: {
        types: ['completed'],
        workflows: ['Release'],
      },
    },
  }
