local utils = import 'utils.libsonnet';

{
  jobs: {
    publish: {
      'runs-on': 'ubuntu-latest',
      steps: [
        {
          uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
        },
        {
          uses: 'leafo/gh-actions-luarocks@' + utils.githubLatestActionTag('actions', 'checkout'),
        },
        {
          env: {
            LUAROCKS_API_KEY: '${{ secrets.LUAROCKS_API_KEY }}',
          },
          name: 'Upload package',
          run: 'luarocks upload --api-key="$LUAROCKS_API_KEY" *.rockspec',
        },
      ],
    },
  },
  name: 'Publish to LuaRocks',
  permissions: {
    contents: 'read',
  },
  on: {
    push: {
      tags: [
        'v*',
      ],
    },
  },
}
