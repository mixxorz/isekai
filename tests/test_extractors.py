import pytest
import responses
from django.utils import timezone
from freezegun import freeze_time

from isekai.extractors import HTTPExtractor
from isekai.operations import extract
from isekai.types import BinaryData
from tests.testapp.models import ConcreteResource


class TestHTTPExtractor:
    @pytest.mark.vcr
    def test_extract_returns_resource_data(self):
        """Test that HTTPExtractor.extract returns expected ResourceData."""
        extractor = HTTPExtractor()

        result = extractor.extract("url:https://www.jpl.nasa.gov/")

        assert result.mime_type == "text/html"
        assert result.data_type == "text"
        assert "Jet Propulsion Laboratory" in result.data

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
        result = extractor.extract("url:https://example.com/images/test-image.png")

        assert result is not None
        assert result.mime_type == "image/png"
        assert result.data_type == "blob"
        assert isinstance(result.data, BinaryData)
        assert result.data.filename == "test-image.png"
        assert result.data.data == png_data

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
        result = extractor.extract("url:https://example.com/download?id=123")

        assert result is not None
        assert result.mime_type == "application/pdf"
        assert result.data_type == "blob"
        assert isinstance(result.data, BinaryData)
        assert result.data.filename == "report.pdf"
        assert result.data.data == pdf_data

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
        result = extractor.extract("url:https://example.com/api/export")

        assert result is not None
        assert result.mime_type == "application/zip"
        assert result.data_type == "blob"
        assert isinstance(result.data, BinaryData)
        assert result.data.filename == "export.zip"
        assert result.data.data == zip_data

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
        result = extractor.extract("url:https://example.com/downloads/my-project-v2")

        assert result is not None
        assert result.mime_type == "application/zip"
        assert result.data_type == "blob"
        assert isinstance(result.data, BinaryData)
        assert result.data.filename == "my-project-v2.zip"
        assert result.data.data == zip_data


@pytest.mark.django_db
@pytest.mark.vcr
class TestExtract:
    def test_extract_loads_data_to_resource(self):
        ConcreteResource.objects.create(key="url:https://www.jpl.nasa.gov/")

        now = timezone.now()
        with freeze_time(now):
            extract()

        resource = ConcreteResource.objects.get()

        assert resource.key == "url:https://www.jpl.nasa.gov/"
        assert resource.mime_type == "text/html"
        assert resource.data_type == "text"
        assert resource.data is not None
        assert "Jet Propulsion Laboratory" in resource.data

        assert resource.status == ConcreteResource.Status.EXTRACTED
        assert resource.extracted_at == now

    def test_extract_cannot_proceed_if_no_data(self):
        ConcreteResource.objects.create(key="gen:foo")

        extract()

        resource = ConcreteResource.objects.get()

        assert resource.status == ConcreteResource.Status.SEEDED
        assert resource.extracted_at is None
        assert resource.mime_type == ""
        assert resource.data_type == ""
        assert resource.text_data == ""
        assert not resource.blob_data

        assert (
            resource.last_error
            == "TransitionError: Cannot transition to EXTRACTED without data"
        )
