/**
 * @file defaults/dependabot.libsonnet
 * @namespace dependabot
 * @brief Default configuration for Dependabot, a tool for keeping dependencies up to date.
 */
{
  local cooldown = { 'default-days': 7 },
  local python_settings(settings) = [{
    cooldown: cooldown,
    directory: '/',
    'package-ecosystem': if settings.package_manager == 'uv' then 'uv' else 'pip',
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
    'multi-ecosystem-groups': {
      infrastructure: {
        schedule: {
          interval: 'weekly',
        },
      },
    },
    updates: [
      {
        cooldown: cooldown,
        directory: '/',
        'package-ecosystem': 'npm',
      },
      {
        directory: '/',
        'package-ecosystem': 'github-actions',
      },
    ] + if settings.project_type == 'python' then python_settings(settings) else [],
    version: 2,
  },
}
