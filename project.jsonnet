local jekyll = import '_config.libjsonnet';
local citation = import 'citation.libjsonnet';
local github = import 'github.libjsonnet';
local package_json = import 'package.libjsonnet';
local pyproject = import 'pyproject.libjsonnet';
local utils = import 'utils.libjsonnet';
local yarnrc = import 'yarnrc.libjsonnet';

function(settings)
  {
    '.gitattributes': utils.manifestLines(import 'gitattributes.libjsonnet'),
    '.github/FUNDING.yml': utils.manifestYaml(github.funding(settings)),
    '.github/dependabot.yml': utils.manifestYaml(github.dependabot),
    '.gitignore': utils.manifestIgnore([]),
    '.pre-commit-config.yaml': utils.manifestYaml(import 'pre-commit-config.libjsonnet'),
    '.prettierignore': utils.manifestIgnore(['*.jsonnet', '/.yarn/**/*.cjs']),
    '.vscode/extensions.json': std.manifestJson(import 'vscode/extensions.libjsonnet'),
    '.vscode/launch.json': std.manifestJson(import 'vscode/launch.libjsonnet'),
    '.vscode/settings.json': std.manifestJson(import 'vscode/settings.libjsonnet'),
    '.yarnrc.yml': utils.manifestYaml(yarnrc(settings)),
    'CITATION.cff': utils.manifestYaml(citation(settings)),
    '_config.yml': utils.manifestYaml(jekyll(settings)),
    'package.json': std.manifestJson(package_json(settings)),
    'pyproject.toml': utils.manifestToml(pyproject(settings)),
    'tests/pyproject.toml': utils.manifestToml(import 'pyproject-tests.libjsonnet'),
  } + github.workflows(settings)
