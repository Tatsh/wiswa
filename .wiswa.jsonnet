local utils = import 'utils.libjsonnet';

(import 'defaults.libjsonnet') + {
  local top = self,
  // General settings
  want_djlint: true,
  want_main: true,

  // Shared
  github_username: 'Tatsh',
  authors: [
    {
      'family-names': 'Udvare',
      'given-names': 'Andrew',
      email: 'audvare@gmail.com',
      name: '%s %s' % [self['given-names'], self['family-names']],
    },
  ],
  project_name: 'wiswa',
  version: '0.0.0',
  description: 'Generate a Python project.',
  keywords: ['command line', 'python'],
  primary_module: std.strReplace(self.project_name, '-', '_'),

  github+: {
    funding: {
      custom: null,
      github: top.github_username,
      ko_fi: 'tatsh2',
      liberapay: 'tatsh2',
      patreon: 'tatsh2',
    },
    pages_uri: 'https://%s.github.io/%s/' % [std.asciiLower(top.github_username), top.project_name],
    username: top.github_username,
  },

  // CITATION.cff
  citation+: {
    authors: utils.citationAuthors(top.authors),
    'date-released': '2025-04-09',
  },

  // Python only
  pyproject+: {
    project+: {
      authors: [{ name: x.name, email: x.email } for x in top.authors],
      name: top.project_name,
      scripts: { [top.project_name]: '%s.main:main' % top.primary_module },
      version: top.version,
    },
    tool+: {
      poetry+: {
        dependencies+: {
          jinja2: '^3.1.6',
          jsonnet: '^0.21.0',
          keyring: '^25.6.0',
          requests: '^2.32.3',
        },
        group+: {
          dev+: {
            dependencies+: {
              'types-requests': '^2.32.0.20250328',
            },
          },
        },
        include: ['%s-jsonnet' % top.primary_module],
        packages: [{ include: x } for x in [top.primary_module]],
      },
      ruff+: {
        'namespace-packages'+: ['wiswa/static'],
      },
    },
  },

  // package.json only
  package_json+: {
    repository: {
      type: 'git',
      url: utils.githubGitSshUri(top.github_username, top.project_name),
    },
  },

  // VS Code
  vscode+: {
    settings+: {
      'files.associations'+: {
        '*.libjsonnet': 'jsonnet',
      },
    },
  },
}
