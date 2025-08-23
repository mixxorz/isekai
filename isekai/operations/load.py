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
        status=Resource.Status.TRANSFORMED
    ).prefetch_related(Prefetch("dependencies", queryset=Resource.objects.only("key")))

    # Calculate build order
    key_to_resource = {resource.key: resource for resource in resources}
    nodes = key_to_resource.keys()
    edges = [
        (resource.key, dep.key)
        for resource in resources
        for dep in resource.dependencies.all()
    ]

    graph = resolve_build_order(nodes, edges)

    # Load the objects
    key_to_obj = {}

    @overload
    def resolver(ref: BlobRef) -> FileRef: ...
    @overload
    def resolver(ref: Ref) -> int | str: ...

    def resolver(ref: Ref) -> FileRef | int | str:
        if str(ref.key) in key_to_obj:
            return key_to_obj[str(ref.key)].pk
        # If the framework is working correctly, we should never hit this case.
        raise ValueError(f"Unable to resolve reference: {ref}")

    for node in graph:
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
