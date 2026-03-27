local utils = import 'utils.libsonnet';

{
  local top = self,
  want_djlint: true,
  want_main: true,
  project_name: 'wiswa',
  version: '0.0.1',
  description: 'A highly opinionated way to generate and maintain projects with Jsonnet.',
  keywords: ['command line', 'jsonnet', 'project generator', 'project management', 'scaffolding'],
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
    copy_metadata+: ['fastmcp'],
    vcpkg: {
      enabled: true,
      targets: {
        'windows-11-arm': {
          triplet: 'arm64-windows',
          packages: ['openssl'],
        },
      },
    },
  },
  python_deps+: {
    main+: {
      aiofiles: utils.latestPypiPackageVersionCaret('aiofiles'),
      niquests: utils.latestPypiPackageVersionCaret('niquests'),
      anyio: utils.latestPypiPackageVersionCaret('anyio'),
      beautifulsoup4: utils.latestPypiPackageVersionCaret('beautifulsoup4'),
      fastmcp: utils.latestPypiPackageVersionCaret('fastmcp'),
      jinja2: utils.latestPypiPackageVersionCaret('jinja2'),
      jsonnet: utils.latestPypiPackageVersionCaret('jsonnet'),
      keyring: utils.latestPypiPackageVersionCaret('keyring'),
      lxml: utils.latestPypiPackageVersionCaret('lxml'),
      tomlkit: utils.latestPypiPackageVersionCaret('tomlkit'),
    },
    dev+: {
      'types-jsonnet': utils.latestPypiPackageVersionCaret('types-jsonnet'),
    },
    tests+: {
      'pytest-asyncio': utils.latestPypiPackageVersionCaret('pytest-asyncio'),
    },
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
      hatch+: {
        build+: {
          targets+: {
            wheel+: {
              packages: [top.primary_module, '%s-jsonnet' % top.primary_module],
            },
          },
        },
      },
      ruff+: {
        'namespace-packages'+: ['wiswa/static'],
      },
    },
  },
}
