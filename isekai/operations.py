import logging
import tempfile
from pathlib import Path
from typing import cast

from django.core.files.base import ContentFile

from isekai.types import BlobResource, Key, TextResource
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

    seeded_resources = seeder.seed()

    if verbose:
        logger.info(f"Found {len(seeded_resources)} resources from seeder")

    # Extract key strings for database lookup
    key_strings = [str(sr.key) for sr in seeded_resources]

    # Get existing resource keys to avoid duplicates
    # TODO: Optimize using `bulk_create` with `ignore_conflicts=True`
    existing_keys = set(
        Resource.objects.filter(key__in=key_strings).values_list("key", flat=True)
    )

    # Filter out existing resources
    new_seeded_resources = [
        sr for sr in seeded_resources if str(sr.key) not in existing_keys
    ]

    if verbose:
        logger.info(
            f"Existing resources: {len(existing_keys)}, New resources: {len(new_seeded_resources)}"
        )

    if not new_seeded_resources:
        if verbose:
            logger.info("No new resources to seed")
        return

    resources = []
    for seeded_resource in new_seeded_resources:
        resource = Resource(
            key=str(seeded_resource.key),
            metadata=seeded_resource.metadata or None,
        )
        resources.append(resource)

        if verbose:
            logger.info(f"Seeded resource: {seeded_resource.key}")

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
            key = Key.from_string(resource.key)
            extracted_data = extractor.extract(key)

            if extracted_data:
                resource.mime_type = extracted_data.mime_type

                # Merge metadata
                if resource.metadata is None:
                    resource.metadata = {}  # type: ignore[assignment]

                resource.metadata.update(dict(extracted_data.metadata))

                if isinstance(extracted_data, TextResource):
                    resource.data_type = "text"
                    resource.text_data = extracted_data.text

                    if verbose:
                        logger.info(
                            f"Extracted text data ({extracted_data.mime_type}) for {resource.key}"
                        )
                elif isinstance(extracted_data, BlobResource):
                    resource.data_type = "blob"
                    # Read the temporary file and save it to the model's FileField
                    with open(extracted_data.path, "rb") as temp_file:
                        resource.blob_data.save(
                            extracted_data.filename,
                            ContentFile(temp_file.read()),
                            save=False,
                        )
                    # Clean up the temporary file
                    extracted_data.path.unlink(missing_ok=True)

                    if verbose:
                        logger.info(
                            f"Extracted blob data ({extracted_data.mime_type}) for {resource.key}"
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


def mine(verbose: bool = False) -> None:
    """Mines extracted resources to discover new resources."""
    if verbose:
        logger.setLevel(logging.INFO)

    miner = Resource.miner

    resources = Resource.objects.filter(status=Resource.Status.EXTRACTED)

    if verbose:
        logger.info(f"Found {resources.count()} extracted resources to process")

    for resource in resources:
        if verbose:
            logger.info(f"Mining resource: {resource.key}")

        # Create appropriate resource object for mining
        key = Key.from_string(resource.key)
        if resource.data_type == "text":
            resource_obj = TextResource(
                mime_type=resource.mime_type,
                text=cast(str, resource.text_data),
                metadata=resource.metadata or {},
            )
        else:
            # For blob data, create a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.write(resource.blob_data.read())
            temp_file.close()

            resource_obj = BlobResource(
                mime_type=resource.mime_type,
                filename=resource.blob_data.name,
                path=Path(temp_file.name),
                metadata=resource.metadata or {},
            )

        # Mine the resource
        mined_resources = miner.mine(key, resource_obj)

        if verbose:
            logger.info(
                f"Discovered {len(mined_resources)} new resources from {resource.key}"
            )

        # Extract key strings for database operations
        mined_key_strings = [str(mr.key) for mr in mined_resources]

        # Create Resource objects for new keys
        new_django_resources = [
            Resource(
                key=str(mr.key), metadata=dict(mr.metadata) if mr.metadata else None
            )
            for mr in mined_resources
        ]

        # Create resources that don't already exist
        Resource.objects.bulk_create(new_django_resources, ignore_conflicts=True)

        # Update the original resource that was mined
        resource.dependencies.set(mined_key_strings)
        resource.transition_to(Resource.Status.MINED)
        resource.save()

        # Clean up temporary file if it was a blob resource
        if isinstance(resource_obj, BlobResource):
            resource_obj.path.unlink(missing_ok=True)

        if verbose:
            logger.info(f"Successfully mined: {resource.key}")

    if verbose:
        mined_count = len(resources)
        logger.info(f"Mining completed: {mined_count} resources processed")
