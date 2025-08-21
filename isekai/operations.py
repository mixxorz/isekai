import logging
from typing import cast

from django.core.files.base import ContentFile

from isekai.types import BinaryData, ResourceData
from isekai.utils import get_resource_model

Resource = get_resource_model()
logger = logging.getLogger(__name__)


def seed(verbose: bool = False) -> None:
    """Seeds resources from various sources."""
    if verbose:
        logger.setLevel(logging.INFO)

    seeder = Resource.seeder

    if verbose:
        logger.info(f"Using seeder: {seeder.__class__.__name__}")

    keys = seeder.seed()

    if verbose:
        logger.info(f"Found {len(keys)} keys from seeder")

    # Get existing resource keys to avoid duplicates
    # TODO: Optimize using `bulk_create` with `ignore_conflicts=True`
    existing_keys = Resource.objects.filter(key__in=keys).values_list("key", flat=True)
    new_keys = set(keys) - set(existing_keys)

    if verbose:
        logger.info(
            f"Existing resources: {len(existing_keys)}, New resources: {len(new_keys)}"
        )

    if not new_keys:
        if verbose:
            logger.info("No new resources to seed")
        return

    resources = []
    for key in new_keys:
        resources.append(Resource(key=key))

        if verbose:
            logger.info(f"Seeded resource: {key}")

    if verbose:
        logger.info("Saving seeded resources to database...")

    Resource.objects.bulk_create(resources)

    if verbose:
        logger.info(f"Seeding completed: {len(resources)} resources seeded")


def extract(verbose: bool = False) -> None:
    """Extracts data from a source."""
    if verbose:
        logger.setLevel(logging.INFO)

    extractor = Resource.extractor

    resources = Resource.objects.filter(status=Resource.Status.SEEDED)

    if verbose:
        logger.info(f"Found {resources.count()} seeded resources to process")

    for resource in resources:
        if verbose:
            logger.info(f"Processing resource: {resource.key}")

        try:
            data = extractor.extract(resource.key)

            if data:
                resource.mime_type = data.mime_type
                resource.data_type = data.data_type

                # Merge metadata
                if resource.metadata is None:
                    resource.metadata = {}  # type: ignore[assignment]

                resource.metadata.update(data.metadata)

                if data.data_type == "text" and isinstance(data.data, str):
                    resource.text_data = data.data
                elif data.data_type == "blob" and isinstance(data.data, BinaryData):
                    resource.blob_data.save(
                        data.data.filename,
                        ContentFile(data.data.data),
                        save=False,
                    )

                if verbose:
                    logger.info(
                        f"Extracted {data.data_type} data ({data.mime_type}) for {resource.key}"
                    )

            resource.transition_to(Resource.Status.EXTRACTED)

            if verbose:
                logger.info(f"Successfully extracted: {resource.key}")

        except Exception as e:
            resource.last_error = f"{e.__class__.__name__}: {str(e)}"

            if verbose:
                logger.error(f"Failed to extract {resource.key}: {e}")

    if verbose:
        logger.info("Saving changes to database...")

    Resource.objects.bulk_update(
        resources,
        [
            "mime_type",
            "data_type",
            "text_data",
            "blob_data",
            "metadata",
            "status",
            "extracted_at",
            "last_error",
        ],
    )

    if verbose:
        extracted_count = sum(
            1 for r in resources if r.status == Resource.Status.EXTRACTED
        )
        error_count = sum(1 for r in resources if r.last_error)
        logger.info(
            f"Extraction completed: {extracted_count} successful, {error_count} errors"
        )


def mine(verbose=False):
    miner = Resource.miner

    resources = Resource.objects.filter(status=Resource.Status.EXTRACTED)

    for resource in resources:
        resource_data = (
            cast(str, resource.data)
            if resource.data_type == "text"
            else BinaryData(
                filename=resource.blob_data.name,
                # TODO: Handle large files more efficiently, e.g. by passing a
                # file-like object instead
                data=resource.blob_data.read(),
            )
        )

        # Mine the resource
        keys = miner.mine(
            resource.key,
            ResourceData(
                mime_type=resource.mime_type,
                data_type=resource.data_type,
                data=resource_data,
                metadata=resource.metadata or {},
            ),
        )
        mined_resources = [Resource(key=key) for key in keys]

        # Create resources that don't already exist
        Resource.objects.bulk_create(mined_resources, ignore_conflicts=True)

        # Update the original resource that was mined
        resource.dependencies.set(keys)
        resource.transition_to(Resource.Status.MINED)
        resource.save()
