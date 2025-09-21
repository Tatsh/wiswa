local utils = import 'utils.libjsonnet';

(import 'defaults.libjsonnet') + {
  local top = self,
  // General settings
  want_djlint: true,
  want_main: true,

  // Shared
  project_name: 'wiswa',
  version: '0.0.0',
  description: 'Generate a Python project.',
  keywords: ['command line', 'python'],
  copilot: {
    intro: 'Wiswa is a tool to generate and manage Python projects.',
  },

  // Python only
  pyproject+: {
    project+: {
      scripts+: { '_wiswa-gen-docs': 'wiswa.main:gen_docs_main' },
    },
    tool+: {
      poetry+: {
        dependencies+: {
          jinja2: '^' + std.native('latestPypiPackageVersion')('jinja2'),
          jsonnet: '^' + std.native('latestPypiPackageVersion')('jsonnet'),
          keyring: '^' + std.native('latestPypiPackageVersion')('keyring'),
          requests: '^' + std.native('latestPypiPackageVersion')('requests'),
        },
        group+: {
          dev+: {
            dependencies+: {
              'types-jsonnet': '^' + std.native('latestPypiPackageVersion')('types-jsonnet'),
              'types-requests': '^' + std.native('latestPypiPackageVersion')('types-requests'),
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
