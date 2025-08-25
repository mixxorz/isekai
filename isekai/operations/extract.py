import logging

from django.core.files.base import ContentFile

from isekai.types import BlobResource, Key, OperationResult, PathFileProxy, TextResource
from isekai.utils.core import get_resource_model

Resource = get_resource_model()
logger = logging.getLogger(__name__)


def extract() -> OperationResult:
    """Extracts data from a source."""
    logger.setLevel(logging.INFO)

    extractors = Resource.extractors

    logger.info(f"Using {len(extractors)} extractors")

    resources = Resource.objects.filter(status=Resource.Status.SEEDED)

    logger.info(f"Found {resources.count()} seeded resources to process")

    for resource in resources:
        logger.info(f"Extracting resource: {resource.key}")

        try:
            key = Key.from_string(resource.key)

            # Extract using the first extractor that can handle the resource
            extracted_resource = None
            for extractor in extractors:
                if extracted_resource := extractor.extract(key):
                    break

            if extracted_resource:
                resource.mime_type = extracted_resource.mime_type

                # Merge metadata
                if resource.metadata is None:
                    resource.metadata = {}

                resource.metadata.update(dict(extracted_resource.metadata))

                if isinstance(extracted_resource, TextResource):
                    resource.data_type = "text"
                    resource.text_data = extracted_resource.text

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
                    assert isinstance(extracted_resource.file_ref, PathFileProxy)
                    extracted_resource.file_ref.path.unlink(missing_ok=True)

                    logger.info(
                        f"Extracted blob data ({extracted_resource.mime_type}) for {resource.key}"
                    )

            resource.transition_to(Resource.Status.EXTRACTED)

            logger.info(f"Successfully extracted: {resource.key}")

        except Exception as e:
            resource.last_error = f"{e.__class__.__name__}: {str(e)}"

            logger.error(f"Failed to extract {resource.key}: {e}")

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

    extracted_count = sum(1 for r in resources if r.status == Resource.Status.EXTRACTED)
    error_count = sum(1 for r in resources if r.last_error)

    logger.info(
        f"Extraction completed: {extracted_count} successful, {error_count} errors"
    )

    messages = [
        f"Processed {len(resources)} resources",
        f"Extracted {extracted_count} resources",
    ]

    if error_count:
        messages.append(f"Failed to extract {error_count} resources")

    return OperationResult(
        result="success" if error_count == 0 else "partial_success",
        messages=messages,
        metadata={},
    )
