import logging

from django.core.management.base import BaseCommand

from isekai.operations import extract


class Command(BaseCommand):
    help = "Extract data from seeded resources"

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose logging output",
        )

    def handle(self, *args, **options):
        if options["verbose"]:
            # Configure logging to output to console
            logging.basicConfig(
                level=logging.INFO,
                format="%(levelname)s: %(message)s",
                force=True,
            )

        extract(verbose=options["verbose"])
