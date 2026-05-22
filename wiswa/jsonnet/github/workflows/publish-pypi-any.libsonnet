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
        needs: ['check'],
        'runs-on': settings.github.workflows.publish_pypi_any.runs_on,
        steps: [
          {
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
          {
            uses: 'actions/setup-python@' + utils.githubLatestActionTag('actions', 'setup-python'),
            with: {
              'python-version': settings.github.workflows.publish_pypi_any.python_version,
            },
          },
        ] + (if is_uv then [{
               name: 'Install uv',
               uses: 'astral-sh/setup-uv@' + utils.githubLatestActionTag('astral-sh', 'setup-uv'),
             }] else [{
               name: 'Install Poetry',
               run: 'pipx install poetry',
             }]) + [
          {
            run: if is_uv then 'uv build' else 'poetry build',
          },
          {
            uses: 'pypa/gh-action-pypi-publish@release/v1',
          },
          {
            uses: 'softprops/action-gh-release@' + utils.githubLatestActionTag('softprops', 'action-gh-release'),
            with: {
              draft: true,
              files: |||
                dist/*.tar.gz
                dist/*.whl
              |||,
            },
          },
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
    permissions: {
      contents: 'write',
      'id-token': 'write',
    },
  }
