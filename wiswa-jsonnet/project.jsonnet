local github = import 'github.libjsonnet';
local utils = import 'utils.libjsonnet';

function(settings)
  local github_items = if settings.using_github then {
    '.github/FUNDING.yml': utils.manifestYaml(settings.github.funding),
    '.github/dependabot.yml': utils.manifestYaml(settings.github.dependabot),
    '_config.yml': utils.manifestYaml(settings.github.pages_config),
  } + github.workflows(settings) else {};
  local gitlab_items = if settings.using_gitlab then {
    '.gitlab-ci.yml': utils.manifestYaml(utils.settings.gitlab_ci),
  } else {};
  local readthedocs_items = if settings.want_docs then {
    '.readthedocs.yaml': utils.manifestYaml(settings.readthedocs),
  } else {};
  local tests_items = if settings.want_tests then {
    'tests/pyproject.toml': utils.manifestToml(settings.tests_pyproject),
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
    'pyproject.toml': utils.manifestToml(settings.pyproject),
  } + tests_items + github_items + gitlab_items + readthedocs_items
