import time

from django.core.management.base import BaseCommand
from rich import box
from rich.console import Console
from rich.table import Table

import isekai
from isekai.pipelines import get_django_pipeline
from isekai.types import Operation, OperationResult
from isekai.utils.progress import LiveProgressLogger


def get_result_display(result: str) -> str:
    """Map result string to display status."""
    if result == "success":
        return "OK"
    elif result == "partial_success":
        return "WARN"
    else:
        return "ERROR"

    return "UNKNOWN"


class Command(BaseCommand):
    help = "Run isekai ETL operations with live progress display"

    console: Console

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Skip interactive prompts and run automatically",
        )

    def handle(self, *args, **options):
        console = Console(file=self.stdout)  # type: ignore

        # Create the header with Unicode underline
        version = isekai.__version__
        header = f"ISEKAI v{version} (Your data in another world)"
        underline = "─" * len(header)

        # Print the header
        console.print(header, style="bold")
        console.print(underline)
        console.print("")  # Empty line

        # Display pipeline configuration
        pipeline = get_django_pipeline()

        try:
            pipeline_config = pipeline.get_configuration()
        except Exception as e:
            console.print(f"Error loading pipeline configuration: {e}")
            return

        # Print Pipeline header separately (not italicized)
        console.print("Pipeline")

        # Create table without title
        table = Table(show_header=True, header_style="bold", box=box.SQUARE)
        table.add_column("Stage", style="cyan", no_wrap=True)
        table.add_column("Processors", style="white")

        # Add rows for each stage
        for stage, processors in pipeline_config.items():
            if processors:
                # Add first processor in the stage
                table.add_row(stage, processors[0])
                # Add remaining processors with empty stage column
                for processor in processors[1:]:
                    table.add_row("", processor)
            else:
                # No processors for this stage
                table.add_row(stage, "[dim]None[/dim]")

        # Display table
        console.print(table)
        console.print()

        # Ask for confirmation unless --no-input is specified
        if not options.get("no_input", False):
            response = input("Start pipeline? [y/N]: ").lower().strip()
            if response not in ["y", "yes"]:
                console.print("Pipeline cancelled.")
                return

        # Run the pipeline
        console.print()
        pipeline_start = time.time()
        progress_logger = LiveProgressLogger()

        results = []

        # Seed
        seed_result = self.execute_step(
            console,
            progress_logger,
            "Seeding",
            pipeline.seed,
        )
        if seed_result:
            results.append(seed_result)

        # Extract and Mine loop
        newly_seeded_count = 1  # Initialize to enter the loop
        while newly_seeded_count > 0:
            # Extract
            execute_result = self.execute_step(
                console,
                progress_logger,
                "Extracting",
                pipeline.extract,
            )

            if execute_result:
                results.append(execute_result)

            # Mine
            mine_result = self.execute_step(
                console,
                progress_logger,
                "Mining",
                pipeline.mine,
            )

            if mine_result:
                newly_seeded_count = mine_result.metadata.get("newly_seeded_count", 0)
                results.append(mine_result)
            else:
                # If mining failed, stop the loop
                newly_seeded_count = 0

        # Transform
        transform_result = self.execute_step(
            console,
            progress_logger,
            "Transforming",
            pipeline.transform,
        )
        if transform_result:
            results.append(transform_result)

        # Load
        load_result = self.execute_step(
            console,
            progress_logger,
            "Loading",
            pipeline.load,
        )
        if load_result:
            results.append(load_result)

        # Calculate total time
        total_time = time.time() - pipeline_start

        # Print completion message
        console.print(f"[[green]DONE[/green]] Pipeline finished in {total_time:.1f}s")
        console.print()

        object_stats = {}
        if load_result and load_result.metadata:
            object_stats = load_result.metadata.get("object_stats", {})

        # Print summary table
        console.print("Summary")
        summary_table = Table(show_header=True, header_style="bold", box=box.SQUARE)
        summary_table.add_column("Object Type", style="cyan", no_wrap=True)
        summary_table.add_column("Count", style="white")

        # Add rows for each object type
        for obj_type, count in object_stats.items():
            summary_table.add_row(obj_type, str(count))

        # Display table
        console.print(summary_table)
        console.print()

        # Calculate overall status
        has_errors = any(r.result == "failure" for r in results)
        has_warnings = any(r.result == "partial_success" for r in results)

        if has_errors:
            status = "[red]FAILED[/red]"
        elif has_warnings:
            status = "[yellow]COMPLETED WITH WARNINGS[/yellow]"
        else:
            status = "[green]COMPLETED SUCCESSFULLY[/green]"

        console.print(f"Result: {status}")

    def execute_step(
        self,
        console: Console,
        progress_logger: LiveProgressLogger,
        step_name: str,
        step_func: Operation,
    ) -> OperationResult | None:
        messages = []
        with progress_logger.task(step_name) as task_manager:
            try:
                result = step_func()
                messages = result.messages
                task_manager.set_status(get_result_display(result.result))
            except Exception as e:
                result = None
                messages = [f"Error: {e}"]
                task_manager.set_status("ERROR")

        for message in messages:
            console.print(f"  {message}")

        console.print("")  # Empty line between operations

        return result
