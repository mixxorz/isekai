from typing import overload

from isekai.types import BlobRef, FileRef, Key, Ref, Spec
from isekai.utils import get_resource_model

Resource = get_resource_model()


def load():
    """Loads objects from resources"""

    loaders = Resource.loaders

    resources = Resource.objects.filter(status=Resource.Status.TRANSFORMED)

    key_to_obj = {}

    @overload
    def resolver(ref: BlobRef) -> FileRef: ...
    @overload
    def resolver(ref: Ref) -> int | str: ...

    def resolver(ref: Ref) -> FileRef | int | str:
        if str(ref.key) in key_to_obj:
            return key_to_obj[str(ref.key)].pk
        raise AssertionError(f"Unexpected ref: {ref}")

    for resource in resources:
        ct = resource.target_content_type
        assert ct
        model_class = ct.model_class()
        assert model_class

        key = Key.from_string(resource.key)
        spec = Spec.from_dict(
            {
                "content_type": f"{model_class._meta.label}",
                "attributes": resource.target_spec,
            }
        )

        obj = None
        for loader in loaders:
            if obj := loader.load([(key, spec)], resolver):
                break

        key_to_obj[resource.key] = obj[0] if obj else None
