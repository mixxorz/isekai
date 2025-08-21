from isekai.types import BlobResource, Key, Spec, TextResource


class BaseTransformer:
    def transform(self, key: Key, resource: TextResource | BlobResource) -> Spec | None:
        return None
