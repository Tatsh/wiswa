/**
 * @file uv.libsonnet
 * @namespace uv
 * @brief Configuration for uv, a Python package and project manager.
 */
{
  /**
   * @brief Default groups for uv dependency management.
   *
   * When using uv, dev dependencies live in `[dependency-groups]` in pyproject.toml.
   */
  'default-groups': ['dev'],
}
