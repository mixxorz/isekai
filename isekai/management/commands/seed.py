import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from isekai.operations import seed


class Command(BaseCommand):
    help = "Seed resources from configured seeder"

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

        seed(verbose=options["verbose"])
