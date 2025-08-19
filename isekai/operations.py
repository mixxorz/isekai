from isekai.types import ExtractionError, TransitionError
from isekai.utils import get_resource_model

Resource = get_resource_model()


def extract():
    """Extracts data from a source."""
    extractor = Resource.extractor

    resources = Resource.objects.filter(status=Resource.Status.SEEDED)

    for resource in resources:
        try:
            data = extractor.extract(resource.key)

            if data:
                resource.mime_type = data.mime_type
                resource.data_type = data.data_type
                if data.data_type == "text":
                    resource.text_data = data.data
                elif data.data_type == "blob":
                    resource.blob_data = data.data

            resource.transition_to(Resource.Status.EXTRACTED)
        except (ExtractionError, TransitionError) as e:
            resource.last_error = f"{e.__class__.__name__}: {str(e)}"

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
