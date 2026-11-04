local utils = import 'utils.libsonnet';

function(settings)
  local config = settings.github.workflows.scan_build;
  local has_docs = std.length(config.documentation_steps) > 0;
  local action(repository) = 'actions/' + repository + '@' +
                             utils.githubLatestActionSha('actions', repository);
  {
    name: 'Pages',
    on: {
      workflow_call: {},
    },
    permissions: {},
    jobs: {
      [if has_docs then 'documentation']: {
        name: 'Documentation',
        'runs-on': 'ubuntu-latest',
        permissions: { contents: 'read' },
        steps: [utils.checkout({ with: config.checkout_options })] + config.documentation_steps + [{
          uses: action('upload-artifact'),
          with: { name: 'documentation', path: config.documentation_path, 'if-no-files-found': 'error' },
        }],
      },
      publish: {
        name: 'Publish reports and documentation',
        [if has_docs then 'needs']: ['documentation'],
        'runs-on': 'ubuntu-latest',
        concurrency: utils.publishConcurrency('pages'),
        environment: { name: 'github-pages', url: '${{ steps.deployment.outputs.page_url }}' },
        permissions: { pages: 'write', 'id-token': 'write' },
        steps: [{
          uses: action('download-artifact'),
          with: {
            name: 'scan-build-${{ github.sha }}',
            path: '_report',
          },
        }] + (if has_docs then [{
                uses: action('download-artifact'),
                with: { name: 'documentation', path: '_documentation' },
              }] else []) + [
          {
            name: 'Assemble site with latest report',
            run: |||
              mkdir -p _site
              if [ -d _documentation ]; then
                cp -a _documentation/. _site/
              fi
              rm -rf _site/scan-build
              mkdir -p _site/scan-build
              cp -a _report/. _site/scan-build/
              python3 - <<'PY'
              from pathlib import Path

              root = Path('_site')
              if not (root / 'index.html').exists():
                  (root / 'index.html').write_text(
                      '<!doctype html><html lang="en"><meta charset="utf-8">'
                      '<title>Clang static analysis</title>'
                      '<a href="scan-build/">Clang static analysis reports</a>', encoding='utf-8')
              (root / '.nojekyll').touch()
              PY
              tar --dereference --hard-dereference -cf "$RUNNER_TEMP/artifact.tar" \
                --exclude=.git -C _site .
            |||,
          },
          { name: 'Configure Pages', uses: action('configure-pages') },
          {
            uses: action('upload-artifact'),
            with: {
              name: 'github-pages',
              path: '${{ runner.temp }}/artifact.tar',
              'if-no-files-found': 'error',
              'retention-days': 1,
            },
          },
          { id: 'deployment', name: 'Deploy Pages', uses: action('deploy-pages') },
          {
            name: 'Report URL',
            env: { PAGE_URL: '${{ steps.deployment.outputs.page_url }}' },
            run: 'echo "[Clang report](${PAGE_URL}scan-build/)" >> "$GITHUB_STEP_SUMMARY"',
          },
        ],
      },
    },
  }
