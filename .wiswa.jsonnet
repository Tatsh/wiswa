local utils = import 'utils.libsonnet';

{
  local top = self,
  uses_user_defaults: true,
  want_djlint: true,
  want_main: true,
  want_flatpak: true,
  publishing+: { flathub: 'sh.tat.wiswa' },
  project_name: 'wiswa',
  version: '0.2.2',
  description: 'A highly opinionated way to generate and maintain projects with Jsonnet.',
  keywords: ['command line', 'jsonnet', 'project generator', 'project management', 'scaffolding'],
  github+: {
    pages_config+: {
      exclude+: ['wiswa/templates/'],
    },
    workflows+: {
      release_gate_workflows+: ['jsonnetfmt'],
    },
  },
  shared_ignore+: ['/docs/_build*/'],
  prettierignore+: ['*.adoc', 'Doxyfile'],
  package_json+: {
    cspell+: {
      ignorePaths+: ['*.html'],
    },
    scripts+: {
      'check-formatting': super['check-formatting'] + ' && jsonnetfmt --string-style s --no-pad-arrays --test -- .wiswa.jsonnet wiswa-jsonnet/**/*.*sonnet',
      format: super.format + ' && jsonnetfmt --string-style s --no-pad-arrays --in-place -- .wiswa.jsonnet wiswa-jsonnet/**/*.*sonnet',
    },
  },
  pre_commit_config+: {
    ci+: {
      skip+: ['check-jsonnet-formatting'],
    },
    repos+: [
      {
        repo: 'local',
        hooks: [
          {
            id: 'check-jsonnet-formatting',
            name: 'Check Jsonnet formatting',
            files: '\\.(jsonnet|libsonnet)$',
            language: 'system',
            entry: 'jsonnetfmt --string-style s --no-pad-arrays --in-place --',
          },
        ],
      },
    ],
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
      anyio: utils.latestPypiPackageVersionCaret('anyio'),
      fastmcp: utils.latestPypiPackageVersionCaret('fastmcp'),
      jinja2: utils.latestPypiPackageVersionCaret('jinja2'),
      jsonnet: utils.latestPypiPackageVersionCaret('jsonnet'),
      keyring: utils.latestPypiPackageVersionCaret('keyring'),
      niquests: utils.latestPypiPackageVersionCaret('niquests'),
      'niquests-cache': utils.latestPypiPackageVersionCaret('niquests-cache'),
      platformdirs: utils.latestPypiPackageVersionCaret('platformdirs'),
      'python-gitlab': utils.latestPypiPackageVersionCaret('python-gitlab'),
      rich: utils.latestPypiPackageVersionCaret('rich'),
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
      local extra_omit = ['typing.py', '**/*.j2'],
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
      ty+: {
        src+: {
          exclude+:
            [
              // ty fails miserably with calls into the Jinja2 environment.
              'tests/test_extensions.py',
            ],
        },
      },
      uv+: {
        'exclude-newer-package'+: {
          'niquests-cache': false,
        },
      },
    },
  },
}
