"""Rich-based progress display with an ASCII banner, a task checklist, and a spinner line."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING
import secrets
import sys

from rich.console import Console, Group
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from types import TracebackType

    from rich.console import ConsoleRenderable, RichCast
    from typing_extensions import Self

__all__ = ('ProgressDisplay', 'TaskId', 'TaskState')

_DOT_FAMILY_WEIGHT = 4
"""Weight applied to ``dots*`` spinner families in the random selection pool.

:meta hide-value:
"""
_DOT_SPINNER_NAMES = ('dots', 'dots2', 'dots3', 'dots4', 'dots5', 'dots6', 'dots7', 'dots8',
                      'dots8Bit', 'dots9', 'dots10', 'dots11', 'dots12')
"""Spinner names in the ``dots`` family.

:meta hide-value:
"""
_OTHER_SPINNER_NAMES = ('pipe', 'star', 'star2', 'hamburger', 'growVertical', 'growHorizontal',
                        'earth', 'runner', 'bouncingBall', 'bouncingBar', 'arc', 'circle')
"""Non-``dots`` spinner names.

:meta hide-value:
"""
_SPINNER_CHOICE_POOL: tuple[str, ...] = (tuple(name for name in _DOT_SPINNER_NAMES
                                               for _ in range(_DOT_FAMILY_WEIGHT)) +
                                         _OTHER_SPINNER_NAMES)
"""Weighted pool of spinner names used by :py:func:`_random_cli_spinner`.

:meta hide-value:
"""

_BANNER_LINES = (
    '██╗    ██╗  ██╗  ███████╗  ██╗    ██╗   █████╗ ',
    '██║    ██║  ██║  ██╔════╝  ██║    ██║  ██╔══██╗',
    '██║ █╗ ██║  ██║  ███████╗  ██║ █╗ ██║  ███████║',
    '██║███╗██║  ██║  ╚════██║  ██║███╗██║  ██╔══██║',
    '╚███╔███╔╝  ██║  ███████║  ╚███╔███╔╝  ██║  ██║',
    ' ╚══╝╚══╝   ╚═╝  ╚══════╝   ╚══╝╚══╝   ╚═╝  ╚═╝',
)
"""Unicode block-letter banner for the progress header.

:meta hide-value:
"""
_BANNER_URL = 'https://github.com/Tatsh/wiswa'
"""Project homepage shown underneath the banner.

