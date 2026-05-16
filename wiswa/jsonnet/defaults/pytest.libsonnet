/**
 * @file pytest.libsonnet
 * @namespace pytest
 * @brief Default configuration for pytest.
 */
{
  /** @brief Options. */
  ini_options: {
    /** @brief Use the standalone mock module instead of the one bundled with pytest. */
    mock_use_standalone_module: true,
    /**
     * @brief List of file glob patterns that pytest will consider as test modules.
     * @var string[]
     */
    norecursedirs: [
      'node_modules',
    ],
    /**
     * @brief List of directory patterns to avoid when recursing for test collection.
     * @var string[]
     */
    python_files: [
      'tests.py',
      'test_*.py',
      '*_tests.py',
    ],
    /**
     * @brief List of directories to search for tests when no specific paths are given.
     * @var string[]
     */
    testpaths: [
      'tests',
    ],
  },
}
