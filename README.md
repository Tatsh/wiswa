# wiswa

[![Python versions](https://img.shields.io/pypi/pyversions/wiswa.svg?color=blue&logo=python&logoColor=white)](https://www.python.org/)
[![PyPI - Version](https://img.shields.io/pypi/v/wiswa)](https://pypi.org/project/wiswa/)
[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/wiswa)](https://github.com/Tatsh/wiswa/tags)
[![License](https://img.shields.io/github/license/Tatsh/wiswa)](https://github.com/Tatsh/wiswa/blob/master/LICENSE.txt)
[![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/wiswa/v0.0.0/master)](https://github.com/Tatsh/wiswa/compare/v0.0.0...master)
[![CodeQL](https://github.com/Tatsh/wiswa/actions/workflows/codeql.yml/badge.svg)](https://github.com/Tatsh/wiswa/actions/workflows/codeql.yml)
[![QA](https://github.com/Tatsh/wiswa/actions/workflows/qa.yml/badge.svg)](https://github.com/Tatsh/wiswa/actions/workflows/qa.yml)
[![Tests](https://github.com/Tatsh/wiswa/actions/workflows/tests.yml/badge.svg)](https://github.com/Tatsh/wiswa/actions/workflows/tests.yml)
[![Coverage Status](https://coveralls.io/repos/github/Tatsh/wiswa/badge.svg?branch=master)](https://coveralls.io/github/Tatsh/wiswa?branch=master)
[![Documentation Status](https://readthedocs.org/projects/wiswa/badge/?version=latest)](https://wiswa.readthedocs.org/?badge=latest)
[![mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![pydocstyle](https://img.shields.io/badge/pydocstyle-enabled-AD4CD3)](https://www.pydocstyle.org/en/stable/)
[![pytest](https://img.shields.io/badge/pytest-zz?logo=Pytest&labelColor=black&color=black)](https://docs.pytest.org/en/stable/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Downloads](https://static.pepy.tech/badge/wiswa/month)](https://pepy.tech/project/wiswa)
[![Stargazers](https://img.shields.io/github/stars/Tatsh/wiswa?logo=github&style=flat)](https://github.com/Tatsh/wiswa/stargazers)

[![@Tatsh](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fpublic.api.bsky.app%2Fxrpc%2Fapp.bsky.actor.getProfile%2F%3Factor=did%3Aplc%3Auq42idtvuccnmtl57nsucz72&query=%24.followersCount&style=social&logo=bluesky&label=Follow+%40Tatsh)](https://bsky.app/profile/Tatsh.bsky.social)
[![Mastodon Follow](https://img.shields.io/mastodon/follow/109370961877277568?domain=hostux.social&style=social)](https://hostux.social/@Tatsh)

Generate a Python project.

## Installation

### Poetry

```shell
poetry add wiswa
```

### Pip

```shell
pip install wiswa
```

## Usage

Add `-d` to show debug logs.

```shell
Usage: wiswa [OPTIONS] [FILE]

  Entry point for the Wiswa CLI.

Options:
  -d, --debug          Enable debug output.
  -J, --jpath TEXT     Add a directory to the Jsonnet search path (only used
                       when evaluating settings).
  -u, --user-defaults  Use defaults.jsonnet file in user preferences
                       directory.
  --skip-github        Skip configuring GitHub project.
  --skip-jsonnet       Skip Jsonnet evaluation.
  --skip-templates     Skip Jinja2 template evaluation.
  -h, --help           Show this message and exit.
```
