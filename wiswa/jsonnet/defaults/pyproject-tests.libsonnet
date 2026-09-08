/**
 * @file pyproject-tests.libsonnet
 * @namespace pyproject_tests
 * @brief `[tool]` section in `tests/pyproject.toml`.
 */
{
  tool: {
    /** @brief `[tool.ruff]` section in `pyproject.toml`. */
    ruff: {
      /** @brief Extend the top-level `pyproject.toml` with this Ruff configuration. */
      extend: '../pyproject.toml',
      /** @brief `[tool.ruff.lint]` section in `pyproject.toml`. */
      lint: {
        /** @brief Ignore these rules for tests. */
        'extend-ignore': [
          'assert',
          'docstring-missing-returns',
          'hardcoded-password-func-arg',
          'hardcoded-password-string',
          'implicit-namespace-package',
          'import-outside-top-level',
          'magic-value-comparison',
          /**
           * Fixtures that install a test-wide guard, such as restoring the working directory, have
           * no call site to be injected into.
           */
          'pytest-fixture-autouse',
          'undocumented-magic-method',
          'undocumented-public-class',
          'undocumented-public-function',
          'undocumented-public-method',
          'undocumented-public-module',
          'undocumented-public-nested-class',
          'undocumented-public-package',
          'unused-function-argument',
          'unused-method-argument',
        ],
        /**
         * @brief If true, enable preview features.
         *
         * Repeated here rather than inherited through ``extend``, because Ruff resolves the
         * selectors in a configuration file before merging it with the one it extends, and a rule
         * named rather than coded is only a valid selector under preview mode.
         */
        preview: true,
        /** @brief `[tool.ruff.lint.pep8-naming]` section in `pyproject.toml`. */
        'pep8-naming': {
          /** @brief Ignore these names for tests. */
          'extend-ignore-names': [
            'test_*',
          ],
        },
      },
    },
  },
}
