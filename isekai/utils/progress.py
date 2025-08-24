import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from rich import box
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, ProgressColumn, TextColumn
from rich.text import Text


class DotsColumn(ProgressColumn):
    """Column that displays dots filling available width."""

    def __init__(self, total_width: int = 80):
        super().__init__()
        self.total_width = total_width

    def render(self, task):
        # Calculate dots needed: total_width - task_name - space - status - time
        task_name_len = len(task.description)
        status_len = 4  # "[OK]" or "[RUNNING]"
        time_len = 5  # "12.3s" format
        spaces_len = 3  # One space before dots, one before status, one before time

        dots_needed = (
            self.total_width - task_name_len - status_len - time_len - spaces_len
        )
        dots_needed = max(5, dots_needed)  # Minimum 5 dots

        return Text("." * dots_needed, style="dim")


class StatusColumn(ProgressColumn):
    """Column that displays task status."""

    def render(self, task):
        if task.finished:
            return Text.from_markup("[[green]OK[/green]]")
        else:
            return Text.from_markup("[[yellow]RUNNING[/yellow]]")


class TimeColumn(ProgressColumn):
    """Column that displays elapsed time in seconds with decimal precision."""

    def __init__(self):
        super().__init__()
        self.final_times = {}  # Store final times for finished tasks

    def render(self, task):
        elapsed = task.elapsed
        if elapsed is None:
            return Text("0.0s", style="progress.elapsed")

        # If task just finished, store the final time
        if task.finished and task.id not in self.final_times:
            self.final_times[task.id] = elapsed

        # Use stored final time if task is finished
        display_time = self.final_times.get(task.id, elapsed)
        style = "white" if task.finished else "progress.elapsed"
        return Text(f"{display_time:.1f}s", style=style)


class LiveLogHandler(logging.Handler):
    """Logging handler that displays logs in a live Rich panel."""

    def __init__(self, live: Live, progress: Progress, max_lines: int = 10) -> None:
        super().__init__()
        self.live = live
        self.progress = progress
        self.max_lines = max_lines
        self.lines: list[str] = []
        self.setFormatter(logging.Formatter("[%(name)s] %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        formatted_message = self.format(record)
        self.lines.append(formatted_message)
        if len(self.lines) > self.max_lines:
            self.lines = self.lines[-self.max_lines :]

        # Always update with logs if we have any
        if self.lines:
            log_content = "\n".join(self.lines)
            log_panel = Panel(
                log_content,
                title="",
                border_style="dim",
                box=box.SQUARE,
                padding=(0, 0, 0, 0),
            )
            # Create the group with progress and logs
            display_group = Group(self.progress, log_panel)
            self.live.update(display_group)
        else:
            self.live.update(self.progress)


class LiveProgressLogger:
    """Live progress display with optional log capturing."""

    def __init__(
        self,
        total_width: int = 80,
        max_log_lines: int = 3,
        logger_name: str
        | list[str]
        | None = None,  # None = all logs, str = single logger, list = multiple loggers
        refresh_per_second: int = 8,
    ):
        self.total_width = total_width
        self.max_log_lines = max_log_lines
        self.refresh_per_second = refresh_per_second

        # Handle different logger name formats
        if logger_name is None:
            self.logger_names = [""]  # Root logger captures all
        elif isinstance(logger_name, str):
            self.logger_names = [logger_name or ""]  # Single logger
        else:
            self.logger_names = logger_name  # Multiple loggers

    @contextmanager
    def task(self, description: str) -> Iterator[logging.Logger]:
        """Context manager for a single task."""
        # Create fresh instances for each task
        progress = Progress(
            TextColumn("{task.description}"),
            DotsColumn(total_width=self.total_width),
            StatusColumn(),
            TimeColumn(),
            expand=False,
        )

        with Live(progress, refresh_per_second=self.refresh_per_second) as live:
            task_id = progress.add_task(description)
            handler = LiveLogHandler(live, progress, self.max_log_lines)
            handler.setLevel(logging.DEBUG)  # Accept all log levels

            # Set up handlers for all specified loggers
            loggers = []
            for logger_name in self.logger_names:
                logger = logging.getLogger(logger_name)
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
                loggers.append(logger)

            try:
                # Return the first logger (or root logger) for convenience
                yield loggers[0]
            finally:
                # Clean up all handlers
                for logger in loggers:
                    logger.removeHandler(handler)
                progress.update(task_id, completed=1, total=1)
                live.update(progress)
                time.sleep(0.5)
