/**
 * @file _config.libsonnet
 * @namespace _config
 * @brief Jekyll configuration for GitHub Pages.
 * @sa [Jekyll Configuration](https://jekyllrb.com/docs/configuration/)
 */
{
  /**
   * @brief Paths excluded from the Jekyll build (not copied to the site output).
   * `CHANGELOG.md` is excluded by default so it is not published as a page on GitHub Pages.
   */
  exclude: ['CHANGELOG.md'],
  /** @brief Jekyll theme to use. */
  theme: 'jekyll-theme-hacker',
}
