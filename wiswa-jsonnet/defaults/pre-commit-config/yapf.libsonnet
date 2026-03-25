local utils = import 'utils.libsonnet';

{
  hooks: [
    {
      id: 'yapf',
      name: 'check Python files are formatted',
    },
  ],
  repo: 'https://github.com/google/yapf',
  rev: utils.githubLatestTag('google', 'yapf'),
}