:meta hide-value:
"""


def _random_cli_spinner() -> str:  # pragma: no cover
    """
    Pick a random spinner name, weighted towards the ``dots`` family.

    Returns
    -------
    str
        A spinner name accepted by :py:class:`rich.spinner.Spinner`.
    """
    return secrets.choice(_SPINNER_CHOICE_POOL)


class TaskState(Enum):
    """State of a progress task."""

    PENDING = 'pending'
    """The task has not yet started."""
    RUNNING = 'running'
    """The task is currently in progress."""
    DONE = 'done'
    """The task finished successfully."""
    SKIPPED = 'skipped'
    """The task was skipped."""


class TaskId(Enum):
    """Identifiers for the progress tasks displayed in the checklist."""

    EVALUATE_SETTINGS = 'evaluate_settings'
    """Evaluating merged settings from ``.wiswa.jsonnet``."""
    EVALUATE_PROJECT = 'evaluate_project'
    """Evaluating ``project.jsonnet`` manifests."""
    WRITE_TEMPLATES = 'write_templates'
    """Writing Jinja2 templated files."""
    DOWNLOAD_YARN = 'download_yarn'
    """Downloading Yarn and its plugins."""
    COPY_STATIC = 'copy_static'
    """Copying static files."""
    POST_PROCESS = 'post_process'
    """Post-processing and manifest normalisation."""
    CONFIGURE_REMOTE = 'configure_remote'
    """Configuring the remote Git host (GitHub or GitLab)."""


@dataclass
class _Task:
    task_id: TaskId
    label: str
    state: TaskState = TaskState.PENDING
    message: str = ''


_DEFAULT_TASKS: tuple[tuple[TaskId, str], ...] = (
    (TaskId.EVALUATE_SETTINGS, 'Evaluate settings'),
    (TaskId.EVALUATE_PROJECT, 'Evaluate project'),
    (TaskId.WRITE_TEMPLATES, 'Write templated files'),
    (TaskId.DOWNLOAD_YARN, 'Download Yarn'),
    (TaskId.COPY_STATIC, 'Copy static files'),
    (TaskId.POST_PROCESS, 'Post-process'),
    (TaskId.CONFIGURE_REMOTE, 'Configure remote'),
)


@dataclass
class ProgressDisplay:
    """
    Live progress display with an ASCII banner, a checklist, and a spinner line.

    The display renders three regions: a coloured ASCII banner, a numbered list of tasks with
    Unicode checkboxes, and a spinner with the latest status message underneath. Completed tasks
    get a green checkmark, running tasks are bold cyan, and skipped tasks are dimmed with
    strike-through. When the display is disabled (debug or quiet mode, or when stderr is not a
    TTY), it becomes a no-op.

    Parameters
    ----------
    enabled : bool
        Whether the display should render. When false, every method becomes a no-op.
    console : Console | None
        Rich console to draw on. A new stderr console is created when not provided.
    """

    enabled: bool = True
    console: Console | None = None
    _tasks: dict[TaskId, _Task] = field(default_factory=dict, init=False)
    _order: tuple[TaskId, ...] = field(default=(), init=False)
    _current: TaskId | None = field(default=None, init=False)
    _message: str = field(default='', init=False)
    _spinner: Spinner | None = field(default=None, init=False)
    _live: Live | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Populate the default task list and console."""
        if self.console is None:
            self.console = Console(file=sys.stderr)
        self._order = tuple(task_id for task_id, _ in _DEFAULT_TASKS)
        for task_id, label in _DEFAULT_TASKS:
            self._tasks[task_id] = _Task(task_id=task_id, label=label)

    def __enter__(self) -> Self:
        """
        Start the display on context entry.

        Returns
        -------
        Self
            The display instance.
        """
        self.start()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None,
                 exc_tb: TracebackType | None) -> None:
        """Stop the display on context exit."""
        self.stop()

    def complete(self, task_id: TaskId) -> None:
        """
        Mark *task_id* as completed.

        Parameters
        ----------
        task_id : TaskId
            The task to mark as done.
        """
        if not self.enabled:
            return
        self._tasks[task_id].state = TaskState.DONE
        if self._current == task_id:
            self._current = None
        self._refresh()

    def skip(self, task_id: TaskId) -> None:
        """
        Mark *task_id* as skipped.

        Parameters
        ----------
        task_id : TaskId
            The task to mark as skipped.
        """
        if not self.enabled:
            return
        self._tasks[task_id].state = TaskState.SKIPPED
        if self._current == task_id:
            self._current = None
        self._refresh()

    def skip_many(self, task_ids: Iterable[TaskId]) -> None:
        """
        Mark several tasks as skipped.

        Parameters
        ----------
        task_ids : Iterable[TaskId]
            The tasks to mark as skipped.
        """
        for task_id in task_ids:
            self.skip(task_id)

    def start(self) -> None:
        """Begin rendering the live display."""
        if not self.enabled or self._live is not None:
            return
        console = self.console if self.console is not None else Console(file=sys.stderr)
        self.console = console
        self._spinner = Spinner(_random_cli_spinner(), text='')
        self._live = Live(self._render(), console=console, refresh_per_second=12, transient=False)
        self._live.start()

    def start_task(self, task_id: TaskId, message: str = '') -> None:
        """
        Mark *task_id* as the currently running task.

        Parameters
        ----------
        task_id : TaskId
            The task to start.
        message : str
            Optional status message shown on the spinner line.
        """
        if not self.enabled:
            return
        self._tasks[task_id].state = TaskState.RUNNING
        self._current = task_id
        self._message = message or self._tasks[task_id].label
        self._refresh()

    def stop(self) -> None:
        """Stop rendering the live display."""
        if self._live is None:
            return
        self._live.update(self._render(), refresh=True)
        self._live.stop()
        self._live = None
        self._spinner = None

    def update_message(self, message: str) -> None:
        """
        Update the status message on the spinner line.

        Parameters
        ----------
        message : str
            The new message to display.
        """
        if not self.enabled:
            return
        self._message = message
        self._refresh()

    @staticmethod
    def _banner_lines() -> Iterator[Text]:
        for line in _BANNER_LINES:
            yield Text(line, style='bold')
        banner_width = max(len(line) for line in _BANNER_LINES)
        url_line = Text(' ' * max(0, banner_width - len(_BANNER_URL)), style='dim')
        url_line.append(_BANNER_URL, style='underline')
        yield url_line

    def _refresh(self) -> None:
        if self._live is None:
            return
        self._live.update(self._render())

    def _render(self) -> Group:
        renderables: list[ConsoleRenderable | RichCast | str] = list(self._banner_lines())
        renderables.append(Text(''))
        renderables.extend(self._render_task_line(self._tasks[task_id]) for task_id in self._order)
        renderables.append(Text(''))
        if self._spinner is not None:
            self._spinner.update(text=Text(self._message or '...', style='bold'))
            renderables.append(self._spinner)
        return Group(*renderables)

    @staticmethod
    def _render_task_line(task: _Task) -> Text:
        match task.state:
            case TaskState.DONE:
                box = Text('☑ ', style='bold green')
                label = Text(task.label, style='green')
            case TaskState.RUNNING:
                box = Text('☐ ', style='bold cyan')
                label = Text(task.label, style='bold cyan')
            case TaskState.SKIPPED:
                box = Text('☒ ', style='dim')
                label = Text(task.label, style='dim strike')
            case TaskState.PENDING:
                box = Text('☐ ', style='dim')
                label = Text(task.label, style='dim')
        line = Text('  ')
        line.append_text(box)
        line.append_text(label)
        return line
