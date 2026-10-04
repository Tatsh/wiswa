local common = import 'github/workflows/_qa-common.libsonnet';
local utils = import 'utils.libsonnet';

function(settings)
  {
    '.github/workflows/prettier.yml': utils.manifestYaml(common.prettier(settings)),
    '.github/workflows/markdownlint.yml': utils.manifestYaml(common.markdownlint(settings)),
    '.github/workflows/spelling.yml': utils.manifestYaml(common.spelling(settings)),
  }
