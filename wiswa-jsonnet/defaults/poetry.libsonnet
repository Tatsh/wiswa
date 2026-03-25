/**
 * @file poetry.libsonnet
 * @namespace poetry
 * @brief Configuration for Poetry, a Python dependency management tool.
 */
{
  /** @brief Configuration for Poetry, a Python dependency management tool. */
  /** @brief Optional dependency groups for organizing dependencies. */
  group: {
    /** @brief Development dependencies, used for development and testing purposes. */
    dev: {
      /** @brief Whether this group is optional. */
      optional: true,
    },
  },
}
