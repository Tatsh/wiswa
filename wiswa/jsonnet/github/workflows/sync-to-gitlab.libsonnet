local utils = import 'utils.libsonnet';

function(settings)
  local mirror_gitlab_config = {
    default_branch_protection: settings.gitlab.default_branch_protection,
    project_approvals: settings.gitlab.project_approvals,
    project_settings: settings.gitlab.project_settings,
    push_rules: settings.gitlab.push_rules,
  };
  {
    jobs: {
      'sync-to-gitlab': {
        'runs-on': 'ubuntu-latest',
        steps: [
          {
            name: 'Checkout repository',
            uses: 'actions/checkout@' + utils.githubLatestActionTag('actions', 'checkout'),
          },
          {
            env: {
              GITHUB_REPO_URI: 'https://github.com/${{ github.repository }}.git',
            },
            name: 'Clone GitHub repository as mirror',
            run: 'git clone --mirror "$GITHUB_REPO_URI" repo.git',
          },
          {
            env: {
              GITLAB_REPO_URI: settings.gitlab_mirror_uri,
              GITLAB_TOKEN: '${{ secrets.GITLAB_TOKEN }}',
            },
            name: 'Push to GitLab mirror',
            run: |||
              if [ -z "$GITLAB_REPO_URI" ] || [ -z "$GITLAB_TOKEN" ]; then
                echo 'GITLAB_REPO_URI and GITLAB_TOKEN must be set.' >&2
                exit 1
              fi
              case "$GITLAB_REPO_URI" in
                https://*) ;;
                *) echo 'GITLAB_REPO_URI must start with https://.' >&2; exit 1 ;;
              esac
              authenticated_url="https://oauth2:${GITLAB_TOKEN}@${GITLAB_REPO_URI#https://}"
              git -C repo.git push --mirror "$authenticated_url"
            |||,
          },
          {
            name: 'Install wiswa-vcs',
            run: 'pipx install wiswa-vcs',
          },
          {
            env: {
              DEFAULT_BRANCH: settings.default_branch,
              GH_TOKEN: '${{ secrets.GITHUB_TOKEN }}',
              GITHUB_REPO_URI: 'https://github.com/${{ github.repository }}.git',
              GITLAB_CONFIG_JSON: std.manifestJsonEx(mirror_gitlab_config, ''),
              GITLAB_REPO_URI: settings.gitlab_mirror_uri,
              GITLAB_TOKEN: '${{ secrets.GITLAB_TOKEN }}',
            },
            name: 'Sync GitLab project metadata',
            run: 'wiswa-sync-gh-gl',
          },
        ],
      },
    },
    name: 'Sync to GitLab',
    on: {
      push: {},
      workflow_dispatch: {},
    },
    permissions: {
      contents: 'read',
    },
  }
