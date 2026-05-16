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
          'ARG001',
          'ARG002',
          'D100',
          'D101',
          'D102',
          'D103',
          'D104',
          'D105',
          'D106',
          'DOC201',
          'INP001',
          'PLC0415',
          'PLR2004',
          'S101',
          'S105',
          'S106',
        ],
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
