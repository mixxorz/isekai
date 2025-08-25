import pytest
import responses
from django.utils import timezone
from freezegun import freeze_time

from isekai.extractors import HTTPExtractor
from isekai.pipelines import get_django_pipeline
from isekai.types import BlobResource, Key, TextResource
from tests.testapp.models import ConcreteResource


class TestHTTPExtractor:
    @pytest.mark.vcr
    def test_extract_returns_resource_data(self):
        """Test that HTTPExtractor.extract returns expected TextResource."""
        extractor = HTTPExtractor()
        key = Key(type="url", value="https://www.jpl.nasa.gov/")

        result = extractor.extract(key)

        assert isinstance(result, TextResource)
        assert result.mime_type == "text/html"
        assert "Jet Propulsion Laboratory" in result.text

    @responses.activate
    def test_extract_binary_content_with_filename_inference(self):
        """Test binary content extraction with filename inference."""
        # Create a small PNG image (1x1 red pixel)
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x00"
            b"\x00\x00\x03\x00\x01\x00\x00\x00\x00\x18\xdd\x8d\xb4\x1c\x00\x00"
            b"\x00\x00IEND\xaeB`\x82"
        )

        responses.add(
            responses.GET,
            "https://example.com/images/test-image.png",
            body=png_data,
            headers={"Content-Type": "image/png"},
            status=200,
        )

        extractor = HTTPExtractor()
        key = Key(type="url", value="https://example.com/images/test-image.png")
        result = extractor.extract(key)

        assert result is not None
        assert isinstance(result, BlobResource)
        assert result.mime_type == "image/png"
        assert result.filename == "test-image.png"
        # Read the temporary file to verify content
        with result.file_ref.open() as f:
            assert f.read() == png_data

    @responses.activate
    def test_extract_binary_with_content_disposition_filename(self):
        """Test filename extraction from Content-Disposition header."""
        pdf_data = b"%PDF-1.4 fake pdf content"

        responses.add(
            responses.GET,
            "https://example.com/download?id=123",
            body=pdf_data,
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": 'attachment; filename="report.pdf"',
            },
            status=200,
        )

        extractor = HTTPExtractor()
        key = Key(type="url", value="https://example.com/download?id=123")
        result = extractor.extract(key)

        assert result is not None
        assert isinstance(result, BlobResource)
        assert result.mime_type == "application/pdf"
        assert result.filename == "report.pdf"
        # Read the temporary file to verify content
        with result.file_ref.open() as f:
            assert f.read() == pdf_data

    @responses.activate
    def test_extract_stores_response_headers_in_metadata(self):
        """Test that HTTPExtractor stores response headers in metadata."""
        test_content = "Test content"
        custom_headers = {
            "Content-Type": "text/plain",
            "X-Custom-Header": "custom-value",
            "Cache-Control": "max-age=3600",
            "Last-Modified": "Wed, 21 Oct 2023 07:28:00 GMT",
        }

        responses.add(
            responses.GET,
            "https://example.com/test.txt",
            body=test_content,
            headers=custom_headers,
            status=200,
        )

        extractor = HTTPExtractor()
        key = Key(type="url", value="https://example.com/test.txt")
        result = extractor.extract(key)

        assert result is not None
        assert isinstance(result, TextResource)
        assert result.mime_type == "text/plain"
        assert result.text == test_content

        # Check that metadata contains response headers
        assert "response_headers" in result.metadata

        response_headers = result.metadata["response_headers"]
        assert response_headers["Content-Type"] == "text/plain"
        assert response_headers["X-Custom-Header"] == "custom-value"
        assert response_headers["Cache-Control"] == "max-age=3600"
        assert response_headers["Last-Modified"] == "Wed, 21 Oct 2023 07:28:00 GMT"

    @responses.activate
    def test_extract_binary_fallback_to_mime_type_extension(self):
        """Test filename generation from MIME type when no other source available."""
        zip_data = b"PK\x03\x04fake zip content"

        responses.add(
            responses.GET,
            "https://example.com/api/export",
            body=zip_data,
            headers={"Content-Type": "application/zip"},
            status=200,
        )

        extractor = HTTPExtractor()
        key = Key(type="url", value="https://example.com/api/export")
        result = extractor.extract(key)

        assert result is not None
        assert isinstance(result, BlobResource)
        assert result.mime_type == "application/zip"
        assert result.filename == "export.zip"
        # Read the temporary file to verify content
        with result.file_ref.open() as f:
            assert f.read() == zip_data

    @responses.activate
    def test_extract_binary_uses_path_segment_as_base_filename(self):
        """Test that the last path segment is used as base filename when no extension in URL."""
        zip_data = b"PK\x03\x04fake zip content"

        responses.add(
            responses.GET,
            "https://example.com/downloads/my-project-v2",
            body=zip_data,
            headers={"Content-Type": "application/zip"},
            status=200,
        )

        extractor = HTTPExtractor()
        key = Key(type="url", value="https://example.com/downloads/my-project-v2")
        result = extractor.extract(key)

        assert result is not None
        assert isinstance(result, BlobResource)
        assert result.mime_type == "application/zip"
        assert result.filename == "my-project-v2.zip"
        # Read the temporary file to verify content
        with result.file_ref.open() as f:
            assert f.read() == zip_data


