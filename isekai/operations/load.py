import logging
from typing import overload

from django.db import transaction
from django.db.models import Model, Prefetch

from isekai.types import BlobRef, FileProxy, Key, OperationResult, Ref, Spec
from isekai.utils.core import get_resource_model
from isekai.utils.graphs import resolve_build_order

Resource = get_resource_model()
logger = logging.getLogger(__name__)


def get_created_object_stats(objects: list[Model]) -> dict[str, int]:
    """Returns a dictionary with counts of created objects by their model name."""
    stats = {}
    for obj in objects:
        model_name = obj.__class__.__name__
        stats[model_name] = stats.get(model_name, 0) + 1
    return stats


def load(verbose: bool = False) -> OperationResult:
    """Loads objects from resources"""
    if verbose:
        logger.setLevel(logging.INFO)

    loaders = Resource.loaders

    if verbose:
        logger.info(f"Using {len(loaders)} loaders")

    resources = Resource.objects.filter(
        status=Resource.Status.TRANSFORMED,
    ).prefetch_related(
        Prefetch(
            "dependencies",
            queryset=Resource.objects.only("key"),
        )
    )

    if verbose:
        logger.info(f"Found {resources.count()} transformed resources to process")

    # Calculate build order
    key_to_resource = {resource.key: resource for resource in resources}
    nodes = key_to_resource.keys()
    edges = [
        (resource.key, dep.key)
        for resource in resources
        for dep in resource.dependencies.all()
        # When calculating the build order, we only need to deal with resources
        # that have not been loaded yet. Dependency resources that are already
        # loaded do not need to be taken into consideration, because we can
        # resolve to them immediately; no need for two-phase loading
        if dep.key in nodes
    ]

    graph = resolve_build_order(nodes, edges)

    if verbose:
        logger.info(f"Build order resolved into {len(graph)} phases")

    # Load the objects
    key_to_obj: dict[str, Model] = {}

    @overload
    def resolver(ref: BlobRef) -> FileProxy: ...
    @overload
    def resolver(ref: Ref) -> int | str: ...

    def resolver(ref: Ref) -> FileProxy | int | str:
        # Try to find the object in the pool of resources currently being loaded
        if str(ref.key) in key_to_obj:
            return key_to_obj[str(ref.key)].pk

        # If it's not there, then it's a reference to a resource that has
        # already been loaded
        if obj := Resource.objects.filter(key=str(ref.key)).first():
            if obj and obj.target_object_id:
                return obj.target_object_id

        # If the framework is working correctly, it is logically impossible to
        # reach this case. The build order resolver ensures that all dependency
        # resources are created either before it's needed, or at the same time
        # as the resource that references it.
        raise ValueError(f"Unable to resolve reference: {ref}")

    for node in graph:
        # Each node in the graph is comprised of one OR MORE resources.
        # If there is more than one resource, that means that those resources
        # need to be loaded together using a two-phase loading process in order
        # to resolve circular dependencies.
        # Single resources are also loaded, but they don't need the same
        # circular dependency handling.
        if len(node) == 1:
            if verbose:
                logger.info(f"Loading resource: {list(node)[0]}")
        else:
            if verbose:
                logger.info(
                    f"Loading {len(node)} resources with circular dependencies: {list(node)}"
                )

        specs = []
        for resource_key in node:
            resource = key_to_resource[resource_key]
            ct = resource.target_content_type
            assert ct, "Resource must have a target content type to be loaded"
            model_class = ct.model_class()
            assert model_class, "Unable to resolve model class for content type"

            key = Key.from_string(resource.key)
            spec = Spec.from_dict(
                {
                    "content_type": f"{model_class._meta.label}",
                    "attributes": resource.target_spec,
                }
            )
            specs.append((key, spec))

        # Load the objects
        try:
            with transaction.atomic():
                resources_to_update = []
                created_objects = []
                for loader in loaders:
                    if created_objects := loader.load(specs, resolver):
                        break

                for ckey, cobject in created_objects:
                    key_to_obj[str(ckey)] = cobject
                    resource = key_to_resource[str(ckey)]
                    resource.target_object_id = cobject.pk
                    resource.transition_to(Resource.Status.LOADED)
                    resources_to_update.append(resource)

                    if verbose:
                        logger.info(f"Successfully loaded: {resource.key}")

                Resource.objects.bulk_update(
                    resources_to_update,
                    [
                        "target_object_id",
                        "status",
                        "loaded_at",
                        "last_error",
                    ],
                )
        except Exception as e:
            # Mark resources in this node as failed
            failed_resources = []
            for resource_key in node:
                resource = key_to_resource[resource_key]
                resource.refresh_from_db()
                resource.last_error = f"{e.__class__.__name__}: {str(e)}"
                failed_resources.append(resource)

                if verbose:
                    logger.error(f"Failed to load {resource.key}: {e}")

            # Save the failed resources
            Resource.objects.bulk_update(
                failed_resources,
                ["last_error"],
            )

            # Stop processing - dependent nodes will also fail
            if verbose:
                logger.error(
                    "Stopping load process due to node failure - remaining nodes would likely fail due to missing dependencies"
                )

            return OperationResult(
                result="failure",
                messages=[
                    f"Load failed at node with resources: {list(node)}",
                    f"Error: {e.__class__.__name__}: {str(e)}",
                ],
                metadata={
                    "object_stats": get_created_object_stats(list(key_to_obj.values()))
                },
            )

    all_resources = list(key_to_resource.values())
    loaded_count = sum(1 for r in all_resources if r.status == Resource.Status.LOADED)

    if verbose:
        logger.info(f"Load completed: {loaded_count} successful")

    messages = [
        f"Processed {len(all_resources)} resources",
        f"Loaded {loaded_count} resources",
    ]

    return OperationResult(
        result="success",
        messages=messages,
        metadata={"object_stats": get_created_object_stats(list(key_to_obj.values()))},
    )
