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
  // cc-session-recover
  '/HANDOFF.md',
  '/.claude/auto-continue.md',
  '/.claude/standing-instructions.md',
  '/.claude/statusline-quota-cache.sh',
  '/.claude/hooks/inject-standing-instructions.sh',
  '/.claude/hooks/remind-on-prompt.sh',
  '/.claude/settings.example.json',
  '/.claude/hooks/log-stop-failure.sh',
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
