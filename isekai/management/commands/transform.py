import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from isekai.operations import transform


class Command(BaseCommand):
    help = "Transform mined resources into target specifications"

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

        transform(verbose=options["verbose"])
