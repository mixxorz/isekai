from django.core.management.base import BaseCommand
from rich import box
from rich.console import Console
from rich.table import Table

import isekai
from isekai.utils.pipeline import get_pipeline_configuration


class Command(BaseCommand):
    help = "Run isekai ETL operations with live progress display"

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Skip interactive prompts and run automatically",
        )

    def handle(self, *args, **options):
        # Create the header with Unicode underline
        version = isekai.__version__
        header = f"ISEKAI v{version} (Your data in another world)"
        underline = "─" * len(header)

        # Print the header
        self.stdout.write(header)
        self.stdout.write(underline)
        self.stdout.write("")  # Empty line

        # Display pipeline configuration
        self.display_pipeline_configuration()

        # Ask for confirmation unless --no-input is specified
        if not options.get("no_input", False):
            response = input("Start pipeline? [y/N]: ").lower().strip()
            if response not in ["y", "yes"]:
                self.stdout.write("Pipeline cancelled.")
                return

        # TODO: Run the actual pipeline here
        self.stdout.write("Pipeline would start here...")

    def display_pipeline_configuration(self):
        """Display the pipeline configuration table."""
        console = Console(file=self.stdout)

        # Get pipeline configuration
        try:
            pipeline_config = get_pipeline_configuration()
        except Exception as e:
            self.stdout.write(f"Error loading pipeline configuration: {e}")
            return

        # Print Pipeline header separately (not italicized)
        self.stdout.write("Pipeline")

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
