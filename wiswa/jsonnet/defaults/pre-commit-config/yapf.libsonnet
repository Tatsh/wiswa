local utils = import 'utils.libsonnet';

{
  hooks: [
    {
      id: 'yapf',
      name: 'check Python files are formatted',
    },
  ],
  repo: 'https://github.com/google/yapf',
  // Derived from the same PyPI lookup as the dev dependency, so the hook and the project format
  // with the same yapf rather than drifting apart on separate schedules.
  rev: 'v' + utils.latestPypiPackageVersion('yapf'),
}
