local utils = import 'utils.libsonnet';

function(settings)
  {
    concurrency: utils.publishConcurrency(),
    jobs: {
      build: {
        container: {
          image: settings.flatpak_image,
          options: '--privileged',
        },
        name: 'Build',
        permissions: utils.attestPermissions(settings),
        'runs-on': '${{ matrix.system.image }}',
        steps: [
          utils.checkout(),
          {
            env: {
              MATRIX_ARCH: '${{ matrix.system.arch }}',
            },
            name: 'Set Flatpak bundle filename',
            id: 'flatpak_bundle',
            run: |||
              version=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
              echo "version=${version}" >> "$GITHUB_OUTPUT"
              echo "filename=%s-${version}-${MATRIX_ARCH}.flatpak" >> "$GITHUB_OUTPUT"
            ||| % settings.publishing.flathub,
          },
        ] + [
          {
            name: 'Build Flatpak',
            uses: 'flatpak/flatpak-github-actions/flatpak-builder@' +
                  utils.githubLatestActionSha('flatpak', 'flatpak-github-actions'),
            with: {
              arch: '${{ matrix.system.arch }}',
              bundle: '${{ steps.flatpak_bundle.outputs.filename }}',
              'manifest-path': '%s.yml' % settings.publishing.flathub,
            },
          },
          {
            name: 'Upload Artifacts',
            uses: 'actions/upload-artifact@' + utils.githubLatestActionSha('actions', 'upload-artifact'),
            with: {
              'if-no-files-found': 'error',
              name: '%s-${{ steps.flatpak_bundle.outputs.version }}-${{ matrix.system.arch }}' % settings.publishing.flathub,
              path: '${{ steps.flatpak_bundle.outputs.filename }}',
            },
          },
          {
            name: 'Attest',
            uses: 'actions/attest@' + utils.githubLatestActionSha('actions', 'attest'),
            with: {
              'subject-path': '${{ steps.flatpak_bundle.outputs.filename }}',
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
      'release-assets': utils.releaseAssetsJob(
        ['build'], '%s-*' % settings.publishing.flathub
      ),
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
    permissions: {},
  }
