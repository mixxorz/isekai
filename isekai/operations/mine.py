import logging

from isekai.types import BlobResource, Key, MinedResource, PathFileProxy
from isekai.utils.core import get_resource_model

Resource = get_resource_model()
logger = logging.getLogger(__name__)


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
            new_resources = [
                Resource(
                    key=str(mr.key), metadata=dict(mr.metadata) if mr.metadata else None
                )
                for mr in mined_resources
            ]

            # Create resources that don't already exist
            Resource.objects.bulk_create(new_resources, ignore_conflicts=True)

            # Update the original resource that was mined
            # NB: We set the dependencies whether or not they were created now
            # by the bulk_create or already existed.
            resource.dependencies.set(mined_key_strings)  # type: ignore[call-arg]
            resource.transition_to(Resource.Status.MINED)
            resource.save()

            # Clean up temporary file if it was a blob resource
            if isinstance(resource_obj, BlobResource) and isinstance(
                resource_obj.file_ref, PathFileProxy
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
