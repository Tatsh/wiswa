local cleanup = import 'github/workflows/cleanup.libsonnet';
local codeql = import 'github/workflows/codeql.libsonnet';
local flatpak_python = import 'github/workflows/flatpak-python.libsonnet';
local lua_publish = import 'github/workflows/publish-luarocks.libsonnet';
local npm_publish_any = import 'github/workflows/publish-npm-any.libsonnet';
local pypi_publish_any = import 'github/workflows/publish-pypi-any.libsonnet';
local winget_publish = import 'github/workflows/publish-winget.libsonnet';
local qa_other = import 'github/workflows/qa-other.libsonnet';
local qa_python = import 'github/workflows/qa-python.libsonnet';
local qa_typescript = import 'github/workflows/qa-typescript.libsonnet';
local release = import 'github/workflows/release.libsonnet';
local snap_python = import 'github/workflows/snap-python.libsonnet';
local tests_typescript = import 'github/workflows/tests-typescript.libsonnet';
local tests = import 'github/workflows/tests.libsonnet';
local utils = import 'utils.libsonnet';

{
  /**
   * Generate GitHub Actions workflow files based on the provided settings.
   * @param settings Object containing configuration for the workflows.
   * @returns An object mapping file paths to their contents, representing the GitHub Actions
   * workflows.
   */
  workflows(settings): (
    if settings.project_type == 'python' then qa_python(settings)
    else if settings.project_type == 'typescript' then
      { '.github/workflows/qa.yml': utils.manifestYaml(qa_typescript(settings)) }
    else
      { '.github/workflows/qa.yml': utils.manifestYaml(qa_other(settings)) }
  ) + (
    if settings.want_codeql then {
      '.github/workflows/codeql.yml': utils.manifestYaml(codeql(settings)),
    } else {}
  ) + (
    if settings.want_tests then {
      '.github/workflows/tests.yml': utils.manifestYaml(
        if settings.project_type == 'typescript' then tests_typescript(settings)
        else tests(settings)
      ),
    } else {}
  ) + (
    if settings.project_type == 'typescript' && !settings.private then {
      '.github/workflows/publish.yml': utils.manifestYaml(npm_publish_any(settings)),
    } else {}
  ) + (
    if settings.project_type == 'python' && !settings.private then {
      '.github/workflows/publish.yml': utils.manifestYaml(pypi_publish_any(settings)),
    } else {}
  ) + (
    if settings.project_type == 'lua' && !settings.private then {
      '.github/workflows/publish.yml': utils.manifestYaml(lua_publish),
    } else {}
  ) + (
    if (settings.project_type == 'c++' || settings.project_type == 'c') && settings.want_winget then {
      '.github/workflows/publish-winget.yml': utils.manifestYaml(winget_publish(settings)),
    } else {}
  ) + (
    if settings.want_flatpak && settings.project_type == 'python' then {
      '.github/workflows/flatpak.yml': utils.manifestYaml(flatpak_python(settings)),
    } else {}
  ) + (
    if settings.want_snap && settings.project_type == 'python' then {
      '.github/workflows/snap.yml': utils.manifestYaml(snap_python(settings)),
    } else {}
  ) + (
    if (settings.want_main || settings.has_multiple_entry_points) && settings.project_type == 'python' then {
      '.github/workflows/release.yml': utils.manifestYaml(release(settings)),
    } else {}
  ) + (
    if settings.private then {
      '.github/workflows/cleanup.yml': utils.manifestYaml(cleanup(settings)),
    } else {}
  ),
}
