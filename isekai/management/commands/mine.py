import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from isekai.operations.mine import mine


class Command(BaseCommand):
    help = "Mine extracted resources to discover new resources"

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

        mine(verbose=options["verbose"])
