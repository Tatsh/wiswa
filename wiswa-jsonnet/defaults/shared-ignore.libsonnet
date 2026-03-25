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
  '.DS_Store*',
  '.*_cache/',
  '.coverage',
  '.cspellcache',
  '.directory',
  '.pnp.*',
  '/.yarn/install-state.gz',
  '/build/',
  'node_modules/',
]
