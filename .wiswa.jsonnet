local utils = import 'utils.libjsonnet';

{
  local top = self,
  want_djlint: true,
  want_main: true,
  project_name: 'wiswa',
  version: '0.0.0',
  description: 'A highly opinionated way to generate and maintain projects with Jsonnet.',
  keywords: ['command line', 'python'],
  copilot: {
    intro: 'Wiswa is a tool to generate and manage projects.',
  },
  shared_ignore+: ['/docs/_build*/'],
  prettierignore+: ['*.adoc', 'Doxyfile'],
  package_json+: {
    cspell+: {
      ignorePaths+: ['*.html'],
    },
  },
  pyinstaller+: {
    collect_data+: ['fastmcp'],
  },
  pyproject+: {
    project+: {
      scripts+: {
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
          tomlkit: utils.latestPypiPackageVersionCaret('tomlkit'),
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
      },
      hatch+: {
        build+: {
          targets+: {
            wheel+: {
              packages+: ['%s-jsonnet' % top.primary_module],
            },
          },
        },
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
