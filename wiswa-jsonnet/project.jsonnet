local github = import 'github.libjsonnet';
local utils = import 'utils.libjsonnet';

function(settings)
  local github_items = if settings.using_github then {
                                                       '.github/FUNDING.yml': utils.manifestYaml(settings.github.funding),
                                                       '.github/dependabot.yml': utils.manifestYaml(settings.github.dependabot),
                                                     } + (
                                                       if settings.github.pages_using_jekyll then
                                                         { '_config.yml': utils.manifestYaml(settings.github.pages_config) } else {}
                                                     ) +
                                                     github.workflows(settings) else {};
  local gitlab_items = if settings.using_gitlab then {
    '.gitlab-ci.yml': utils.manifestYaml(utils.settings.gitlab_ci),
  } else {};
  local readthedocs_items = if settings.want_docs && settings.project_type == 'python' then {
    '.readthedocs.yaml': utils.manifestYaml(settings.readthedocs),
  } else {};
  local tests_items = if settings.project_type == 'python' && settings.want_tests then {
    'tests/pyproject.toml': utils.manifestToml(settings.tests_pyproject),
  } else {};
  local python_items = if settings.project_type == 'python' then {
    'pyproject.toml': utils.manifestToml(settings.pyproject),
  } else {};
  local cz_json = if settings.project_type != 'python' then {
    '.cz.json': std.manifestJson(settings.cz),
  } else {};
  local c_cpp_items = if settings.project_type == 'c' || settings.project_type == 'c++' then {
    '.clang-format': utils.manifestYaml(settings.clang_format),
    '.cmake-format.yaml': utils.manifestYaml(settings.cmake_format),
    '.vscode/c_cpp_properties.json': std.manifestJson(settings.vscode.c_cpp),
    'CMakePresets.json': std.manifestJson(settings.cmake_presets),
    'CMakeUserPresets.json': std.manifestJson(settings.cmake_user_presets),
    'vcpkg.json': std.manifestJson(settings.vcpkg),
    'vcpkg-configuration.json': std.manifestJson(settings.vcpkg_config),
  } else {};
  local xcode_items = if settings.project_type == 'xcode' then {
    '.clang-format': utils.manifestYaml(settings.clang_format),
  } else {};
  local lua_items = if settings.project_type == 'lua' then {
    '.luacheckrc': utils.manifestLines(settings.luacheck),
  } else {};
  local typescript_items = if settings.project_type == 'typescript' then {
    'tsconfig.json': std.manifestJson(settings.tsconfig),
  } else {};
  {
    '.gitattributes': utils.manifestLines(settings.gitattributes),
    '.gitignore': utils.manifestLines(settings.gitignore),
    '.pre-commit-config.yaml': utils.manifestYaml(settings.pre_commit_config),
    '.prettierignore': utils.manifestLines(settings.prettierignore),
    '.vscode/extensions.json': std.manifestJson(settings.vscode.extensions),
    '.vscode/launch.json': std.manifestJson(settings.vscode.launch),
    '.vscode/settings.json': std.manifestJson(settings.vscode.settings),
    '.yarnrc.yml': utils.manifestYaml(settings.yarnrc),
    'CITATION.cff': utils.manifestYaml(settings.citation),
    'package.json': std.manifestJson(settings.package_json),
  } +
  c_cpp_items +
  cz_json +
  github_items +
  gitlab_items +
  lua_items +
  python_items +
  readthedocs_items +
  tests_items +
  typescript_items +
  xcode_items
