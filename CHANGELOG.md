<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Parallelised independent async operations across the generation pipeline for faster project
  creation and updates:
  - `wiswa/main.py`: Yarn download and plugin fetch now run concurrently; static file copying and
    `py.typed` creation also run in parallel.
  - `wiswa/utils/templating.py`: Common, agent/skill, and Python-specific template writes now
    execute concurrently via `asyncio.gather`.
  - `wiswa/utils/github.py`: Removed duplicate API calls; security PUT requests and ruleset upsert
    operations now run in parallel.
  - `wiswa/utils/postprocess.py`: File cleanup operations and configuration file writes now run
    concurrently.

## [0.0.1] - 2026-03-24

First version.

[unreleased]: https://github.com/Tatsh/wiswa/-/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/Tatsh/bascom/releases/tag/v0.0.1
