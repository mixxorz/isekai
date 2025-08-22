import logging

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile

from isekai.types import (
    BlobResource,
    Key,
    MinedResource,
    PathFileRef,
    SeededResource,
    TextResource,
    TransformError,
)
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


def extract(verbose: bool = False) -> None:
    """Extracts data from a source."""
    if verbose:
        logger.setLevel(logging.INFO)

    extractors = Resource.extractors

    if verbose:
        logger.info(f"Using {len(extractors)} extractors")

    resources = Resource.objects.filter(status=Resource.Status.SEEDED)

    if verbose:
        logger.info(f"Found {resources.count()} seeded resources to process")

    for resource in resources:
        if verbose:
            logger.info(f"Extracting resource: {resource.key}")

        try:
            key = Key.from_string(resource.key)

            # Extract using the first extractor that can handle the resource
            extracted_resource = None
            for extractor in extractors:
                er = extractor.extract(key)
                if er:
                    extracted_resource = er
                    break

            if extracted_resource:
                resource.mime_type = extracted_resource.mime_type

                # Merge metadata
                if resource.metadata is None:
                    resource.metadata = {}  # type: ignore[assignment]

                resource.metadata.update(dict(extracted_resource.metadata))

                if isinstance(extracted_resource, TextResource):
                    resource.data_type = "text"
                    resource.text_data = extracted_resource.text

                    if verbose:
                        logger.info(
                            f"Extracted text data ({extracted_resource.mime_type}) for {resource.key}"
                        )
                elif isinstance(extracted_resource, BlobResource):
                    resource.data_type = "blob"
                    # Read the temporary file and save it to the model's FileField
                    with extracted_resource.file_ref.open() as temp_file:
                        resource.blob_data.save(
                            extracted_resource.filename,
                            ContentFile(temp_file.read()),
                            save=False,
                        )

                    # Clean up the temporary file
                    assert isinstance(extracted_resource.file_ref, PathFileRef)
                    extracted_resource.file_ref.path.unlink(missing_ok=True)

                    if verbose:
                        logger.info(
                            f"Extracted blob data ({extracted_resource.mime_type}) for {resource.key}"
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

    miners = Resource.miners

    if verbose:
        logger.info(f"Using {len(miners)} miners")

    resources = Resource.objects.filter(status=Resource.Status.EXTRACTED)

    if verbose:
        logger.info(f"Found {resources.count()} extracted resources to process")

    for resource in resources:
        if verbose:
            logger.info(f"Mining resource: {resource.key}")

        # Create appropriate resource object for mining
        key = Key.from_string(resource.key)
        resource_obj = resource.to_resource_dataclass()

        try:
            # Mine the resource
            mined_resources: list[MinedResource] = []

            for miner in miners:
                mined_resources.extend(miner.mine(key, resource_obj))

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
            if isinstance(resource_obj, BlobResource) and isinstance(
                resource_obj.file_ref, PathFileRef
            ):
                resource_obj.file_ref.path.unlink(missing_ok=True)

            if verbose:
                logger.info(f"Successfully mined: {resource.key}")

        except Exception as e:
            resource.last_error = f"{e.__class__.__name__}: {str(e)}"

            if verbose:
                logger.error(f"Failed to mine {resource.key}: {e}")

    if verbose:
        logger.info("Saving changes to database...")

    Resource.objects.bulk_update(
        resources,
        [
            "status",
            "mined_at",
            "last_error",
        ],
    )

    if verbose:
        mined_count = sum(1 for r in resources if r.status == Resource.Status.MINED)
        error_count = sum(1 for r in resources if r.last_error)
        logger.info(f"Mining completed: {mined_count} successful, {error_count} errors")


def transform(verbose: bool = False) -> None:
    """Transforms mined resources into target specifications."""
    if verbose:
        logger.setLevel(logging.INFO)

    transformers = Resource.transformers

    if verbose:
        logger.info(f"Using {len(transformers)} transformers")

    content_types = ContentType.objects.values_list("app_label", "model", "pk")

    ct_map = {f"{app_label}.{model}": pk for app_label, model, pk in content_types}

    resources = Resource.objects.filter(status=Resource.Status.MINED)

    if verbose:
        logger.info(f"Found {resources.count()} mined resources to process")

    for resource in resources:
        if verbose:
            logger.info(f"Transforming resource: {resource.key}")

        try:
            key = Key.from_string(resource.key)
            resource_obj = resource.to_resource_dataclass()
            # Use the first transformer that can handle the resource
            spec = next(
                transformer.transform(key, resource_obj) for transformer in transformers
            )

            if spec:
                try:
                    content_type = ct_map[spec.content_type.lower()]
                except KeyError as e:
                    raise TransformError(
                        f"Unknown content type: {spec.content_type}"
                    ) from e

                spec_dict = spec.to_dict()
                resource.target_content_type_id = content_type
                resource.target_spec = spec_dict["attributes"]

                resource.transition_to(Resource.Status.TRANSFORMED)

                if verbose:
                    logger.info(f"Successfully transformed: {resource.key}")

        except Exception as e:
            resource.last_error = f"{e.__class__.__name__}: {str(e)}"

            if verbose:
                logger.error(f"Failed to transform {resource.key}: {e}")

    if verbose:
        logger.info("Saving changes to database...")

    Resource.objects.bulk_update(
        resources,
        [
            "target_content_type_id",
            "target_spec",
            "status",
            "transformed_at",
            "last_error",
        ],
    )

    if verbose:
        transformed_count = sum(
            1 for r in resources if r.status == Resource.Status.TRANSFORMED
        )
        error_count = sum(1 for r in resources if r.last_error)
        logger.info(
            f"Transform completed: {transformed_count} successful, {error_count} errors"
        )
