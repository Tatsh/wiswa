local utils = import 'utils.libsonnet';

function(settings)
  local config = settings.github.workflows.scan_build;
  local compiler_options = if std.startsWith(config.runs_on, 'macos') then
    '--use-cc="$(xcrun --find clang)" --use-c++="$(xcrun --find clang++)"'
  else '--use-cc=clang --use-c++=clang++';
  local action(repository) = 'actions/' + repository + '@' +
                             utils.githubLatestActionSha('actions', repository);
  local upload(name, path) = {
    uses: action('upload-artifact'),
    with: { name: name, path: path, 'if-no-files-found': 'error' },
  };
  local download(name, path) = {
    uses: action('download-artifact'),
    with: { name: name, path: path },
  };
  local has_docs = std.length(config.documentation_steps) > 0;
  {
    name: 'Static analysis and Pages',
    on: {
      push: { 'branches-ignore': ['scan-build-pages'] },
      pull_request: {},
      workflow_dispatch: {},
    },
    permissions: {},
    jobs: {
      analyze: {
        name: 'scan-build',
        'runs-on': config.runs_on,
        permissions: { contents: 'read' },
        defaults: { run: { shell: 'bash' } },
        [if std.length(std.objectFields(config.env)) > 0 then 'env']: config.env,
        steps: [utils.checkout({ with: config.checkout_options })] + config.setup_steps + [
          {
            name: 'Install Clang analyzer',
            run: if std.startsWith(config.runs_on, 'macos') then |||
              brew install llvm
              echo "$(brew --prefix llvm)/bin" >> "$GITHUB_PATH"
            ||| else |||
              sudo apt-get update
              sudo apt-get install -y clang clang-tools
            |||,
          },
          {
            name: 'Configure with compiler interception',
            env: { SCAN_BUILD_CONFIGURE_COMMAND: config.configure_command },
            run: 'mkdir -p scan-build-report\n' +
                 'scan-build ' + compiler_options + ' -o "$RUNNER_TEMP/scan-configure" ' +
                 'bash -eo pipefail -c "$SCAN_BUILD_CONFIGURE_COMMAND" ' +
                 '2>&1 | tee scan-build-report/build.log',
          },
          {
            id: 'analysis',
            name: 'Analyze a clean build',
            env: { SCAN_BUILD_BUILD_COMMAND: config.build_command },
            run: |||
              mkdir -p scan-build-report
              scan-build %s -plist-html --keep-empty -v \
                -o scan-build-report/results bash -eo pipefail -c "$SCAN_BUILD_BUILD_COMMAND" \
                2>&1 | tee -a scan-build-report/build.log
            ||| % compiler_options,
          },
          {
            name: 'Prepare report and verify analysis coverage',
            'if': '${{ !cancelled() }}',
            env: {
              ANALYSIS_OUTCOME: '${{ steps.analysis.outcome }}',
              ANALYSIS_SCOPE: config.scope,
            },
            run: |||
              python3 - <<'PY'
              import html
              import os
              from pathlib import Path

              root = Path('scan-build-report')
              root.mkdir(exist_ok=True)
              reports = sorted(root.glob('results/*/index.html'))
              units = list(root.glob('results/*/*.plist'))
              failures = list(root.glob('results/*/failures/*'))
              complete = os.environ['ANALYSIS_OUTCOME'] == 'success' and bool(units) and not failures
              status = 'Analysis completed' if complete else 'Analysis incomplete or build failed'
              links = ''.join('<li><a href="' + html.escape(str(p.relative_to(root))) +
                              '">Clang HTML report</a></li>' for p in reports)
              if not reports and complete:
                  links = '<li>No bugs reported by the enabled Clang checkers.</li>'
              page = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                      '<title>Clang static analysis</title><h1>' + status + '</h1><p>Commit ' +
                      html.escape(os.environ['GITHUB_SHA']) + '</p><p>' +
                      html.escape(os.environ['ANALYSIS_SCOPE']) + '</p><p>' + str(len(units)) +
                      ' translation units. ' + str(len(failures)) + ' analyzer failure files.</p>' +
                      '<ul>' + links + '</ul><p><a href="build.log">Build log</a></p></html>')
              (root / 'index.html').write_text(page, encoding='utf-8')
              if not complete:
                  raise SystemExit('Incomplete analysis; inspect the build log and analyzer failures.')
              PY
            |||,
          },
          upload('scan-build-${{ github.sha }}', 'scan-build-report') + {
            'if': '${{ !cancelled() }}',
          },
        ],
      },
      [if has_docs then 'documentation']: {
        name: 'Documentation',
        'runs-on': 'ubuntu-latest',
        'if': "${{ github.event_name != 'pull_request' && github.ref_name == github.event.repository.default_branch }}",
        permissions: { contents: 'read' },
        steps: [utils.checkout({ with: config.checkout_options })] + config.documentation_steps + [
          upload('documentation', config.documentation_path),
        ],
      },
      publish: {
        name: 'Publish reports and documentation',
        needs: ['analyze'] + (if has_docs then ['documentation'] else []),
        'if': "${{ !cancelled() && github.event_name != 'pull_request' }}",
        'runs-on': 'ubuntu-latest',
        concurrency: utils.publishConcurrency('pages'),
        environment: {
          name: 'github-pages',
          url: '${{ steps.deployment.outputs.page_url }}',
        },
        permissions: { contents: 'write', pages: 'write', 'id-token': 'write' },
        steps: [
          utils.checkout(),
          download('scan-build-${{ github.sha }}', '_report'),
        ] + (if has_docs then [download('documentation', '_documentation') + {
               'if': "${{ needs.documentation.result == 'success' }}",
             }] else []) + [
          {
            name: 'Restore report archive',
            env: { GH_TOKEN: '${{ github.token }}' },
            run: |||
              git init _site
              git -C _site remote add origin "https://github.com/$GITHUB_REPOSITORY.git"
              export GIT_CONFIG_COUNT=1
              export GIT_CONFIG_KEY_0=http.https://github.com/.extraheader
              GIT_CONFIG_VALUE_0="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
              export GIT_CONFIG_VALUE_0
              status=0
              git -C _site ls-remote --exit-code origin refs/heads/scan-build-pages || status=$?
              if [ "$status" -eq 0 ]; then
                git -C _site fetch --depth=1 origin scan-build-pages
                git -C _site checkout -b scan-build-pages FETCH_HEAD
              elif [ "$status" -ne 2 ]; then
                exit "$status"
              fi
            |||,
          },
          {
            name: 'Assemble site and retain commit reports',
            run: |||
              if [ -d _documentation ]; then
                cp -a _documentation/. _site/
              fi
              mkdir -p "_site/scan-build/$GITHUB_SHA"
              cp -a _report/. "_site/scan-build/$GITHUB_SHA/"
              python3 - <<'PY'
              from pathlib import Path

              root = Path('_site')
              reports = root / 'scan-build'
              commits = sorted(p.name for p in reports.iterdir() if p.is_dir())
              links = ''.join('<li><a href="' + sha + '/">' + sha + '</a></li>' for sha in commits)
              (reports / 'index.html').write_text(
                  '<!doctype html><html lang="en"><meta charset="utf-8">'
                  '<title>Clang static analysis</title><h1>Commit reports</h1><ul>' + links + '</ul>',
                  encoding='utf-8')
              if not (root / 'index.html').exists():
                  (root / 'index.html').write_text(
                      '<!doctype html><html lang="en"><meta charset="utf-8">'
                      '<title>Clang static analysis</title>'
                      '<a href="scan-build/">Clang static analysis reports</a>', encoding='utf-8')
              (root / '.nojekyll').touch()
              PY
            |||,
          },
          {
            name: 'Save report archive',
            env: { GH_TOKEN: '${{ github.token }}' },
            run: |||
              export GIT_CONFIG_COUNT=1
              export GIT_CONFIG_KEY_0=http.https://github.com/.extraheader
              GIT_CONFIG_VALUE_0="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
              export GIT_CONFIG_VALUE_0
              git -C _site config user.name 'github-actions[bot]'
              git -C _site config user.email '41898282+github-actions[bot]@users.noreply.github.com'
              git -C _site add .
              if ! git -C _site diff --cached --quiet; then
                git -C _site commit -m "Reports for $GITHUB_SHA"
                git -C _site push origin HEAD:refs/heads/scan-build-pages
              fi
              tar --dereference --hard-dereference -cf "$RUNNER_TEMP/artifact.tar" \
                --exclude=.git -C _site .
            |||,
          },
          { name: 'Configure Pages', uses: action('configure-pages') },
          upload('github-pages', '${{ runner.temp }}/artifact.tar') + {
            with+: { 'retention-days': 1 },
          },
          { id: 'deployment', name: 'Deploy Pages', uses: action('deploy-pages') },
          {
            name: 'Report URL',
            env: { PAGE_URL: '${{ steps.deployment.outputs.page_url }}' },
            run: 'echo "[Clang report](${PAGE_URL}scan-build/$GITHUB_SHA/)" >> "$GITHUB_STEP_SUMMARY"',
          },
        ],
      },
    },
  }
