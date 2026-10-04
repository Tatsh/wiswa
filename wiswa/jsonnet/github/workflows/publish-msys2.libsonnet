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
              cd %(pkgbuild_dir)s || exit 1
              sed -i "s/^pkgver=.*/pkgver=${VERSION}/" PKGBUILD
              sed -i "s/^pkgrel=.*/pkgrel=1/" PKGBUILD
              NEW_SUM=$(curl -L "https://github.com/%(source_repo)s/archive/refs/tags/v${VERSION}.tar.gz" | sha256sum | awk '{print $1}')
              sed -i "s/^sha256sums=.*/sha256sums=('${NEW_SUM}')/" PKGBUILD
            ||| % { pkgbuild_dir: pkgbuild_dir, source_repo: source_repo },
          },
          {
            name: 'Create pull request',
            env: {
              FORK: fork,
              GH_TOKEN: '${{ secrets.MSYS2_TOKEN }}',
              TAG: '${{ steps.version.outputs.tag }}',
              VERSION: '${{ steps.version.outputs.version }}',
            },
            run: |||
              base_repo='msys2/MINGW-packages'
              branch="%(package_name)s-${VERSION}"
              title="%(pkgbuild_dir)s: update to ${VERSION}"
              body="This PR was automatically created from the [%(project_name)s ${TAG} release](https://github.com/%(source_repo)s/releases/tag/${TAG})."
              git checkout -B "$branch"
              git add -A
              if git diff --cached --quiet; then
                echo 'The PKGBUILD is already up to date.'
                exit 0
              fi
              git commit -m "$title"
              gh auth setup-git
              push_repo="${FORK:-$base_repo}"
              git push --force "https://github.com/${push_repo}.git" "HEAD:refs/heads/${branch}"
              head="$branch"
              if [[ -n "$FORK" ]]; then
                head="${FORK%%%%/*}:${branch}"
              fi
              existing=$(gh pr list --repo "$base_repo" --head "$branch" --state open \
                --json number --jq '.[0].number // empty')
              if [[ -n "$existing" ]]; then
                echo "Pull request #${existing} exists; its branch was updated."
                exit 0
              fi
              gh pr create --repo "$base_repo" --base master --head "$head" --title "$title" \
                --body "$body"
            ||| % {
              package_name: package_name,
              pkgbuild_dir: pkgbuild_dir,
              project_name: settings.project_name,
              source_repo: source_repo,
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
