local utils = import 'utils.libsonnet';

function(settings)
  local config = settings.github.workflows.scan_build;
  local compiler_options = if std.startsWith(config.runs_on, 'macos') then
    '--use-analyzer="$(xcrun --find clang)" --use-cc="$(xcrun --find clang)" '
    + '--use-c++="$(xcrun --find clang++)"'
  else '--use-cc=clang --use-c++=clang++';
  local action(repository) = 'actions/' + repository + '@' +
                             utils.githubLatestActionSha('actions', repository);
  local upload(name, path) = {
    uses: action('upload-artifact'),
    with: { name: name, path: path, 'if-no-files-found': 'error' },
  };
  local scoped = std.length(settings.static_analysis_paths) > 0;
  local exclude_options = if scoped then
    ' --exclude "$(python3 .github/scripts/static-analysis.py --exclude)"' else '';
  local scope_build(command) = if !scoped then command else |||
    export STATIC_ANALYSIS_CC="$CC" STATIC_ANALYSIS_CXX="$CXX"
    export STATIC_ANALYSIS_REAL_CC=%s STATIC_ANALYSIS_REAL_CXX=%s
    export CC="$GITHUB_WORKSPACE/.wiswa-ci/scan-build-cc"
    export CXX="$GITHUB_WORKSPACE/.wiswa-ci/scan-build-cxx"
    %s
  ||| % [
    if std.startsWith(config.runs_on, 'macos') then '"$(xcrun --find clang)"' else 'clang',
    if std.startsWith(config.runs_on, 'macos') then '"$(xcrun --find clang++)"' else 'clang++',
    command,
  ];
  {
    name: 'Clang static analysis',
    on: {
      push: {},
      pull_request: {},
      workflow_dispatch: {},
    },
    permissions: {},
    jobs: {
      pages: {
        name: 'Pages',
        needs: ['analyze'],
        'if': "${{ github.event_name != 'pull_request' }}",
        uses: '$/.github/workflows/pages.yml',
        permissions: { contents: 'read', pages: 'write', 'id-token': 'write' },
      },
      analyze: {
        name: 'scan-build',
        'runs-on': config.runs_on,
        permissions: { contents: 'read' },
        defaults: { run: { shell: 'bash' } },
        [if std.length(std.objectFields(config.env)) > 0 then 'env']: config.env,
        steps: [utils.checkout({ with: config.checkout_options })] + config.setup_steps +
               (if scoped then [{
                  name: 'Prepare scoped compiler wrappers',
                  run: |||
                    mkdir -p .wiswa-ci
                    install -m 755 .github/scripts/static-analysis.py .wiswa-ci/scan-build-cc
                    install -m 755 .github/scripts/static-analysis.py .wiswa-ci/scan-build-cxx
                  |||,
                }] else []) + [
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
            env: { SCAN_BUILD_CONFIGURE_COMMAND: scope_build(config.configure_command) },
            run: 'mkdir -p scan-build-report\n' +
                 'scan-build ' + compiler_options + exclude_options + ' -o "$RUNNER_TEMP/scan-configure" ' +
                 'bash -eo pipefail -c "$SCAN_BUILD_CONFIGURE_COMMAND" ' +
                 '2>&1 | tee scan-build-report/build.log',
          },
          {
            id: 'analysis',
            name: 'Analyze a clean build',
            env: { SCAN_BUILD_BUILD_COMMAND: scope_build(config.build_command) },
            run: |||
              mkdir -p scan-build-report
              scan-build %s -plist-html --keep-empty -v \
                -o scan-build-report/results bash -eo pipefail -c "$SCAN_BUILD_BUILD_COMMAND" \
                2>&1 | tee -a scan-build-report/build.log
            ||| % (compiler_options + exclude_options),
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
              import os
              import shutil
              from pathlib import Path

              root = Path('scan-build-report')
              root.mkdir(exist_ok=True)
              reports = sorted(root.glob('results/*/index.html'))
              units = list(root.glob('results/*/*.plist'))
              failures = list(root.glob('results/*/failures/*'))
              complete = os.environ['ANALYSIS_OUTCOME'] == 'success' and bool(units) and not failures
              print(os.environ['ANALYSIS_SCOPE'])
              print(f'{len(units)} translation units. {len(failures)} analyzer failure files.')
              if not complete:
                  raise SystemExit('Incomplete analysis; inspect the build log and analyzer failures.')
              if len(reports) > 1:
                  raise SystemExit('Expected a single Clang HTML report.')
              if reports:
                  shutil.copytree(reports[0].parent, root, dirs_exist_ok=True)
              else:
                  for unit in units:
                      shutil.copy2(unit, root)
                  (root / 'index.html').write_text(
                      '<!doctype html><html lang="en"><meta charset="utf-8">'
                      '<title>Clang static analysis</title>'
                      '<h1>No bugs reported by the enabled Clang checkers.</h1>', encoding='utf-8')
              shutil.rmtree(root / 'results')
              PY
            |||,
          },
          upload('scan-build-${{ github.sha }}', 'scan-build-report') + {
            'if': '${{ !cancelled() }}',
          },
        ],
      },
    },
  }
