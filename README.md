# wiswa

<!-- WISWA-GENERATED-README:START -->

[![Python versions](https://img.shields.io/pypi/pyversions/wiswa.svg?color=blue&logo=python&logoColor=white)](https://www.python.org/)
[![PyPI - Version](https://img.shields.io/pypi/v/wiswa)](https://pypi.org/project/wiswa/)
[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/wiswa)](https://github.com/Tatsh/wiswa/tags)
[![License](https://img.shields.io/github/license/Tatsh/wiswa)](https://github.com/Tatsh/wiswa/blob/master/LICENSE.txt)
[![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/wiswa/v0.3.4/master)](https://github.com/Tatsh/wiswa/compare/v0.3.4...master)
[![CodeQL](https://github.com/Tatsh/wiswa/actions/workflows/codeql.yml/badge.svg)](https://github.com/Tatsh/wiswa/actions/workflows/codeql.yml)
[![QA](https://github.com/Tatsh/wiswa/actions/workflows/qa.yml/badge.svg)](https://github.com/Tatsh/wiswa/actions/workflows/qa.yml)
[![Tests](https://github.com/Tatsh/wiswa/actions/workflows/tests.yml/badge.svg)](https://github.com/Tatsh/wiswa/actions/workflows/tests.yml)
[![Coverage Status](https://coveralls.io/repos/github/Tatsh/wiswa/badge.svg?branch=master)](https://coveralls.io/github/Tatsh/wiswa?branch=master)
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-blue?logo=dependabot)](https://github.com/dependabot)
[![Documentation Status](https://readthedocs.org/projects/wiswa/badge/?version=latest)](https://wiswa.readthedocs.org/?badge=latest)
[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![uv](https://img.shields.io/badge/uv-261230?logo=astral)](https://docs.astral.sh/uv/)
[![pytest](https://img.shields.io/badge/pytest-zz?logo=Pytest&labelColor=black&color=black)](https://docs.pytest.org/en/stable/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Downloads](https://static.pepy.tech/badge/wiswa/month)](https://pepy.tech/project/wiswa)
[![Stargazers](https://img.shields.io/github/stars/Tatsh/wiswa?logo=github&style=flat)](https://github.com/Tatsh/wiswa/stargazers)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Prettier](https://img.shields.io/badge/Prettier-black?logo=prettier)](https://prettier.io/)

[![@Tatsh](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpublic.api.bsky.app%2Fxrpc%2Fapp.bsky.actor.getProfile%2F%3Factor=did%3Aplc%3Auq42idtvuccnmtl57nsucz72&query=%24.followersCount&label=Follow+%40Tatsh&logo=bluesky&style=social)](https://bsky.app/profile/Tatsh.bsky.social)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Tatsh-black?logo=buymeacoffee)](https://buymeacoffee.com/Tatsh)
[![Libera.Chat](https://img.shields.io/badge/Libera.Chat-Tatsh-black?logo=liberadotchat)](irc://irc.libera.chat/Tatsh)
[![Mastodon Follow](https://img.shields.io/mastodon/follow/109370961877277568?domain=hostux.social&style=social)](https://hostux.social/@Tatsh)
[![Patreon](https://img.shields.io/badge/Patreon-Tatsh2-F96854?logo=patreon)](https://www.patreon.com/Tatsh2)

<!-- WISWA-GENERATED-README:STOP -->

A highly opinionated way to generate projects with Jsonnet.

## Installation

We recommend a **global** install so `wiswa` and `wiswa-mcp` are on your `PATH`
from any working directory:

```shell
uv tool install wiswa
```

Or with pipx:

```shell
pipx install wiswa
```

If you prefer not to install globally, add Wiswa as a **development dependency**
of your project—for example `uv add --group dev wiswa`, or list `wiswa` under
`dependency-groups.dev` in `pyproject.toml` and install inside the project
virtual environment with your usual workflow.

## Usage

![demo](demo.gif)

Add `-d` to show debug logs.

```shell
Usage: wiswa [OPTIONS] [FILE]

  Entry point for the Wiswa CLI.

Options:
  --cache-time INTEGER            Cache expiry time in seconds.  [default:
                                  600]
  -d, --debug                     Enable debug output.
  -J, --jpath TEXT                Add a directory to the Jsonnet search path
                                  (only used when evaluating settings).
  --no-cache                      Disable HTTP response caching.
  -o, --output-dir DIRECTORY      Output directory for generated files.
  -q, --quiet                     Suppress the progress spinner.
  --skip-jsonnet                  Skip project.jsonnet manifests; settings merge still runs.
  --skip-postprocess              Skip post-processing steps.
  --skip-remote                   Skip configuring the remote Git host (GitHub or GitLab).
  --skip-static                   Skip copying static files.
  --skip-templates                Skip Jinja2 template evaluation.
  --skip-yarn                     Skip Yarn download.
  -h, --help                      Show this message and exit.
```

## Remote API tokens (GitHub and GitLab)

When Wiswa configures the remote (`wiswa` without `--skip-remote`), it calls the GitHub or GitLab
API using a **personal access token**. Tokens are read from the environment when supported, or from
the system keyring. Service names include the **repository hostname** so different hosts (for
example GitHub.com, GitHub Enterprise, or self-managed GitLab) keep separate credentials.

Keyring entries use the usual **service name** and **username** fields (for example as shown by
`secret-tool` on Linux or Keychain Access on macOS). The **username** is normally your OS login
name (`whoami`).

### GitHub

1. Service `wiswa-github:<hostname>`, username your OS user. The hostname is taken from
   `repository_uri` (for example `github.com` for `https://github.com/org/repo`).

Example (hostname `github.com`, OS user `alice`):

```shell
python -m keyring set 'wiswa-github:github.com' alice
# paste the token at the prompt
```

### GitLab

1. **Environment:** `GITLAB_TOKEN` (if set, used first).
2. **Preferred:** service `wiswa-gitlab:<hostname>`, username your OS user (for example
   `wiswa-gitlab:gitlab.com`).
3. Same service with **username** equal to the hostname is also checked (for older or alternate
   storage patterns).

Example for `gitlab.com`:

```shell
export GITLAB_TOKEN='glpat-...'   # optional; overrides keyring

python -m keyring set 'wiswa-gitlab:gitlab.com' "$(whoami)"
```

## MCP Server

Wiswa includes an MCP server (`wiswa-mcp`) that exposes settings discovery tools for AI assistants.

### Claude Code

```shell
claude mcp add wiswa-mcp -- wiswa-mcp
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "wiswa-mcp": {
      "command": "wiswa-mcp"
    }
  }
}
```

### GitHub Copilot CLI

Add to `.github/copilot/mcp.json`:

```json
{
  "mcpServers": {
    "wiswa-mcp": {
      "command": "wiswa-mcp"
    }
  }
}
```
