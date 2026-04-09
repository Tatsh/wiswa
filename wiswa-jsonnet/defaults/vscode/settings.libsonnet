/**
 * @file settings.libsonnet
 * @namespace vscode::settings
 * @brief Generate `settings.json` content for Visual Studio Code.
 */
{
  /**
   * @brief Generate Python-specific settings.
   * @param python_tab_size Tab size for Python files.
   * @param python_package_index_depth Depth for Python package indexing.
   * @param rst_tab_size Tab size for reStructuredText files.
   * @param want_tests Whether to add pytest settings.
   * @param want_yapf Whether to use YAPF as the default formatter for Python.
   * @returns An object representing Python-specific settings.
   * @pt int, int, int, bool, bool
   * @rv object
   */
  python_items(python_tab_size=4, python_package_index_depth=100, rst_tab_size=3, want_tests=true, want_yapf=true):: {
    '[python]': {
      'editor.defaultFormatter': if want_yapf then 'eeyore.yapf' else 'charliermarsh.ruff',
      'editor.formatOnSaveMode': 'file',
      'editor.tabSize': python_tab_size,
    },
    '[restructuredtext]': {
      'editor.defaultFormatter': 'lextudio.restructuredtext',
      'editor.formatOnSaveMode': 'file',
      'editor.tabSize': rst_tab_size,
    },
    'python.analysis.autoImportCompletions': true,
    'python.analysis.completeFunctionParens': true,
    'python.analysis.importFormat': 'relative',
    'python.analysis.indexing': true,
    'python.analysis.inlayHints.callArgumentNames': 'all',
    'python.analysis.inlayHints.functionReturnTypes': true,
    'python.analysis.inlayHints.pytestParameters': true,
    'python.analysis.inlayHints.variableTypes': true,
    'python.analysis.packageIndexDepths': [
      {
        depth: python_package_index_depth,
        name: '',
      },
    ],
    'python.languageServer': 'Pylance',
  } + (if want_tests then {
         'python.testing.pytestArgs': ['tests'],
         'python.testing.pytestEnabled': true,
       } else {}) + {
    'restructuredtext.experimental': true,
    'restructuredtext.linter.disabledLinters': ['rstcheck'],
    'restructuredtext.linter.doc8.extraArgs': [
      '--config',
      '${workspaceFolder}/pyproject.toml',
    ],
    'restructuredtext.linter.run': 'onSave',
  },
  /**
   * @brief Generate C/C++-specific settings.
   * @param c_cpp_tab_size Tab size for C/C++ files.
   * @returns An object representing C/C++-specific settings.
   * @pt int
   * @rv object
   */
  cpp_items(c_cpp_tab_size=4):: {
    '[c]': {
      'editor.defaultFormatter': 'ms-vscode.cpptools',
      'editor.tabSize': c_cpp_tab_size,
    },
    '[cpp]': {
      'editor.defaultFormatter': 'ms-vscode.cpptools',
      'editor.tabSize': c_cpp_tab_size,
    },
    'C_Cpp.default.configurationProvider': 'ms-vscode.cmake-tools',
  },
  /**
   * @brief Get the main settings for Visual Studio Code.
   * @param settings The project settings.
   * @returns An object representing the main settings for Visual Studio Code.
   * @pt object
   * @rv object
   */
  get(settings):: {
    '[jsonnet]': {
      'editor.defaultFormatter': 'Grafana.vscode-jsonnet',
    },
    '[shellscript]': {
      'editor.tabSize': settings.shell_tab_size,
      'editor.defaultFormatter': 'foxundermoon.shell-format',
    },
    'cSpell.enabled': true,
    'editor.codeActionsOnSave': { 'source.fixAll': 'always' },
    'editor.defaultFormatter': 'esbenp.prettier-vscode',
    'editor.formatOnPaste': true,
    'editor.formatOnSave': true,
    'editor.formatOnType': true,
    'editor.insertSpaces': true,
    'editor.rulers': [settings.line_width],
    'editor.tabSize': settings.tab_size,
    'editor.wordWrapColumn': settings.line_width,
    'files.associations': {
      '*.json.dist': 'json',
    },
    'files.insertFinalNewline': true,
    'files.trimFinalNewlines': true,
    'files.trimTrailingWhitespace': true,
    'files.eol': '\n',
    'shellformat.flag': 'i 2 -ci -sr',
    'sortJSON.excludedFiles': [],
    'sortJSON.excludedPaths': [],
  } + (
    if settings.project_type == 'c' || settings.project_type == 'c++' then
      self.cpp_items(settings.c_cpp_tab_size) else {}
  ) + (
    if settings.project_type == 'python' then
      self.python_items(
        settings.python_tab_size,
        settings.python_package_index_depth,
        settings.rst_tab_size,
        settings.want_tests,
        settings.want_yapf
      ) else {}
  ) + (
    if settings.using_gitlab then { 'yaml.customTags': ['!reference sequence'] } else {}
  ) + { 'yaml.format.printWidth': settings.line_width },
}
