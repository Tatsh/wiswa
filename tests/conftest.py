"""Configuration for Pytest."""
from __future__ import annotations

from pathlib import Path
from typing import NoReturn
import os

from click.testing import CliRunner
import pytest

import wiswa.vcs.github

if os.getenv('_PYTEST_RAISE', '0') != '0':  # pragma no cover

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call: pytest.CallInfo[None]) -> NoReturn:
        assert call.excinfo is not None
        raise call.excinfo.value

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo: pytest.ExceptionInfo[BaseException]) -> NoReturn:
        raise excinfo.value


@pytest.fixture(autouse=True)
def recover_stale_process_cwd(request: pytest.FixtureRequest) -> None:
    """
    Recover when the process cwd was removed mid-session.

    Gentoo Portage test phases often run pytest with aggressive temporary-directory retention.
    The process working directory can then point at a path that no longer exists, so
    ``Path.cwd()`` raises ``FileNotFoundError`` before ``monkeypatch.chdir`` can save the
    prior cwd.
    """
    try:
        Path.cwd()
    except FileNotFoundError:
        os.chdir(Path(request.config.rootpath))


@pytest.fixture(autouse=True)
def isolate_github_tag_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Isolate the GitHub tag cache from the user cache directory.

    Stubbed GitHub sessions return fixture tags and SHAs. Without this fixture,
    :py:mod:`wiswa.vcs.github` writes the stubbed tags and SHAs to the real disk cache, and later
    real Wiswa runs pin the stubbed values.
    """
    monkeypatch.setattr(wiswa.vcs.github, '_disk_cache_path',
                        lambda: tmp_path / 'github_tag_cache.json')
    monkeypatch.setattr(wiswa.vcs.github, '_disk_store_memo_box', [None])
    monkeypatch.setattr(wiswa.vcs.github, '_tag_cache', {})


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
