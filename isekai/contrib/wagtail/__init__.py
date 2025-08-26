from wagtail.images import get_image_model_string

from isekai.transformers import BaseTransformer
from isekai.types import BlobRef, BlobResource, Key, Spec


class ImageTransformer(BaseTransformer):
    allowed_image_mime_types: list[str] = [
        "image/avif",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/svg+xml",
    ]

    def __init__(self, allowed_mime_types: list[str] | None = None):
        self.allowed_image_mime_types = allowed_mime_types or getattr(
            self.__class__, "allowed_image_mime_types", []
        )

    def transform(self, key: Key, resource: BlobResource) -> Spec | None:
        if resource.mime_type not in self.allowed_image_mime_types:
            return None

        # Create a Wagtail Image spec
        return Spec(
            content_type=get_image_model_string(),
            attributes={
                "title": resource.filename,
                "file": BlobRef(key),  # Reference itself
                "description": resource.metadata.get("alt_text", ""),
            },
        )
