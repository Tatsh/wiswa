function(settings) {
  jobs: {
    'update-winget': {
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
  on: {
    release: {
      types: [
        'released',
      ],
    },
  },
}
