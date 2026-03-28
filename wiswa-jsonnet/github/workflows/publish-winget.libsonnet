local check_workflows = import 'github/workflows/_check-workflows.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local watched_workflows = std.sort(
    ['QA'] +
    (if settings.want_tests then ['Tests'] else [])
  );
  {
    jobs: {
      check: check_workflows.job(watched_workflows),
      'update-winget': {
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
