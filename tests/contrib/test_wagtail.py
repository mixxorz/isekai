from isekai.contrib.wagtail import ImageTransformer
from isekai.types import BlobRef, BlobResource, InMemoryFileProxy, Key


class TestWagtailImageTransformer:
    def test_transform_image(self):
        transformer = ImageTransformer()

        key = Key(type="url", value="https://example.com/image.png")

        # Create a small PNG image (1x1 red pixel)
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x00"
            b"\x00\x00\x03\x00\x01\x00\x00\x00\x00\x18\xdd\x8d\xb4\x1c\x00\x00"
            b"\x00\x00IEND\xaeB`\x82"
        )

        resource = BlobResource(
            mime_type="image/png",
            filename="image.png",
            file_ref=InMemoryFileProxy(content=png_data),
            metadata={"alt_text": "A red pixel"},
        )

        spec = transformer.transform(key, resource)

        assert spec
        assert spec.content_type == "wagtailimages.Image"
        assert spec.attributes == {
            "title": "image.png",
            "file": BlobRef(key),
            "description": "A red pixel",
        }

    def test_disallowed_mime_types(self):
        transformer = ImageTransformer()

        key = Key(type="url", value="https://example.com/image.txt")

        resource = BlobResource(
            mime_type="text/plain",
            filename="image.txt",
            file_ref=InMemoryFileProxy(content=b"Not an image"),
            metadata={},
        )

        spec = transformer.transform(key, resource)

        assert spec is None
