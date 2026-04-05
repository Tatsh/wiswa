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
  '/.cursor/plans/',
  '/.wiswa-ci/',
  '/.yarn/install-state.gz',
  '/build/',
  'node_modules/',
]
