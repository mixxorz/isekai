from isekai.transformers import BaseTransformer
from isekai.types import BlobRef, BlobResource, Key, Spec


class ImageTransformer(BaseTransformer):
    allowed_image_mime_types = [
        "image/avif",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/svg+xml",
    ]

    def __init__(self, allowed_mime_types=None):
        self.allowed_image_mime_types = allowed_mime_types or getattr(
            self.__class__, "allowed_image_mime_types", None
        )

    def transform(self, key: Key, resource: BlobResource) -> Spec | None:
        if resource.mime_type != "image/png":
            return None

        # Create a Wagtail Image spec
        return Spec(
            content_type="wagtail.Image",
            attributes={
                "title": resource.filename,
                "file": BlobRef(key),
                "description": resource.metadata.get("alt_text", ""),
            },
        )
