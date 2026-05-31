/**
 * @file shared-ignore.libsonnet
 * @brief Default list of glob patterns to ignore in various tools.
 * @namespace shared_ignore
 * @var string[] ignore_patterns
 */
[
  '*.kate-swp',
  '*.log',
  '*~',
  '.*.swp',
  '.*_cache/',
  '.DS_Store*',
  '.coverage',
  '.cspellcache',
  '.directory',
  '.pnp.*',
  '/.wiswa-ci/',
  '/.yarn/install-state.gz',
  '/build/',
  'node_modules/',
  /*
   * Workaround for https://github.com/anthropics/claude-code/issues/46584:
   * Claude Code creates stub shell/editor config files at the project root.
   * Remove these entries once the upstream issue is fixed.
   */
  '/.bash_profile',
  '/.bashrc',
  '/.claude/commands',
  '/.claude/hooks',
  '/.gitconfig',
  '/.gitmodules',
  '/.idea',
  '/.mcp.json',
  '/.profile',
  '/.ripgreprc',
  '/.zprofile',
  '/.zshrc',
]
