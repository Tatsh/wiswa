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
  'default-groups': 'all',
  /**
   * @brief Time period for excluding newer versions of dependencies.
   *
   * Limit candidate packages to those that were uploaded prior to the given date.
   * Accepts RFC 3339 timestamps (e.g., 2006-12-02T02:07:43Z), a "friendly" duration (e.g.,
   * 24 hours, 1 week, 30 days), or an ISO 8601 duration (e.g., PT24H, P7D, P30D).
   *
   * Durations do not respect semantics of the local time zone and are always resolved to a fixed
   * number of seconds assuming that a day is 24 hours (e.g., DST transitions are ignored). Calendar
   * units such as months and years are not allowed.
   */
  'exclude-newer': '1 week',
}
