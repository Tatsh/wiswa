"""Tests for static analysis publication."""

from __future__ import annotations

from pathlib import Path
from shutil import which
from typing import Any, cast
import json
import os
import subprocess as sp

import _jsonnet  # ruff:ignore[import-private-name]
import pytest

_LIBRARY = Path(__file__).resolve().parent.parent / 'wiswa/jsonnet'
_BASH = which('bash') or '/bin/bash'
_GIT = which('git') or '/usr/bin/git'


def _workflow(*, documentation: bool = False, runs_on: str = 'ubuntu-latest') -> dict[str, Any]:
    """
    Render the analysis workflow.

    Parameters
    ----------
    documentation : bool
        Include a documentation build.
    runs_on : str
        Runner image for analysis.

    Returns
    -------
    dict[str, Any]
    """
    documentation_steps = '[{run: "cmake --build build --target docs"}]' if documentation else '[]'
    return cast(
        'dict[str, Any]',
        json.loads(
            _jsonnet.evaluate_snippet(
                'scan-build-test',
                f"""
        local settings = (import 'defaults.libsonnet') + {{
          project_name: 'example',
          github+: {{ workflows+: {{ scan_build+: {{
            runs_on: {json.dumps(runs_on)},
            checkout_options: {{ 'fetch-depth': 0, submodules: 'recursive' }},
            documentation_steps: {documentation_steps},
          }} }} }},
        }};
        (import 'github/workflows/scan-build.libsonnet')(settings)
        """,
                jpathdir=[str(_LIBRARY)],
                native_callbacks={'githubLatestActionSha': (('o', 'r'), lambda _o, _r: 'a' * 40)})))


@pytest.mark.parametrize('runs_on', ['ubuntu-latest', 'macos-15'])
def test_workflow_uses_platform_compiler_and_analyzer(runs_on: str) -> None:
    workflow = _workflow(runs_on=runs_on)
    commands = [
        step['run'] for step in workflow['jobs']['analyze']['steps']
        if 'scan-build ' in step.get('run', '')
    ]
    compiler = '"$(xcrun --find clang)"' if runs_on.startswith('macos') else 'clang'
    assert len(commands) == 2
    assert all(f'--use-cc={compiler} ' in command for command in commands)
    if runs_on.startswith('macos'):
        assert all(f'--use-analyzer={compiler} ' in command for command in commands)
    else:
        assert all('--use-analyzer=' not in command for command in commands)


@pytest.mark.parametrize('fail', [False, True])
def test_compiler_variables_and_errors_inside_scan_build(tmp_path: Path, *, fail: bool) -> None:
    steps = _workflow()['jobs']['analyze']['steps']
    compiler_wrapper = """scan-build() {
      while [ "$1" != bash ]; do shift; done
      CC=intercepted-c CXX=intercepted-cxx "$@"
    }
    """
    for step in (steps[2], steps[3]):
        variable, command = next(iter(step['env'].items()))
        assert command.startswith('cmake ')
        env = os.environ | {
            'CC': 'outside-c',
            'CXX': 'outside-cxx',
            'RUNNER_TEMP': str(tmp_path),
            variable: ('false\ntrue' if fail else 'printf "%s:%s" "$CC" "$CXX" > compiler.txt')
        }
        if fail:
            with pytest.raises(sp.CalledProcessError):
                sp.run([_BASH, '-eo', 'pipefail', '-c', compiler_wrapper + step['run']],
                       cwd=tmp_path,
                       env=env,
                       check=True,
                       capture_output=True,
                       text=True)
        else:
            sp.run([_BASH, '-eo', 'pipefail', '-c', compiler_wrapper + step['run']],
                   cwd=tmp_path,
                   env=env,
                   check=True,
                   capture_output=True,
                   text=True)
            assert (tmp_path / 'compiler.txt').read_text(encoding='utf-8') == \
                'intercepted-c:intercepted-cxx'


