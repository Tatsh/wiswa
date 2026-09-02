/**
 * @file defaults/cz.libsonnet
 * @namespace cz
 * @brief Default configuration for commitizen.
 */
local utils = import 'utils.libsonnet';

{
  /**
   * @brief Get commitizen configuration.
   * @param settings The project settings.
   * @returns An object representing the commitizen configuration.
   * @pt object
   * @rv object
   * @sa [Commitizen Configuration Options](https://commitizen-tools.github.io/commitizen/config/configuration_file/#configuration-options)
   */
  get(settings):: {
    local cpp_files = if settings.project_type == 'c' || settings.project_type == 'c++' then [
      'CMakeLists.txt',
      'vcpkg.json',
    ] else [],
    local man = if settings.want_man then ['man/%s.1' % settings.project_name] else [],
    local snap = if settings.want_snap then ['snapcraft.yaml'] else [],
    local flatpak = if utils.wantFlatpakOutputs(settings) then ['%s.yml' % settings.publishing.flathub] else [],
    local cff_files = if settings.want_cff then ['CITATION.cff'] else [],
    commitizen: {
      name: 'cz_path',
      remove_path_prefixes: ['include', 'src'],
      tag_format: 'v$version',
      version_files: std.set([
        '.wiswa.jsonnet',
        'README.md',
        'package.json',
      ] + cff_files + cpp_files + flatpak + man + snap),
      version_provider: 'npm',
      version_scheme: 'semver',
    },
  },
}
