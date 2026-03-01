local utils = import 'utils.libjsonnet';
{
  name: 'Yarn cache',
  uses: 'actions/cache@' + utils.githubLatestActionTag('actions', 'cache'),
  with: {
    key: "${{ runner.os }}-yarn-${{ hashFiles('yarn.lock', '.yarnrc.yml') }}",
    path: '~/.yarn/berry',
    'restore-keys': '${ runner.os }}-yarn',
  },
}
