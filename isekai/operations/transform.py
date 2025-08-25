import logging

from django.contrib.contenttypes.models import ContentType

from isekai.types import Key, OperationResult, TransformError
from isekai.utils.core import get_resource_model

Resource = get_resource_model()
logger = logging.getLogger(__name__)


def transform(verbose: bool = False) -> OperationResult:
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
            spec = None
            for transformer in transformers:
                if spec := transformer.transform(key, resource_obj):
                    break

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
    transformed_count = sum(
        1 for r in resources if r.status == Resource.Status.TRANSFORMED
    )
    error_count = sum(1 for r in resources if r.last_error)

    if verbose:
        logger.info(
            f"Transform completed: {transformed_count} successful, {error_count} errors"
        )

    messages = [
        f"Processed {len(resources)} resources",
        f"Transformed {transformed_count} resources",
    ]

    if error_count:
        messages.append(f"Failed to transform {error_count} resources")

    return OperationResult(
        result="success" if error_count == 0 else "partial_success",
        messages=messages,
        metadata={},
    )
