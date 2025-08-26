from isekai.contrib.wagtail.transformers import DocumentTransformer, ImageTransformer
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


class TestWagtailDocumentTransformer:
    def test_transform_document(self):
        transformer = DocumentTransformer()

        key = Key(type="url", value="https://example.com/document.pdf")

        # Create PDF document content
        pdf_data = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"

        resource = BlobResource(
            mime_type="application/pdf",
            filename="document.pdf",
            file_ref=InMemoryFileProxy(content=pdf_data),
            metadata={},
        )

        spec = transformer.transform(key, resource)

        assert spec
        assert spec.content_type == "wagtaildocs.Document"
        assert spec.attributes == {
            "title": "document.pdf",
            "file": BlobRef(key),
        }

    def test_transform_word_document(self):
        transformer = DocumentTransformer()

        key = Key(type="file", value="/path/to/document.docx")

        resource = BlobResource(
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="report.docx",
            file_ref=InMemoryFileProxy(content=b"Word document content"),
            metadata={},
        )

        spec = transformer.transform(key, resource)

        assert spec
        assert spec.content_type == "wagtaildocs.Document"
        assert spec.attributes == {
            "title": "report.docx",
            "file": BlobRef(key),
        }

    def test_disallowed_mime_types(self):
        transformer = DocumentTransformer()

        key = Key(type="url", value="https://example.com/image.png")

        resource = BlobResource(
            mime_type="image/png",
            filename="image.png",
            file_ref=InMemoryFileProxy(content=b"PNG image data"),
            metadata={},
        )

        spec = transformer.transform(key, resource)

        assert spec is None

    def test_custom_allowed_mime_types(self):
        # Test with custom allowed mime types
        transformer = DocumentTransformer(allowed_mime_types=["text/plain"])

        key = Key(type="file", value="/path/to/text.txt")

        resource = BlobResource(
            mime_type="text/plain",
            filename="text.txt",
            file_ref=InMemoryFileProxy(content=b"Plain text content"),
            metadata={},
        )

        spec = transformer.transform(key, resource)

        assert spec
        assert spec.content_type == "wagtaildocs.Document"

        # Test that PDF is now not allowed
        pdf_resource = BlobResource(
            mime_type="application/pdf",
            filename="document.pdf",
            file_ref=InMemoryFileProxy(content=b"%PDF content"),
            metadata={},
        )

        spec = transformer.transform(key, pdf_resource)
        assert spec is None
