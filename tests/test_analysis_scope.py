"""Tests for project-specific native analysis scope."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import re
import shlex
import subprocess as sp
import sys

import _jsonnet  # ruff:ignore[import-private-name]
import pytest

_LIBRARY = Path(__file__).resolve().parent.parent / 'wiswa/jsonnet'


def _script(tmp_path: Path, *, paths: tuple[str,
                                            ...] = ('src', 'tests', 'Project', 'main.c')) -> Path:
    """
    Render the managed analysis helper.

    Parameters
    ----------
    tmp_path : Path
        Isolated project root.
    paths : tuple[str, ...]
        Project source paths.

    Returns
    -------
    Path
    """
    outputs = json.loads(
        _jsonnet.evaluate_snippet(
            'analysis-scope',
            f"""
      local settings = (import 'defaults.libsonnet') + {{
        project_type: 'other', private: true,
        want_clang_format: false, want_codeql: false, want_scan_build: false,
        want_tests: false, want_gitlab_mirror: false,
        static_analysis_paths: {json.dumps(paths)},
      }};
      (import 'github.libsonnet').workflows(settings)
    """,
            jpathdir=[str(_LIBRARY)],
            native_callbacks={'githubLatestActionSha': (('o', 'r'), lambda _o, _r: 'a' * 40)}))
    path = tmp_path / 'static-analysis.py'
    path.write_text(outputs['.github/scripts/static-analysis.py'], encoding='utf-8')
    return path


@pytest.mark.parametrize(('source', 'expected'), [
    ('src/main.cpp', 'analyze'),
    ('tests/test.c', 'analyze'),
    ('Project/game.m', 'analyze'),
    ('main.c', 'analyze'),
    ('other.c', 'compile'),
    ('.vcpkg/buildtrees/lib/lib.c', 'compile'),
    ('3rdparty/library.c', 'compile'),
    ('src/3rdparty/library.c', 'compile'),
    ('build/probe.c', 'compile'),
    ('src-other/main.c', 'compile'),
])
@pytest.mark.parametrize('response_file', [False, True])
def test_compiler_only_analyzes_project_sources(tmp_path: Path, source: str, expected: str, *,
                                                response_file: bool) -> None:
    script = _script(tmp_path)
    wrapper = tmp_path / 'scan-build-cc'
    script.rename(wrapper)
    for name, output in (('analyzer', 'analyze'), ('compiler', 'compile')):
        tool = tmp_path / name
        tool.write_text(f'#!/bin/sh\nprintf "{output}"\n', encoding='utf-8')
        tool.chmod(0o755)
    args = ['-c', str(tmp_path / source)]
    if response_file:
        (tmp_path / 'arguments.rsp').write_text(' '.join(args), encoding='utf-8')
        args = ['@arguments.rsp']
    result = sp.run(
        [sys.executable, str(wrapper), *args],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ | {
            'GITHUB_WORKSPACE': str(tmp_path),
            'STATIC_ANALYSIS_CC': str(tmp_path / 'analyzer'),
            'STATIC_ANALYSIS_REAL_CC': str(tmp_path / 'compiler'),
        })
    assert result.stdout == expected


def test_sarif_preserves_project_and_unlocated_findings(tmp_path: Path) -> None:
    script = _script(tmp_path)
    results: list[dict[str, Any]] = [{'message': {'text': 'unknown location'}}]
    results.extend({'locations': [{
        'physicalLocation': {
            'artifactLocation': {
                'uri': path
            }
        }
    }]} for path in ('src/main.cpp', 'tests/test.c', '3rdparty/lib.c', '.vcpkg/lib.c',
                     'src/3rdparty/nested.c', 'src-other/main.c'))
    sarif = tmp_path / 'results.sarif'
    sarif.write_text(json.dumps({'runs': [{'results': results}]}), encoding='utf-8')
    sp.run(
        [sys.executable, str(script), '--sarif', str(sarif)],
        cwd=tmp_path,
        env=os.environ | {'GITHUB_WORKSPACE': str(tmp_path)},
        check=True,
        capture_output=True)
    assert json.loads(sarif.read_text(encoding='utf-8'))['runs'][0]['results'] == results[:3]


@pytest.mark.parametrize('language', ['cc', 'cxx'])
def test_nested_response_files_preserve_arguments_and_select_language(tmp_path: Path,
                                                                      language: str) -> None:
    script = _script(tmp_path, paths=('src/../source',))
    wrapper = tmp_path / f'scan-build-{language}'
    script.rename(wrapper)
    for name in ('cc', 'cxx', 'compiler'):
        tool = tmp_path / name
        tool.write_text(f'#!/bin/sh\nprintf "{name}\\n"\nprintf "%s\\n" "$@"\n', encoding='utf-8')
        tool.chmod(0o755)
    (tmp_path / 'inner.rsp').write_text(shlex.join(['-c', 'source/main file.cpp']),
                                        encoding='utf-8')
    (tmp_path / 'outer.rsp').write_text('@inner.rsp', encoding='utf-8')
    result = sp.run(
        [sys.executable, str(wrapper), '@outer.rsp'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ | {
            'GITHUB_WORKSPACE': str(tmp_path),
            'STATIC_ANALYSIS_CC': str(tmp_path / 'cc'),
            'STATIC_ANALYSIS_CXX': str(tmp_path / 'cxx'),
            'STATIC_ANALYSIS_REAL_CC': str(tmp_path / 'compiler'),
            'STATIC_ANALYSIS_REAL_CXX': str(tmp_path / 'compiler'),
        })
    assert result.stdout.splitlines() == [language, '@outer.rsp']


def test_recursive_response_files_fail_before_compilation(tmp_path: Path) -> None:
    script = _script(tmp_path)
    wrapper = tmp_path / 'scan-build-cc'
    script.rename(wrapper)
    (tmp_path / 'outer.rsp').write_text('@inner.rsp', encoding='utf-8')
    (tmp_path / 'inner.rsp').write_text('@outer.rsp', encoding='utf-8')
    with pytest.raises(sp.CalledProcessError) as error:
        sp.run([sys.executable, str(wrapper), '@outer.rsp'],
               cwd=tmp_path,
               check=True,
               capture_output=True,
               text=True)
    assert 'Recursive compiler response file.' in error.value.stderr


def test_sarif_resolves_artifact_indexes_chained_bases_and_encoded_paths(tmp_path: Path) -> None:
    script = _script(tmp_path, paths=('src/project',))
    artifacts = [
        {
            'location': {
                'uri': 'main%20file.cpp',
                'uriBaseId': 'PROJECT'
            }
        },
        {
            'location': {
                'uri': (tmp_path / '3rdparty/library.c').as_uri()
            }
        },
    ]
    results = [
        {
            'locations': [{
                'physicalLocation': {
                    'artifactLocation': {
                        'index': 0
                    }
                }
            }]
        },
        {
            'locations': [{
                'physicalLocation': {
                    'artifactLocation': {
                        'uri': (tmp_path / 'src/project/main file.cpp').as_uri(),
                    }
                }
            }]
        },
        {
            'locations': [{
                'physicalLocation': {
                    'artifactLocation': {
                        'index': 1
                    }
                }
            }]
        },
    ]
    sarif = tmp_path / 'results.sarif'
    sarif.write_text(json.dumps({
        'runs': [{
            'artifacts': artifacts,
            'originalUriBaseIds': {
                'ROOT': {
                    'uri': (tmp_path / 'src').as_uri() + '/'
                },
                'PROJECT': {
                    'uri': 'project/',
                    'uriBaseId': 'ROOT'
                },
            },
            'results': results,
        }]
    }),
                     encoding='utf-8')
    sp.run(
        [sys.executable, str(script), '--sarif', str(sarif)],
        cwd=tmp_path,
        env=os.environ | {'GITHUB_WORKSPACE': str(tmp_path)},
        check=True,
        capture_output=True)
    assert json.loads(sarif.read_text(encoding='utf-8'))['runs'][0]['results'] == results[:2]


@pytest.mark.parametrize(('case', 'message'), [
    ('empty', 'CodeQL produced no SARIF files.'),
    ('cycle', 'Recursive SARIF URI base.'),
])
def test_invalid_sarif_inputs_fail(tmp_path: Path, case: str, message: str) -> None:
    script = _script(tmp_path)
    sarif = tmp_path / 'results'
    sarif.mkdir()
    if case == 'cycle':
        (sarif / 'results.sarif').write_text(json.dumps({
            'runs': [{
                'originalUriBaseIds': {
                    'A': {
                        'uri': 'src/',
                        'uriBaseId': 'B'
                    },
                    'B': {
                        'uri': './',
                        'uriBaseId': 'A'
                    },
                },
                'results': [{
                    'locations': [{
                        'physicalLocation': {
                            'artifactLocation': {
                                'uri': 'main.c',
                                'uriBaseId': 'A',
                            }
                        }
                    }]
                }],
            }]
        }),
                                             encoding='utf-8')
    with pytest.raises(sp.CalledProcessError) as error:
        sp.run([sys.executable, str(script), '--sarif',
                str(sarif)],
               cwd=tmp_path,
               env=os.environ | {'GITHUB_WORKSPACE': str(tmp_path)},
               check=True,
               capture_output=True,
               text=True)
    assert message in error.value.stderr


def test_exclusion_pattern_matches_only_outside_project_scope(tmp_path: Path) -> None:
    script = _script(tmp_path)
    (tmp_path / 'main.c').write_text('int main(void) { return 0; }\n', encoding='utf-8')
    result = sp.run([sys.executable, str(script), '--exclude'],
                    cwd=tmp_path,
                    env=os.environ | {'GITHUB_WORKSPACE': str(tmp_path)},
                    check=True,
                    capture_output=True,
                    text=True)
    pattern = re.compile(result.stdout.strip())
    assert not pattern.search(str(tmp_path / 'src'))
    assert not pattern.search(str(tmp_path))
    assert not pattern.search(str(tmp_path / 'tests/subdir'))
    assert pattern.search(str(tmp_path / '.vcpkg'))
    assert pattern.search(str(tmp_path / 'src/3rdparty'))
    assert pattern.search(str(tmp_path / 'src-other'))
