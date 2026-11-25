"""Tests for project-specific native analysis scope."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
import json
import os
import subprocess as sp
import sys

import _jsonnet  # ruff:ignore[import-private-name]
import pytest

_LIBRARY = Path(__file__).resolve().parent.parent / 'wiswa/jsonnet'


def _workflows(paths: tuple[str, ...], languages: tuple[str, ...], *,
               want_codeql: bool) -> dict[str, str]:
    """
    Render the managed workflows.

    Parameters
    ----------
    paths : tuple[str, ...]
        Project source paths.
    languages : tuple[str, ...]
        CodeQL languages.
    want_codeql : bool
        Whether the CodeQL workflow is generated.

    Returns
    -------
    dict[str, str]
    """
    return cast(
        'dict[str, str]',
        json.loads(
            _jsonnet.evaluate_snippet(
                'analysis-scope',
                f"""
      local settings = (import 'defaults.libsonnet') + {{
        project_type: 'other', private: true,
        want_clang_format: false, want_codeql: {json.dumps(want_codeql)},
        want_tests: false, want_gitlab_mirror: false,
        static_analysis_paths: {json.dumps(paths)},
        github+: {{ codeql+: {{ languages: {json.dumps(languages)} }} }},
      }};
      (import 'github.libsonnet').workflows(settings)
    """,
                jpathdir=[str(_LIBRARY)],
                native_callbacks={'githubLatestActionSha': (('o', 'r'), lambda _o, _r: 'a' * 40)})))


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
    outputs = _workflows(paths, ('c-cpp', 'actions'), want_codeql=True)
    path = tmp_path / 'static-analysis.py'
    path.write_text(outputs['.github/scripts/static-analysis.py'], encoding='utf-8')
    return path


@pytest.mark.parametrize(('paths', 'languages', 'want_codeql'), [
    (('src',), ('c-cpp', 'actions'), False),
    (('src',), ('actions',), True),
    ((), ('c-cpp', 'actions'), True),
])
def test_helper_requires_native_codeql_and_paths(paths: tuple[str, ...], languages: tuple[str, ...],
                                                 *, want_codeql: bool) -> None:
    outputs = _workflows(paths, languages, want_codeql=want_codeql)
    assert '.github/scripts/static-analysis.py' not in outputs


@pytest.mark.parametrize('language', ['c-cpp', 'cpp'])
def test_helper_generated_for_native_codeql(language: str) -> None:
    outputs = _workflows(('src',), (language, 'actions'), want_codeql=True)
    assert "_PATHS: tuple[str, ...] = ('src',)" in outputs['.github/scripts/static-analysis.py']


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


@pytest.mark.parametrize('arguments', [['--exclude'], ['@arguments.rsp'], []])
def test_only_sarif_filtering_is_supported(tmp_path: Path, arguments: list[str]) -> None:
    script = _script(tmp_path)
    with pytest.raises(sp.CalledProcessError) as error:
        sp.run([sys.executable, str(script), *arguments],
               cwd=tmp_path,
               check=True,
               capture_output=True,
               text=True)
    assert 'Usage: static-analysis.py --sarif FILE_OR_DIRECTORY' in error.value.stderr
