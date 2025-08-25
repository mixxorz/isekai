import logging

from isekai.types import OperationResult, SeededResource
from isekai.utils.core import get_resource_model

Resource = get_resource_model()
logger = logging.getLogger(__name__)


def seed(verbose: bool = False) -> OperationResult:
    """Seeds resources from various sources."""
    if verbose:
        logger.setLevel(logging.INFO)

    seeders = Resource.seeders

    if verbose:
        logger.info(f"Using {len(seeders)} seeders")

    failed_seeders = []

    seeded_resources: list[SeededResource] = []
    for seeder in seeders:
        try:
            resources = seeder.seed()
        except Exception:
            failed_seeders.append(seeder)
            continue

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

    messages = [
        f"Ran {len(seeders)} seeders",
        f"Seeded {len(resources)} resources",
    ]

    if failed_seeders:
        messages.append(f"{len(failed_seeders)} seeders failed")

    return OperationResult(
        result="success" if not failed_seeders else "partial_success",
        messages=messages,
        metadata={},
    )