def test_workflow_publication_permissions_and_triggers() -> None:
    workflow = _workflow(documentation=True)
    assert workflow['on']['push'] == {'branches-ignore': ['scan-build-pages']}
    assert workflow['on']['pull_request'] == {}
    assert workflow['permissions'] == {}
    assert workflow['jobs']['analyze']['permissions'] == {'contents': 'read'}
    assert workflow['jobs']['analyze']['steps'][0]['with'] == {
        'fetch-depth': 0,
        'persist-credentials': False,
        'submodules': 'recursive'
    }
    assert workflow['jobs']['documentation']['permissions'] == {'contents': 'read'}
    publish = workflow['jobs']['publish']
    assert "github.event_name != 'pull_request'" in publish['if']
    assert "needs.analyze.result == 'success'" in publish['if']
    assert publish['concurrency'] == {'cancel-in-progress': False, 'group': 'pages', 'queue': 'max'}
    assert publish['needs'] == ['analyze', 'documentation']
    assert publish['permissions'] == {'contents': 'write', 'id-token': 'write', 'pages': 'write'}


@pytest.mark.parametrize(('enabled', 'filename'), [(False, 'scan-build.yml'),
                                                   (True, 'scan-build.yml'), (True, 'pages.yml')])
def test_workflow_generator_opt_in(*, enabled: bool, filename: str) -> None:
    files = json.loads(
        _jsonnet.evaluate_snippet('scan-build-selection',
                                  f"""
        local settings = (import 'defaults.libsonnet') + {{
          project_type: 'other',
          want_scan_build: {json.dumps(enabled)},
          want_clang_format: false,
          want_codeql: false,
          want_tests: false,
          want_gitlab_mirror: false,
          private: false,
          github+: {{ workflows+: {{ scan_build+: {{ workflow_file: {json.dumps(filename)} }} }} }},
        }};
        std.objectFields((import 'github.libsonnet').workflows(settings))
        """,
                                  jpathdir=[str(_LIBRARY)]))
    assert (f'.github/workflows/{filename}' in files) is enabled


@pytest.mark.parametrize(('units', 'failures', 'outcome', 'reports', 'complete'), [
    (1, False, 'success', 0, True),
    (1, False, 'success', 1, True),
    (1, False, 'success', 2, False),
    (0, False, 'success', 0, False),
    (1, True, 'success', 1, False),
    (1, False, 'failure', 1, False),
])
def test_report_requires_completed_analysis(tmp_path: Path, *, units: int, failures: bool,
                                            outcome: str, reports: int, complete: bool) -> None:
    steps = _workflow()['jobs']['analyze']['steps']
    script = next(s['run'] for s in steps if s.get('name', '').startswith('Prepare report'))
    report = tmp_path / 'scan-build-report/results/run'
    report.mkdir(parents=True)
    for index in range(units):
        (report / f'report-{index}.plist').write_text('test fixture', encoding='utf-8')
    for index in range(reports):
        directory = report if index == 0 else report.parent / str(index)
        directory.mkdir(exist_ok=True)
        (directory / 'index.html').write_text('<a href="report.html">Clang report</a>',
                                              encoding='utf-8')
        (directory / 'report.html').write_text('Clang finding', encoding='utf-8')
    if failures:
        (report / 'failures').mkdir()
        (report / 'failures/crash.txt').write_text('analyzer failure', encoding='utf-8')
    result = sp.run([_BASH, '-e', '-o', 'pipefail', '-c', script],
                    check=False,
                    cwd=tmp_path,
                    capture_output=True,
                    text=True,
                    env=os.environ | {
                        'ANALYSIS_OUTCOME': outcome,
                        'ANALYSIS_SCOPE': 'Native test sources.',
                        'GITHUB_SHA': 'a' * 40
                    })
    assert (result.returncode == 0) is complete
    report_index = tmp_path / 'scan-build-report/index.html'
    assert report_index.exists() is complete
    if complete:
        page = report_index.read_text(encoding='utf-8')
        assert 'Analysis completed' not in page
        assert ('No bugs reported' in page) is (reports == 0)
        assert (report_index.parent / 'report-0.plist').exists()
        assert not (tmp_path / 'scan-build-report/results').exists()
        if reports:
            assert page == '<a href="report.html">Clang report</a>'
            assert (report_index.parent /
                    'report.html').read_text(encoding='utf-8') == 'Clang finding'


