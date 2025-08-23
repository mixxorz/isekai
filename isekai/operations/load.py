from typing import overload

from django.db import transaction
from django.db.models import Prefetch

from isekai.graphs import resolve_build_order
from isekai.types import BlobRef, FileRef, Key, Ref, Spec
from isekai.utils import get_resource_model

Resource = get_resource_model()


def load():
    """Loads objects from resources"""

    loaders = Resource.loaders

    resources = Resource.objects.filter(
        status=Resource.Status.TRANSFORMED,
    ).prefetch_related(
        Prefetch(
            "dependencies",
            queryset=Resource.objects.only("key"),
        )
    )

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

    # Load the objects
    key_to_obj = {}

    @overload
    def resolver(ref: BlobRef) -> FileRef: ...
    @overload
    def resolver(ref: Ref) -> int | str: ...

    def resolver(ref: Ref) -> FileRef | int | str:
        # Try to find the object in the pool of resources currently being loaded
        if str(ref.key) in key_to_obj:
            return key_to_obj[str(ref.key)].pk

        # If it's not there, then it's a reference to a resource that has
        # already been loaded
        if obj_id := Resource.objects.get(key=str(ref.key)).target_object_id:
            return obj_id

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

            Resource.objects.bulk_update(
                resources_to_update,
                [
                    "target_object_id",
                    "status",
                    "loaded_at",
                    "last_error",
                ],
            )
