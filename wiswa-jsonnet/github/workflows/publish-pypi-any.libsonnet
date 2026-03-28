local check_workflows = import 'github/workflows/_check-workflows.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  local is_uv = settings.package_manager == 'uv';
  local watched_workflows = std.sort(
    ['QA', 'Tests'] +
    (if settings.want_main || settings.has_multiple_entry_points then
       (if settings.supported_platforms == 'all' || std.member(settings.supported_platforms, 'linux') then ['AppImage'] else []) +
       (if settings.supported_platforms == 'all' || std.member(settings.supported_platforms, 'windows') || std.member(settings.supported_platforms, 'macos') then ['PyInstaller'] else [])
     else []) +
    (if settings.want_flatpak then ['Flatpak'] else []) +
    (if settings.want_snap then ['Snap'] else [])
  );
  {
    jobs: {
      check: check_workflows.job(watched_workflows),
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
