import logging

from isekai.types import SeededResource
from isekai.utils import get_resource_model

Resource = get_resource_model()
logger = logging.getLogger(__name__)


def seed(verbose: bool = False) -> None:
    """Seeds resources from various sources."""
    if verbose:
        logger.setLevel(logging.INFO)

    seeders = Resource.seeders

    if verbose:
        logger.info(f"Using {len(seeders)} seeders")

    seeded_resources: list[SeededResource] = []
    for seeder in seeders:
        seeded_resources.extend(seeder.seed())

    if verbose:
        logger.info(f"Found {len(seeded_resources)} resources from seeders")

    resources = []
    for seeded_resource in seeded_resources:
        resource = Resource(
            key=str(seeded_resource.key),
            metadata=seeded_resource.metadata or None,
        )
        resources.append(resource)

        if verbose:
            logger.info(f"Seeded resource: {seeded_resource.key}")

    if verbose:
        logger.info("Saving seeded resources to database...")

    Resource.objects.bulk_create(resources, ignore_conflicts=True)

    if verbose:
        logger.info(f"Seeding completed: {len(resources)} resources processed")
