Clang static analysis
=====================

Set ``want_scan_build: true`` in ``.wiswa.jsonnet`` to generate a workflow that
runs scan-build on every branch push and pull request. Configure native build
dependencies and commands under ``github.workflows.scan_build``. CMake is the
default build system; Meson, Make, and iOS builds need explicit commands.
Swift, Python, and JavaScript source are outside Clang static analysis coverage.
Python projects with native extensions can enable analysis for their native build.

.. code-block:: jsonnet

   {
     want_scan_build: true,
     github+: { workflows+: { scan_build+: {
       configure_command: 'cmake -S . -B build-scan -DCMAKE_BUILD_TYPE=Debug',
       build_command: 'cmake --build build-scan --clean-first --parallel 2',
       setup_steps: [{ run: 'sudo apt-get update && sudo apt-get install -y libssl-dev' }],
     } } },
   }

The workflow intercepts configuration and compilation. HTML reports, plist
results, and build logs are uploaded as CI artifacts. A successful analysis
must produce at least one plist result without analyser failures. Findings do
not fail CI; failed builds and incomplete analysis do. Empty analyses never
produce a successful report.

Pushes replace the report at ``<project Pages URL>/scan-build/``. The URL opens
the Clang HTML report directly. Successful analyses without findings display
``No bugs reported by the enabled Clang checkers.`` Pull requests upload artifacts
without publishing or requesting write permissions. GitHub does not trigger an individual
workflow for each intermediate commit when several commits are pushed together.

Enable GitHub Actions as the repository's Pages publishing source. Existing
documentation workflows must share the generated deployment. Set
``workflow_file: 'pages.yml'``, transfer documentation build steps into
``documentation_steps``, and set ``documentation_path`` to their output directory.
Documentation builds run on the default branch. Other branches retain the
previously published documentation. Projects using Jekyll can use a pinned
``actions/jekyll-build-pages`` step with ``destination: 'build/html'``.

Publication replaces the report in the ``scan-build-pages`` site branch, merges
documentation, and deploys the assembled site through GitHub Pages. Site branch
pushes do not trigger analysis. Publishing jobs request ``contents: write``,
``pages: write``, and ``id-token: write``; build jobs request ``contents: read``.
Publication uses a shared concurrency queue to prevent conflicting site
updates. GitHub permits up to 100 pending jobs in a concurrency group with
``queue: max``. Only the latest successful report is published. Previous reports
remain in Git history. CI artifacts expire according to repository retention settings.

``scope`` describes the analysed sources in the build log. Cross-compiled
projects can analyse host tools with a separate native build and record that
scope. A report for host tools does not cover the cross-compiled target.
