local utils = import 'utils.libsonnet';

{
  local top = self,
  uses_user_defaults: true,
  primary_module_qualified: 'wiswa.tool',
  want_djlint: true,
  want_main: true,
  want_flatpak: true,
  publishing+: { flathub: 'sh.tat.wiswa' },
  project_name: 'wiswa',
  version: '0.4.0',
  description: 'A highly opinionated way to generate and maintain projects with Jsonnet.',
  keywords: ['command line', 'jsonnet', 'project generator', 'project management', 'scaffolding'],
  github+: {
    pages_config+: {
      exclude+: ['wiswa/tool/templates/'],
    },
    workflows+: {
      release_gate_workflows+: ['jsonnetfmt'],
    },
  },
  shared_ignore+: ['/docs/_build*/'],
  prettierignore+: ['*.adoc', 'Doxyfile'],
  security_policy_supported_versions: { '0.3.x': ':white_check_mark:' },
  package_json+: {
    cspell+: {
      ignorePaths+: ['*.html'],
    },
    scripts+: {
      'check-formatting': super['check-formatting'] + ' && jsonnetfmt --string-style s --no-pad-arrays --test -- .wiswa.jsonnet wiswa/jsonnet/**/*.*sonnet',
      format: super.format + ' && jsonnetfmt --string-style s --no-pad-arrays --in-place -- .wiswa.jsonnet wiswa/jsonnet/**/*.*sonnet',
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
  flatpak+: {
    modules: [
      super.modules[0] {
        sources: [
          {
            tag: 'v' + top.version,
            type: 'git',
            url: 'https://github.com/Tatsh/wiswa',
          },
        ],
      },
    ],
  },
  snapcraft+: {
    parts+: {
      [top.project_name]+: {
        source: 'https://github.com/Tatsh/wiswa.git',
        'source-tag': 'v' + top.version,
      },
    },
  },
  python_deps+: {
    main+: {
      anyio: utils.latestPypiPackageVersionCaret('anyio'),
      jinja2: utils.latestPypiPackageVersionCaret('jinja2'),
      jsonnet: utils.latestPypiPackageVersionCaret('jsonnet'),
      keyring: utils.latestPypiPackageVersionCaret('keyring'),
      niquests: utils.latestPypiPackageVersionCaret('niquests'),
      'niquests-cache': utils.latestPypiPackageVersionCaret('niquests-cache'),
      platformdirs: utils.latestPypiPackageVersionCaret('platformdirs'),
      rich: utils.latestPypiPackageVersionCaret('rich'),
      tomlkit: utils.latestPypiPackageVersionCaret('tomlkit'),
      'wiswa-typing': utils.latestPypiPackageVersionCaret('wiswa-typing'),
      'wiswa-vcs': utils.latestPypiPackageVersionCaret('wiswa-vcs'),
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
        wiswa: 'wiswa.tool.main:main',
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
              packages: [top.primary_module],
            },
          },
        },
      },
      ruff+: {
        'namespace-packages'+: ['wiswa/tool/static'],
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
          'wiswa-typing': '2026-05-18',
          'wiswa-vcs': '2026-05-23',
        },
      },
    },
  },
}
