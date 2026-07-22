"""Tests for the :py:mod:`wiswa.tool.progress` module."""

from __future__ import annotations

from typing import TYPE_CHECKING
import io

from rich.console import Console
from wiswa.tool.progress import ProgressDisplay, TaskId

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _make_display(enabled: bool = True) -> tuple[ProgressDisplay, io.StringIO]:
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=80, legacy_windows=False)
    return ProgressDisplay(enabled=enabled, console=console), buf


def test_progress_display_disabled_is_noop() -> None:
    display, buf = _make_display(enabled=False)
    display.start()
    display.start_task(TaskId.EVALUATE_SETTINGS)
    display.update_message('hello')
    display.complete(TaskId.EVALUATE_SETTINGS)
    display.skip(TaskId.EVALUATE_PROJECT)
    display.skip_many([TaskId.WRITE_TEMPLATES, TaskId.DOWNLOAD_YARN])
    display.stop()
    assert not buf.getvalue()


def test_progress_display_renders_banner_checklist_and_spinner_message() -> None:
    display, buf = _make_display()
    display.start()
    display.start_task(TaskId.EVALUATE_SETTINGS, 'Evaluating settings...')
    display.complete(TaskId.EVALUATE_SETTINGS)
    display.skip(TaskId.EVALUATE_PROJECT)
    display.start_task(TaskId.WRITE_TEMPLATES, 'Writing templated files...')
    display.update_message('still writing')
    display.complete(TaskId.WRITE_TEMPLATES)
    display.stop()
    out = buf.getvalue()
    assert 'Evaluate settings' in out
    assert 'Evaluate project' in out
    assert 'Write templated files' in out
    assert '☑' in out
    assert '☒' in out
    assert 'still writing' in out


def test_progress_display_context_manager(mocker: MockerFixture) -> None:
    display, _ = _make_display()
    start = mocker.patch.object(display, 'start')
    stop = mocker.patch.object(display, 'stop')
    with display as entered:
        assert entered is display
    start.assert_called_once()
    stop.assert_called_once()


def test_progress_display_skip_many_renders_strike_through() -> None:
    display, buf = _make_display()
    display.start()
    display.skip_many([TaskId.DOWNLOAD_YARN, TaskId.COPY_STATIC])
    display.stop()
    out = buf.getvalue()
    assert 'Download Yarn' in out
    assert 'Copy static files' in out
    assert out.count('☒') >= 2


def test_progress_display_start_stop_idempotent() -> None:
    display, _ = _make_display()
    display.start()
    display.start()
    display.stop()
    display.stop()


def test_progress_display_running_task_shown_as_cyan() -> None:
    display, buf = _make_display()
    display.start()
    display.start_task(TaskId.EVALUATE_SETTINGS, 'Evaluating settings...')
    display.stop()
    out = buf.getvalue()
    assert 'Evaluating settings...' in out
    assert 'Evaluate settings' in out


def test_progress_display_defaults_to_stderr_console() -> None:
    display = ProgressDisplay(enabled=False)
    assert display.console is not None


def test_progress_display_skip_running_task_clears_spinner_message() -> None:
    display, buf = _make_display()
    display.start()
    display.start_task(TaskId.EVALUATE_SETTINGS, 'Evaluating settings...')
    display.skip(TaskId.EVALUATE_SETTINGS)
    display.stop()
    out = buf.getvalue()
    assert '☒' in out


def test_progress_display_update_before_start_does_not_raise() -> None:
    display, buf = _make_display()
    display.start_task(TaskId.EVALUATE_SETTINGS, 'hello')
    display.update_message('still nothing')
    display.complete(TaskId.EVALUATE_SETTINGS)
    assert not buf.getvalue()


def test_progress_display_shows_project_url() -> None:
    display, buf = _make_display()
    display.start()
    display.stop()
    assert 'https://github.com/Tatsh/wiswa' in buf.getvalue()


def test_progress_display_pending_tasks_are_shown() -> None:
    display, buf = _make_display()
    display.start()
    display.stop()
    out = buf.getvalue()
    for label in ('Evaluate settings', 'Evaluate project', 'Write templated files', 'Download Yarn',
                  'Copy static files', 'Post-process', 'Configure remote'):
        assert label in out


def test_progress_display_complete_non_current_task_preserves_current() -> None:
    display, buf = _make_display()
    display.start()
    display.start_task(TaskId.EVALUATE_SETTINGS, 'Evaluating settings...')
    display.complete(TaskId.EVALUATE_PROJECT)
    display.stop()
    out = buf.getvalue()
    assert 'Evaluating settings...' in out
    assert '☑' in out


def test_progress_display_skip_non_current_task_preserves_current() -> None:
    display, buf = _make_display()
    display.start()
    display.start_task(TaskId.EVALUATE_SETTINGS, 'Evaluating settings...')
    display.skip(TaskId.EVALUATE_PROJECT)
    display.stop()
    out = buf.getvalue()
    assert 'Evaluating settings...' in out
    assert '☒' in out


def test_progress_display_start_task_before_start_is_noop_when_not_enabled() -> None:
    display, buf = _make_display(enabled=False)
    display.start_task(TaskId.EVALUATE_SETTINGS, 'hi')
    assert not buf.getvalue()


def test_progress_display_update_message_noop_when_disabled() -> None:
    display, buf = _make_display(enabled=False)
    display.update_message('ignored')
    assert not buf.getvalue()
