local utils = import 'utils.libsonnet';

function(settings)
  {
    jobs: {
      build: {
        container: {
          image: 'ghcr.io/flathub-infra/flatpak-github-actions:freedesktop-24.08',
          options: '--privileged',
        },
        'runs-on': '${{ matrix.system.image }}',
        steps: [
          {
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
          {
            name: 'Set Flatpak bundle filename',
            id: 'flatpak_bundle',
            run: |||
              version=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
              echo "version=${version}" >> "$GITHUB_OUTPUT"
              echo "filename=%s-${version}-${{ matrix.system.arch }}.flatpak" >> "$GITHUB_OUTPUT"
            ||| % settings.publishing.flathub,
          },
        ] + [
          {
            name: 'Build Flatpak',
            uses: 'flatpak/flatpak-github-actions/flatpak-builder@' +
                  utils.githubLatestActionTag('flatpak', 'flatpak-github-actions'),
            with: {
              arch: '${{ matrix.system.arch }}',
              bundle: '${{ steps.flatpak_bundle.outputs.filename }}',
              'manifest-path': '%s.yml' % settings.publishing.flathub,
            },
          },
          {
            name: 'Upload Artifacts',
            uses: 'actions/upload-artifact@' + utils.githubLatestActionTag('actions', 'upload-artifact'),
            with: {
              'if-no-files-found': 'error',
              name: '%s-${{ steps.flatpak_bundle.outputs.version }}-${{ matrix.system.arch }}' % settings.publishing.flathub,
              path: '${{ steps.flatpak_bundle.outputs.filename }}',
            },
          },
          {
            name: 'Attest',
            uses: 'actions/attest@' + utils.githubLatestActionTag('actions', 'attest'),
            with: {
              'subject-path': '${{ steps.flatpak_bundle.outputs.filename }}',
            },
          },
          {
            'if': "github.ref_type == 'tag'",
            name: 'Upload package',
            uses: 'softprops/action-gh-release@' + utils.githubLatestActionTag('softprops', 'action-gh-release'),
            with: {
              draft: true,
              fail_on_unmatched_files: true,
              files: '${{ steps.flatpak_bundle.outputs.filename }}',
            },
          },
        ],
        strategy: {
          matrix: {
            system: [
              {
                arch: 'x86_64',
                image: 'ubuntu-latest',
              },
              {
                arch: 'aarch64',
                image: 'ubuntu-24.04-arm',
              },
            ],
          },
        },
      },
    },
    name: 'Flatpak',
    on: {
      push: {
        branches: [
          'master',
        ],
        paths: ['%s/**' % utils.moduleImportToPath(mod) for mod in settings.modules] + [
          '.github/workflows/flatpak.yml',
          '%s.yml' % settings.publishing.flathub,
          'pyproject.toml',
          'uv.lock',
          'poetry.lock',
        ],
        tags: [
          'v*.*.*',
        ],
      },
      workflow_dispatch: null,
    },
    permissions: (if settings.private then { actions: 'write' } else {}) + {
      attestations: 'write',
      contents: 'write',
      'id-token': 'write',
    },
  }
