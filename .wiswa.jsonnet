local utils = import 'utils.libjsonnet';

{
  local top = self,
  want_djlint: true,
  want_main: true,
  project_name: 'wiswa',
  version: '0.0.0',
  description: 'Generate a Python project.',
  keywords: ['command line', 'python'],
  copilot: {
    intro: 'Wiswa is a tool to generate and manage Python projects.',
  },
  shared_ignore+: ['/docs/_build*/'],
  prettierignore+: ['*.adoc', 'Doxyfile'],
  package_json+: {
    cspell+: {
      ignorePaths+: ['*.html'],
    },
  },
  pyproject+: {
    project+: {
      scripts+: {
        '_wiswa-gen-docs': 'wiswa.main:gen_docs_main',
        'wiswa-mcp': 'wiswa.mcp:main',
      },
    },
    tool+: {
      local extra_omit = ['typing.py'],
      coverage+: {
        report+: { omit+: extra_omit },
        run+: { omit+: extra_omit },
      },
      pytest+: {
        ini_options+: {
          asyncio_mode: 'auto',
        },
      },
      poetry+: {
        dependencies+: {
          aiofiles: utils.latestPypiPackageVersionCaret('aiofiles'),
          aiohttp: utils.latestPypiPackageVersionCaret('aiohttp'),
          'aiohttp-client-cache': {
            version: utils.latestPypiPackageVersionCaret('aiohttp-client-cache'),
            extras: ['filesystem'],
          },
          anyio: utils.latestPypiPackageVersionCaret('anyio'),
          beautifulsoup4: utils.latestPypiPackageVersionCaret('beautifulsoup4'),
          fastmcp: utils.latestPypiPackageVersionCaret('fastmcp'),
          jinja2: utils.latestPypiPackageVersionCaret('jinja2'),
          jsonnet: utils.latestPypiPackageVersionCaret('jsonnet'),
          keyring: utils.latestPypiPackageVersionCaret('keyring'),
          lxml: utils.latestPypiPackageVersionCaret('lxml'),
        },
        group+: {
          dev+: {
            dependencies+: {
              'types-jsonnet': utils.latestPypiPackageVersionCaret('types-jsonnet'),
            },
          },
          tests+: {
            dependencies+: {
              'pytest-asyncio': utils.latestPypiPackageVersionCaret('pytest-asyncio'),
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
  vscode+: {
    settings+: {
      'files.associations'+: {
        '*.libjsonnet': 'jsonnet',
      },
    },
  },
}