@pytest.mark.django_db
@pytest.mark.vcr
class TestExtract:
    def test_extract_loads_text_data_to_resource(self):
        ConcreteResource.objects.create(key="url:https://www.jpl.nasa.gov/")

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.extract()

        resource = ConcreteResource.objects.get()

        assert resource.key == "url:https://www.jpl.nasa.gov/"
        assert resource.mime_type == "text/html"
        assert resource.data_type == "text"
        assert resource.data is not None
        assert "Jet Propulsion Laboratory" in resource.data

        assert resource.status == ConcreteResource.Status.EXTRACTED
        assert resource.extracted_at == now

        assert resource.metadata
        assert "response_headers" in resource.metadata
        assert "Content-Type" in resource.metadata["response_headers"]

    @responses.activate
    def test_extract_loads_blob_data_to_resource(self):
        """Test that extract() properly handles binary data extraction and saves to FileField."""
        # Create a small PNG image (1x1 red pixel)
        png_data = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x00"
            b"\x00\x00\x03\x00\x01\x00\x00\x00\x00\x18\xdd\x8d\xb4\x1c\x00\x00"
            b"\x00\x00IEND\xaeB`\x82"
        )

        responses.add(
            responses.GET,
            "https://example.com/test-image.png",
            body=png_data,
            headers={"Content-Type": "image/png"},
            status=200,
        )

        ConcreteResource.objects.create(key="url:https://example.com/test-image.png")

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.extract()

        resource = ConcreteResource.objects.get()

        assert resource.key == "url:https://example.com/test-image.png"
        assert resource.mime_type == "image/png"
        assert resource.data_type == "blob"
        assert "test-image" in resource.blob_data.name
        assert resource.blob_data.name.endswith(".png")
        assert resource.blob_data.read() == png_data
        assert resource.text_data == ""

        assert resource.status == ConcreteResource.Status.EXTRACTED
        assert resource.extracted_at == now

    def test_extract_handles_extractor_chaining(self):
        # Create a resource that will be processed by multiple extractors
        ConcreteResource.objects.create(key="foo:bar")

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.extract()

        resource = ConcreteResource.objects.get()

        assert resource.key == "foo:bar"
        assert resource.mime_type == "foo/bar"
        assert resource.data_type == "text"
        assert resource.data == "foo bar data"

        assert resource.status == ConcreteResource.Status.EXTRACTED
        assert resource.extracted_at == now

    @responses.activate
    def test_extract_merges_metadata_with_existing_resource_metadata(self):
        """Test that extract operation merges metadata with existing resource metadata."""
        test_content = "<html><body>Test</body></html>"

        responses.add(
            responses.GET,
            "https://example.com/merge-test.html",
            body=test_content,
            headers={"Content-Type": "text/html", "X-Source": "test"},
            status=200,
        )

        # Create a resource with existing metadata
        resource = ConcreteResource.objects.create(
            key="url:https://example.com/merge-test.html",
            metadata={
                "custom_field": "existing_value",
                "another_field": {"nested": "data"},
            },
        )
        assert resource.status == ConcreteResource.Status.SEEDED

        # Run extract operation
        pipeline = get_django_pipeline()
        pipeline.extract()

        # Reload resource from database
        resource.refresh_from_db()

        # Verify resource was extracted successfully
        assert resource.status == ConcreteResource.Status.EXTRACTED

        # Verify metadata was merged (not replaced)
        assert resource.metadata
        assert "custom_field" in resource.metadata
        assert resource.metadata["custom_field"] == "existing_value"
        assert "another_field" in resource.metadata
        assert resource.metadata["another_field"] == {"nested": "data"}

        # Verify new response_headers were added
        assert "response_headers" in resource.metadata
        response_headers = resource.metadata["response_headers"]
        assert response_headers["Content-Type"] == "text/html"
        assert response_headers["X-Source"] == "test"

    @responses.activate
    def test_extract_is_idempotent(self):
        """Test that running extract multiple times doesn't re-extract already extracted resources."""
        test_content = "<html><body>Test Content</body></html>"

        responses.add(
            responses.GET,
            "https://example.com/test-page.html",
            body=test_content,
            headers={"Content-Type": "text/html"},
            status=200,
        )

        # Create a seeded resource
        resource = ConcreteResource.objects.create(
            key="url:https://example.com/test-page.html"
        )
        assert resource.status == ConcreteResource.Status.SEEDED

        # First extract operation
        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.extract()

        # Verify resource was extracted
        resource.refresh_from_db()
        assert resource.status == ConcreteResource.Status.EXTRACTED
        assert resource.extracted_at == now
        assert resource.text_data == test_content

        # Clear the responses to ensure second extract doesn't make HTTP requests
        responses.reset()

        # Second extract operation - should not process already extracted resources
        later = now + timezone.timedelta(hours=1)
        with freeze_time(later):
            pipeline = get_django_pipeline()
            pipeline.extract()  # Should be no-op

        # Verify resource state unchanged
        resource.refresh_from_db()
        assert resource.status == ConcreteResource.Status.EXTRACTED
        assert resource.extracted_at == now  # Timestamp should not change
        assert resource.text_data == test_content  # Data should remain the same
