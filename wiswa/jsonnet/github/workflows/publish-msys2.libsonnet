local utils = import 'utils.libsonnet';

function(settings)
  local primary_author = settings.authors[0];
  local config = settings.github.workflows.publish_msys2;
  local package_name = config.package_name;
  local fork = config.fork;
  local pkgbuild_dir = 'mingw-w64-' + package_name;
  local source_repo = '%s/%s' % [settings.github_username, settings.github_project_name];
  {
    concurrency: utils.publishConcurrency(
      '${{ github.workflow }}-${{ github.event.workflow_run.head_sha }}'
    ),
    jobs: {
      check: utils.publishedReleaseJob(),
      'update-pkgbuild': {
        'if': "needs.check.outputs.tag != ''",
        name: 'Update PKGBUILD',
        needs: ['check'],
        'runs-on': 'ubuntu-latest',
        steps: [
          {
            id: 'version',
            name: 'Extract version',
            env: {
              TAG_NAME: '${{ needs.check.outputs.tag }}',
            },
            run: |||
              TAG="$TAG_NAME"
              VERSION="${TAG#v}"
              echo "version=$VERSION" >> "$GITHUB_OUTPUT"
              echo "tag=$TAG" >> "$GITHUB_OUTPUT"
            |||,
          },
          utils.checkout({
            name: 'Checkout MINGW-packages repository',
            with: {
              repository: 'msys2/MINGW-packages',
              token: '${{ secrets.MSYS2_TOKEN }}',
            },
          }),
          {
            name: 'Configure git',
            run: |||
              git config user.name "%s"
              git config user.email "%s"
            ||| % [utils.authorName(primary_author), primary_author.email],
          },
          {
            name: 'Update PKGBUILD',
            env: {
              VERSION: '${{ steps.version.outputs.version }}',
            },
            run: |||
              git remote add upstream https://github.com/msys2/MINGW-packages.git
              git fetch upstream
              git checkout master
              git reset --hard upstream/master
              cd %(pkgbuild_dir)s
              sed -i "s/^pkgver=.*/pkgver=${VERSION}/" PKGBUILD
              sed -i "s/^pkgrel=.*/pkgrel=1/" PKGBUILD
              NEW_SUM=$(curl -L "https://github.com/%(source_repo)s/archive/refs/tags/v${VERSION}.tar.gz" | sha256sum | awk '{print $1}')
              sed -i "s/^sha256sums=.*/sha256sums=('${NEW_SUM}')/" PKGBUILD
            ||| % { pkgbuild_dir: pkgbuild_dir, source_repo: source_repo },
          },
          {
            name: 'Create Pull Request',
            uses: 'peter-evans/create-pull-request@' + utils.githubLatestActionSha('peter-evans', 'create-pull-request'),
            with: {
              base: 'master',
              branch: '%s-${{ steps.version.outputs.version }}' % package_name,
              'commit-message': '%s: update to ${{ steps.version.outputs.version }}' % pkgbuild_dir,
              title: '%s: update to ${{ steps.version.outputs.version }}' % pkgbuild_dir,
              token: '${{ secrets.MSYS2_TOKEN }}',
              body: |||
                This PR was automatically created from the [%s ${{ steps.version.outputs.tag }} release](https://github.com/%s/releases/tag/${{ steps.version.outputs.tag }}).
              ||| % [settings.project_name, source_repo],
              'push-to-fork': fork,
            },
          },
        ],
      },
    },
    name: 'Update MSYS2 PKGBUILD',
    on: {
      workflow_run: {
        types: ['completed'],
        workflows: ['Release'],
      },
    },
    permissions: {
      contents: 'read',
    },
  }
