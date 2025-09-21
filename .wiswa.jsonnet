local utils = import 'utils.libjsonnet';

{
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
          jinja2: utils.latestPypiPackageVersionCaret('jinja2'),
          jsonnet: utils.latestPypiPackageVersionCaret('jsonnet'),
          keyring: utils.latestPypiPackageVersionCaret('keyring'),
          requests: utils.latestPypiPackageVersionCaret('requests'),
        },
        group+: {
          dev+: {
            dependencies+: {
              'types-jsonnet': utils.latestPypiPackageVersionCaret('types-jsonnet'),
              'types-requests': utils.latestPypiPackageVersionCaret('types-requests'),
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
