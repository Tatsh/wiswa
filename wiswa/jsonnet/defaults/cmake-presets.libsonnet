/**
 * @file defaults/cmake-presets.libsonnet
 * @namespace cmake_presets
 * @brief Default settings for `CMakePresets.json`.
 */
{
  /**
   * @brief CMake presets for use with vcpkg.
   *
   *
   * <dl>
   * <dt>Structure</dt>
   * <dd>
   * @code
   * {
   *   binaryDir: string;
   *   cacheVariables: { [key: string]: string; };
   *   generator: string;
   *   name: string;
   * }
   * @endcode
   * </dd>
   * </dt>
   * </dl>
   */
  configurePresets: [
    {
      binaryDir: '${sourceDir}/build',
      cacheVariables: {
        CMAKE_TOOLCHAIN_FILE: '$env{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake',
      },
      generator: 'Ninja',
      name: 'vcpkg',
    },
  ],
  /** @brief Version of the CMake presets. */
  version: 2,
}
