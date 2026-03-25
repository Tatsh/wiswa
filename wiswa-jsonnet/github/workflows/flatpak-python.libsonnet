local utils = import 'utils.libsonnet';

function(settings)
  local bundle_name = '%s.flatpak' % settings.project_name;
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
        ] + (if settings.private then [{
               env: {
                 GH_TOKEN: '${{ secrets.GITHUB_TOKEN }}',
               },
               name: 'Delete old caches and artifacts',
               run: |||
                 gh cache list --json id,createdAt -q '.[] | select((now - (.createdAt | sub("\\.[0-9]+"; "") | fromdateiso8601)) > 43200) | .key' | xargs -r -L1 gh cache delete
                 gh api repos/${{ github.repository }}/actions/artifacts --paginate -q '.artifacts[] | select((now - (.created_at | sub("\\.[0-9]+"; "") | fromdateiso8601)) > 43200) | .id' | xargs -r -I{} gh api -X DELETE repos/${{ github.repository }}/actions/artifacts/{}
               |||,
             }] else []) + [
          {
            name: 'Build Flatpak',
            uses: 'flathub-infra/flatpak-github-actions/flatpak-builder@' +
                  utils.githubLatestActionTag('flathub-infra', 'flatpak-github-actions'),
            with: {
              arch: '${{ matrix.system.arch }}',
              bundle: bundle_name,
              'manifest-path': '%s.yml' % settings.publishing.flathub,
            },
          },
          {
            name: 'Upload Artifacts',
            uses: 'actions/upload-artifact@' + utils.githubLatestActionTag('actions', 'upload-artifact'),
            with: {
              'if-no-files-found': 'error',
              name: '%s-flatpak-${{ matrix.system.arch }}' % settings.project_name,
              path: bundle_name,
            },
          },
          {
            name: 'Attest',
            uses: 'actions/attest@' + utils.githubLatestActionTag('actions', 'attest'),
            with: {
              'subject-path': bundle_name,
            },
          },
          {
            'if': "github.ref_type == 'tag'",
            name: 'Upload package',
            uses: 'softprops/action-gh-release@' + utils.githubLatestActionTag('softprops', 'action-gh-release'),
            with: {
              draft: true,
              fail_on_unmatched_files: true,
              files: bundle_name,
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
        paths: [
          '**/*.py',
          '**/*.pyi',
          '.github/workflows/flatpak.yml',
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