def test_site_replaces_previous_reports_and_preserves_documentation(tmp_path: Path) -> None:
    steps = _workflow()['jobs']['publish']['steps']
    script = next(s['run'] for s in steps if s.get('name', '').startswith('Assemble site'))
    docs = tmp_path / '_documentation'
    docs.mkdir()
    (docs / 'index.html').write_text('API documentation', encoding='utf-8')
    report = tmp_path / '_report'
    report.mkdir()
    (report / 'index.html').write_text('Clang report', encoding='utf-8')
    site = tmp_path / '_site'
    site.mkdir()
    legacy = site / 'scan-build' / ('c' * 40)
    legacy.mkdir(parents=True)
    (legacy / 'index.html').write_text('Previous report', encoding='utf-8')
    for sha in ('a' * 40, 'b' * 40):
        (report / 'index.html').write_text(sha, encoding='utf-8')
        sp.run([_BASH, '-e', '-o', 'pipefail', '-c', script],
               check=True,
               cwd=tmp_path,
               capture_output=True,
               text=True,
               env=os.environ | {'GITHUB_SHA': sha})
    assert (site / 'index.html').read_text(encoding='utf-8') == 'API documentation'
    assert (site / 'scan-build/index.html').read_text(encoding='utf-8') == 'b' * 40
    assert sorted(p.name for p in (site / 'scan-build').iterdir()) == ['index.html']


def test_archive_round_trip_without_persisted_credentials(tmp_path: Path) -> None:
    remote = tmp_path / 'remote.git'
    sp.run([_GIT, 'init', '--bare', str(remote)], check=True, capture_output=True)
    gitconfig = tmp_path / 'gitconfig'
    gitconfig.write_text(
        f'[url "{remote.as_uri()}"]\n\tinsteadOf = https://github.com/example/reports.git\n',
        encoding='utf-8')
    steps = _workflow()['jobs']['publish']['steps']
    scripts = [
        s['run'] for s in steps
        if s.get('name', '') in {'Restore site', 'Assemble site with latest report', 'Save site'}
    ]
    for index, sha in enumerate(('a' * 40, 'b' * 40, 'b' * 40)):
        run = tmp_path / str(index)
        run.mkdir()
        report = run / '_report'
        report.mkdir()
        (report / 'index.html').write_text(sha, encoding='utf-8')
        if index == 0:
            docs = run / '_documentation'
            docs.mkdir()
            (docs / 'index.html').write_text('API documentation', encoding='utf-8')
        env = os.environ | {
            'GH_TOKEN': 'test-fixture',
            'GITHUB_REPOSITORY': 'example/reports',
            'GITHUB_SHA': sha,
            'GIT_CONFIG_GLOBAL': str(gitconfig),
            'RUNNER_TEMP': str(run)
        }
        for script in scripts:
            sp.run([_BASH, '-e', '-o', 'pipefail', '-c', script],
                   check=True,
                   cwd=run,
                   capture_output=True,
                   text=True,
                   env=env)
        assert (run / '_site/index.html').read_text(encoding='utf-8') == 'API documentation'
        assert 'extraheader' not in (run / '_site/.git/config').read_text(encoding='utf-8')
    result = sp.run(
        [_GIT, '--git-dir',
         str(remote), 'ls-tree', '--name-only', 'scan-build-pages:scan-build'],
        check=True,
        capture_output=True,
        text=True)
    assert result.stdout.strip() == 'index.html'
    result = sp.run(
        [_GIT, '--git-dir',
         str(remote), 'show', 'scan-build-pages:scan-build/index.html'],
        check=True,
        capture_output=True,
        text=True)
    assert result.stdout == 'b' * 40
    result = sp.run([_GIT, '--git-dir',
                     str(remote), 'rev-list', '--count', 'scan-build-pages'],
                    check=True,
                    capture_output=True,
                    text=True)
    assert result.stdout.strip() == '2'
