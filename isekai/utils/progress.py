import logging
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
        task_name_len = len(task.description)
        status_len = 4
        time_len = 5
        spaces_len = 3

        dots_needed = (
            self.total_width - task_name_len - status_len - time_len - spaces_len
        )
        dots_needed = max(5, dots_needed)

        return Text("." * dots_needed, style="dim")


class StatusColumn(ProgressColumn):
    """Column that displays task status."""

    def render(self, task):
        if task.finished:
            status = getattr(task, "_status", "OK")
            if status == "OK":
                return Text.from_markup("[[green]OK[/green]]")
            elif status == "WARN":
                return Text.from_markup("[[yellow]WARN[/yellow]]")
            elif status == "ERROR":
                return Text.from_markup("[[red]ERROR[/red]]")
            else:
                return Text.from_markup("[[green]OK[/green]]")
        else:
            return Text.from_markup("[RUNNING]")


class TimeColumn(ProgressColumn):
    """Column that displays elapsed time in seconds with decimal precision."""

    def __init__(self):
        super().__init__()
        self.final_times = {}

    def render(self, task):
        elapsed = task.elapsed
        if elapsed is None:
            return Text("0.0s", style="progress.elapsed")

        if task.finished and task.id not in self.final_times:
            self.final_times[task.id] = elapsed
        display_time = self.final_times.get(task.id, elapsed)
        style = "white" if task.finished else "progress.elapsed"
        return Text(f"{display_time:.1f}s", style=style)


class LogFormatter(logging.Handler):
    """Handler that formats log records as Rich Text objects for display."""

    LEVEL_COLORS = {
        "DEBUG": "cyan",
        "INFO": "blue",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "magenta",
    }

    def __init__(self, max_lines=20, on_emit=None):
        super().__init__()
        self.max_lines = max_lines
        self.log_rows = []
        self.on_emit = on_emit

    def emit(self, record):
        """Process log record, store formatted data, and trigger callback."""
        try:
            level_color = self.LEVEL_COLORS.get(record.levelname, "white")

            message_color = (
                level_color
                if record.levelname in ("WARNING", "ERROR", "CRITICAL")
                else None
            )

            log_data = {
                "level": record.levelname,
                "level_color": level_color,
                "logger": record.name,
                "message": record.getMessage(),
                "message_color": message_color,
            }

            self.log_rows.append(log_data)

            if len(self.log_rows) > self.max_lines:
                self.log_rows[:] = self.log_rows[-self.max_lines :]

            if self.on_emit:
                formatted_logs = self.format_logs()
                self.on_emit(formatted_logs)

        except Exception:
            self.handleError(record)

    def format_logs(self):
        """Format stored logs as Rich Text objects."""
        if not self.log_rows:
            return []

        max_level_len = max(len(row["level"]) for row in self.log_rows)
        max_logger_len = max(len(row["logger"]) for row in self.log_rows)

        formatted_lines = []
        for row in self.log_rows:
            level_padded = row["level"].ljust(max_level_len)
            level_text = Text()
            level_text.append("[ ", style="dim bold")
            level_text.append(level_padded, style=row["level_color"])
            level_text.append(" ]", style="dim bold")

            logger_padded = row["logger"].ljust(max_logger_len)
            logger_text = Text(logger_padded, style="dim")

            line = Text()
            line.append_text(level_text)
            line.append(" ")
            line.append_text(logger_text)
            line.append(" | ", style="dim bold")
            line.append(row["message"], style=row["message_color"])

            formatted_lines.append(line)

        return formatted_lines


class LoggingCapture:
    """Context manager for capturing logging to a specific handler."""

    def __init__(self, handler):
        self.handler = handler

    def __enter__(self):
        """Set up logging capture for all existing loggers."""
        # Store original state for all loggers (including root)
        self.original_logger_states = {}

        # Handle root logger (empty name)
        root_logger = logging.getLogger()
        self.original_logger_states[""] = {
            "level": root_logger.level,
            "handlers": root_logger.handlers.copy(),
            "propagate": root_logger.propagate,
        }

        # Handle all other loggers
        for name, logger in logging.Logger.manager.loggerDict.items():
            if isinstance(logger, logging.Logger):
                self.original_logger_states[name] = {
                    "level": logger.level,
                    "handlers": logger.handlers.copy(),
                    "propagate": logger.propagate,
                }

                # Configure each logger to propagate and have no handlers
                logger.setLevel(logging.NOTSET)
                logger.handlers.clear()
                logger.propagate = True

        # Configure root logger to handle everything
        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()
        root_logger.addHandler(self.handler)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore original logging setup for all loggers."""
        # Restore all loggers (including root)
        for name, state in self.original_logger_states.items():
            logger = logging.getLogger(name)
            logger.setLevel(state["level"])
            logger.handlers.clear()
            logger.handlers.extend(state["handlers"])
            logger.propagate = state["propagate"]


class TaskManager:
    """Manages task status for progress display."""

    def __init__(self, progress, task_id):
        self.progress = progress
        self.task_id = task_id

    def set_status(self, status: str):
        """Set the final status of the task (OK, WARN, ERROR)."""
        task = self.progress.tasks[self.task_id]
        task._status = status


class LiveProgressLogger:
    """Manages Rich Live display with progress bar and log panel."""

    def __init__(
        self,
        total_width: int = 80,
        max_log_lines: int = 20,
        refresh_per_second: int = 10,
    ):
        self.total_width = total_width
        self.max_log_lines = max_log_lines
        self.refresh_per_second = refresh_per_second

    @contextmanager
    def task(self, description: str):
        """Context manager for a single task with progress and log capture."""
        progress = Progress(
            TextColumn("{task.description}"),
            DotsColumn(total_width=self.total_width),
            StatusColumn(),
            TimeColumn(),
            expand=False,
        )

        with Live(progress, refresh_per_second=self.refresh_per_second) as live:

            def update_display(formatted_logs):
                """Update Live display with progress and formatted logs."""
                if formatted_logs:
                    log_panel = Panel(
                        Group(*formatted_logs),
                        title="",
                        border_style="dim",
                        box=box.SQUARE,
                        padding=(0, 0, 0, 0),
                    )
                    live.update(Group(progress, log_panel))
                else:
                    live.update(progress)

            log_formatter = LogFormatter(
                max_lines=self.max_log_lines, on_emit=update_display
            )

            with LoggingCapture(log_formatter):
                task_id = progress.add_task(description)
                task_manager = TaskManager(progress, task_id)

                yield task_manager

                progress.update(task_id, completed=1, total=1)
