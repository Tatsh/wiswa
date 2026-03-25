/**
 * @file defaults/pyproject.libsonnet
 * @namespace pyproject
 * @brief Default settings for `pyproject.toml`.
 */
{
  /** Project metadata, including name, version, description, authors, and license. */
  project: import 'defaults/project.libsonnet',
  /** Tool-specific configurations for various Python development tools. */
  tool: {
    /** Configuration for Commitizen. */
    commitizen: {
      /** Extension to use by default. */
      name: 'cz_path',
      /** Prefixes to remove when using cz-path. */
      remove_path_prefixes: ['include', 'src'],
      /** Format for version tags. */
      tag_format: 'v$version',
      /** List of files to update with the new version. */
      version_files: [
        '.wiswa.jsonnet',
        'CITATION.cff',
        'README.md',
        'package.json',
      ],
      /** Provider for versioning, such as "pep440" or "pep621". */
      version_provider: 'pep621',
    },
    /** Configuration for code coverage. */
    coverage: import 'defaults/coverage.libsonnet',
    /** Configuration for doc8, a documentation linter. */
    doc8: {
      /** Maximum line length for documentation files. */
      'max-line-length': 100,
    },
    /** Configuration for mypy. */
    mypy: import 'defaults/mypy.libsonnet',
    /** Configuration for Poetry. */
    poetry: import 'defaults/poetry.libsonnet',
    /** Configuration for Pyright. */
    pyright: import 'defaults/pyright.libsonnet',
    /** Configuration for pytest. */
    pytest: import 'defaults/pytest.libsonnet',
    /** Configuration for Ruff. */
    ruff: import 'defaults/ruff.libsonnet',
    /** Configuration for uv. */
    uv: import 'defaults/uv.libsonnet',
    /** Configuration for YAPF. */
    yapf: import 'defaults/yapf.libsonnet',
    /** Configuration for YAPF ignore patterns. */
    yapfignore: import 'defaults/yapfignore.libsonnet',
  },
}
