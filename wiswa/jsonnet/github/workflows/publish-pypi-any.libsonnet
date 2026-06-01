local check_workflows = import 'github/workflows/_check-workflows.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local is_uv = settings.package_manager == 'uv';
  local optional_workflows = std.set(
    ['Prettier', 'QA', 'Spelling', 'markdownlint'] +
    (if settings.want_tests then ['Tests'] else [])
  );
  local required_workflows = std.set(
    (if settings.want_appimage then ['AppImage'] else []) +
    (if settings.want_pyinstaller then ['PyInstaller'] else []) +
    (if utils.wantFlatpakOutputs(settings) then ['Flatpak'] else []) +
    (if settings.want_snap then ['Snap'] else []) +
    settings.github.workflows.release_gate_workflows
  );
  {
    jobs: {
      check: check_workflows.job(required_workflows, optional_workflows),
      publish: {
        [if settings.github.workflows.release_environment != '' then 'environment']:
          settings.github.workflows.release_environment,
        needs: ['check'],
        permissions: {
          contents: 'write',
          'id-token': 'write',
        },
        'runs-on': settings.github.workflows.publish_pypi_any.runs_on,
        steps: [
          utils.checkout(),
          {
            uses: 'actions/setup-python@' + utils.githubLatestActionSha('actions', 'setup-python'),
            with: {
              'python-version': settings.github.workflows.publish_pypi_any.python_version,
            },
          },
        ] + (if is_uv then [{
               name: 'Install uv',
               uses: 'astral-sh/setup-uv@' + utils.githubLatestActionSha('astral-sh', 'setup-uv'),
               with: {
                 'enable-cache': false,
               },
             }] else [{
               name: 'Install Poetry',
               run: 'pipx install poetry',
             }]) + [
          {
            run: if is_uv then 'uv build' else 'poetry build',
          },
          {
            uses: 'pypa/gh-action-pypi-publish@' + utils.githubLatestActionSha('pypa', 'gh-action-pypi-publish'),
          },
          utils.ghDraftReleaseStep(['dist/*.tar.gz', 'dist/*.whl']),
        ],
      },
    },
    name: 'Publish',
    on: {
      push: {
        tags: [
          'v*',
        ],
      },
    },
    permissions: {},
  }
