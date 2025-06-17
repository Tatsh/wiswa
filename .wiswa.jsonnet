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

  github+: {
    funding+: {
      ko_fi: 'tatsh2',
      liberapay: 'tatsh2',
      patreon: 'tatsh2',
    },
  },

  // Python only
  pyproject+: {
    tool+: {
      poetry+: {
        dependencies+: {
          jinja2: '^3.1.6',
          jsonnet: '^0.21.0',
          keyring: '^25.6.0',
          requests: '^2.32.4',
        },
        group+: {
          dev+: {
            dependencies+: {
              'types-requests': '^2.32.4.20250611',
            },
          },
        },
        include: ['%s-jsonnet' % top.primary_module],
      },
      ruff+: {
        'namespace-packages'+: ['wiswa/static'],
      },
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
