import logging

from isekai.utils import get_resource_model

Resource = get_resource_model()
logger = logging.getLogger(__name__)


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
                if data.data_type == "text" and isinstance(data.data, str):
                    resource.text_data = data.data
                elif data.data_type == "blob" and isinstance(data.data, bytes):
                    resource.blob_data = data.data  # type: ignore[assignment]

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
