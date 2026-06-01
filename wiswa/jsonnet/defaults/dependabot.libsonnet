/**
 * @file defaults/dependabot.libsonnet
 * @namespace dependabot
 * @brief Default configuration for Dependabot, a tool for keeping dependencies up to date.
 */
{
  local cooldown = { 'default-days': 7 },
  local groups = {
    development: { 'dependency-type': 'development' },
    production: { 'dependency-type': 'production' },
  },
  local schedule = { interval: 'weekly' },
  local c_cpp_settings = [{
    cooldown: cooldown,
    directory: '/',
    'package-ecosystem': 'vcpkg',
    schedule: schedule,
  }],
  local python_settings(settings) = [{
    cooldown: cooldown,
    directory: '/',
    groups: groups,
    'package-ecosystem': if settings.package_manager == 'uv' then 'uv' else 'pip',
    schedule: schedule,
  }],
  /**
   * @brief Get dependabot configuration.
   * @param settings The project settings.
   * @returns An object representing the dependabot configuration.
   * @pt object
   * @rv object
   * @sa [Dependabot Configuration Options](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuring-dependabot-version-updates#configuration-options)
   */
  updates(settings):: {
    updates: [
               {
                 cooldown: cooldown,
                 directory: '/',
                 groups: groups,
                 'package-ecosystem': 'npm',
                 schedule: schedule,
               },
               {
                 cooldown: cooldown,
                 directory: '/',
                 groups: {
                   'github-actions': { patterns: ['*'] },
                 },
                 'package-ecosystem': 'github-actions',
                 schedule: schedule,
               },
             ]
             + (if settings.project_type == 'python' then python_settings(settings) else [])
             + (if settings.project_type == 'c' || settings.project_type == 'c++' then c_cpp_settings else []),
    version: 2,
  },
}
