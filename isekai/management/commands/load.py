import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from isekai.operations.load import load


class Command(BaseCommand):
    help = "Load transformed resources into Django models"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose logging output",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["verbose"]:
            # Configure logging to output to console
            logging.basicConfig(
                level=logging.INFO,
                format="%(levelname)s: %(message)s",
                force=True,
            )

        load(verbose=options["verbose"])
