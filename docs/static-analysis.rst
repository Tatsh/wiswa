Static analysis scope
=====================

Set ``static_analysis_paths`` to the first-party source and test paths for the
project, such as ``['src', 'tests']``, ``['Project']``, or ``['native', 'tests']``.
Paths are relative to the repository root. Files under ``.vcpkg`` or ``3rdparty``
are excluded, including nested ``.vcpkg`` and ``3rdparty`` directories.

When ``want_codeql`` is set and the CodeQL languages include ``c-cpp``, Wiswa
generates ``.github/scripts/static-analysis.py`` from the configured paths. The
CodeQL workflow runs the helper between analysis and upload to drop native
findings outside the project paths. Manual C/C++ database extraction still
includes dependency context. Findings without source locations are preserved.
Custom native workflows must run the helper with ``--sarif FILE_OR_DIRECTORY``
between analysis and upload. Actions and other language analyses retain their scope.

.. code-block:: jsonnet

   {
     want_codeql: true,
     static_analysis_paths: ['src', 'tests'],
   }

Earlier releases also generated a Clang scan-build workflow and a Pages workflow
that published its reports. Regeneration deletes ``.github/workflows/scan-build.yml``
and the scan-build Pages workflow, and logs a warning while ``want_scan_build`` or
``github.workflows.scan_build`` remains in ``.wiswa.jsonnet``.
