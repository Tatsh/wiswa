/**
 * @file ruff.libsonnet
 * @brief Default configuration for Ruff linter and formatter.
 * @namespace ruff
 * @sa [Ruff Documentation](https://docs.astral.sh/ruff/configuration/)
 */
{
  /** @brief Directory to use for Ruff cache. */
  'cache-dir': '~/.cache/ruff',
  /** @brief If true, force exclude files even if they are explicitly included. */
  'force-exclude': true,
  /** @brief Configuration for code formatting. */
  format: {
    /** @brief If true, format code in docstrings. */
    'docstring-code-format': true,
    /** @brief Line ending style to use. */
    'line-ending': 'lf',
    /** @brief If true, enable preview features. */
    preview: true,
    /** @brief Quote style to use. */
    'quote-style': 'single',
  },
  /** @brief Maximum allowed line length. */
  'line-length': 100,
  /** @brief List of namespace packages in the project. */
  'namespace-packages': ['docs', 'tests'],
  /** @brief If true, apply fixes that may be unsafe. */
  'unsafe-fixes': true,
  /** @brief Configuration for Ruff linter. */
  lint: {
    'extend-select': ['ALL'],
    /** @brief List of error codes to ignore. */
    ignore: [
      'ANN401',
      'CPY001',
      // D201 wants no blank line after the signature, yet D203 wants a blank line after a ``class`` line.
      'D203',
      // D204 wants a blank line after the class docstring; YAPF removes it.
      'D204',
      // Disabled because we want """ to always be on its own line for multi-line docstrings.
      'D212',
      // Personal preference really. ``raise NoRowFound`` is just as clear as ``raise NoRowFoundError``.
      'N818',
      'S404',
      // Disabled because of false positives.
      'S603',
      'TD002',
    ],
    /** @brief If true, enable preview features. */
    preview: true,
    'flake8-builtins': {
      'allowed-modules': ['types', 'typing'],
      // 'strict-checking': true,
    },
    'flake8-quotes': {
      'inline-quotes': 'single',
      'multiline-quotes': 'double',
    },
    /** @brief Configuration for Ruff's isort implementation. */
    isort: {
      /** @brief If true, isort will be case-sensitive when sorting imports. */
      'case-sensitive': true,
      'combine-as-imports': true,
      'from-first': true,
      'required-imports': ['from __future__ import annotations'],
      'section-order': ['future', 'standard-library', 'third-party', 'local-folder'],
    },
    /** @brief Configuration for Ruff's mccabe implementation. */
    mccabe: {
      'max-complexity': 20,
    },
    'pep8-naming': {
      'extend-ignore-names': [
        'test_*',
      ],
    },
    pydocstyle: {
      convention: 'numpy',
    },
    pylint: {
      'max-args': 20,
      'max-branches': 20,
      'max-locals': 20,
      'max-positional-args': 15,
      'max-public-methods': 30,
      'max-returns': 10,
      'max-statements': 100,
    },
  },
}
