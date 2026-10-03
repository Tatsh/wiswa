local utils = import 'utils.libsonnet';

function(settings)
  {
    jobs: {
      check: utils.publishedReleaseJob(extra_outputs={
        has_installer_assets: '${{ steps.check_assets.outputs.has_installer_assets }}',
        has_winget_token: '${{ steps.check_secret.outputs.has_winget_token }}',
      }, extra_steps=[
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
        {
          env: {
            GH_TOKEN: '${{ github.token }}',
            REPO: '${{ github.repository }}',
            TAG: '${{ steps.release.outputs.tag }}',
          },
          id: 'check_assets',
          'if': "steps.release.outputs.tag != ''",
          name: 'Check release has installer assets',
          run: |||
            count=$(gh release view --repo "$REPO" "$TAG" --json assets \
              --jq '[.assets[].name | select(test("\\.(exe|msi|msix|appx)(bundle)?$"; "i"))] | length' \
              || echo 0)
            if [[ "$count" -gt 0 ]]; then
              echo 'has_installer_assets=true' >> "$GITHUB_OUTPUT"
            else
              echo 'has_installer_assets=false' >> "$GITHUB_OUTPUT"
              echo "::warning::Release ${TAG} has no installer assets; skipping update-winget."
            fi
          |||,
        },
      ]),
      'update-winget': {
        'if': "needs.check.outputs.has_winget_token == 'true' && needs.check.outputs.has_installer_assets == 'true'",
        needs: ['check'],
        'runs-on': 'windows-latest',
        steps: [
          {
            uses: 'vedantmgoyal9/winget-releaser@' + utils.githubLatestActionSha('vedantmgoyal9', 'winget-releaser'),
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
