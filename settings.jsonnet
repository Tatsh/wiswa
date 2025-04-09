local github_username = 'Tatsh';
local project_name = 'wiswa';

local authors = [
    {
        'given-names': 'Andrew',
        'family-names': 'Udvare',
        name: '%s %s' % [self['given-names'], self['family-names']],
        email: 'audvare@gmail.com',
    }
];

{
  // Shared
  project_name: project_name,
  version: '0.0.0',
  authors: [{ name: x.name, email: x.email } for x in authors],
  description: 'Generate a Python project.',
  directory_name: self.project_name,
  documentation_uri: 'https://%s.readthedocs.org' % self.project_name,
  homepage: self.github.pages_uri,
  keywords: ['command line', 'python'],
  license: 'MIT',
  repository_name: self.project_name,
  repository_uri: 'https://github.com/%s/%s' % [
    self.github.username,
    self.project_name,
  ],

  github: {
    funding: {
      custom: null,
      github: github_username,
      ko_fi: 'tatsh2',
      liberapay: 'tatsh2',
      patreon: 'tatsh2',
    },
    pages_theme: 'jekyll-theme-hacker',
    pages_uri: 'https://%s.github.io/%s/' % [
      std.asciiLower(github_username),
      project_name,
    ],
    username: github_username,
  },

  citation: {
    authors: [{'family-names': x['family-names'], 'given-names': x['given-names']} for x in authors],
    date_released: '2025-04-09',
  },


  // Python only
  dependencies: {
    main: {},
    dev: {},
    docs: {},
    tests: {},
  },
  min_python_minor_version: '10',
  primary_module: project_name,
  supported_python_versions:
    ['3.%s' % self.min_python_minor_version] + [
      ('3.%s' % i)
      for i in [11, 12, 13]
    ],
  modules: [std.strReplace(self.primary_module, '-', '_')],
  packages: [{ include: m } for m in self.modules],
  scripts: { [project_name]: '%s.main:main' % project_name },

  // package.json only
  repository: {
    type: 'git',
    url: 'git@github.com:%s/%s.git' % [github_username, project_name],
  },
  yarn_version: '4.8.1',
}
