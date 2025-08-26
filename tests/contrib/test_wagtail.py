from datetime import date

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from freezegun import freeze_time
from wagtail.models import Site

from isekai.contrib.wagtail.loaders import PageLoader
from isekai.contrib.wagtail.transformers import DocumentTransformer, ImageTransformer
from isekai.pipelines import Pipeline
from isekai.types import BlobRef, BlobResource, InMemoryFileProxy, Key, Ref
from tests.testapp.models import ConcreteResource, ReportIndexPage, ReportPage


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


@pytest.mark.django_db
@pytest.mark.database_backend
class TestWagtailPageLoader:
    def test_page_loader_creates_parent_child_pages_from_transformed_resources(self):
        """Test that PageLoader creates Wagtail pages"""

        report_index_ct = ContentType.objects.get_for_model(ReportIndexPage)
        report_page_ct = ContentType.objects.get_for_model(ReportPage)

        site_root = Site.objects.get(is_default_site=True).root_page

        report_index_resource = ConcreteResource.objects.create(
            key="url:https://example.com/reports",
            mime_type="application/json",
            data_type="text",
            text_data="unused",
            metadata={},
            target_content_type=report_index_ct,
            target_spec={
                "title": "Reports",
                "intro": "<p>This is the reports index page</p>",
                "slug": "reports",
                "__wagtail_parent_page": site_root.pk,
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        report_page_resource = ConcreteResource.objects.create(
            key="url:https://example.com/reports/annual-2023",
            mime_type="application/json",
            data_type="text",
            text_data="unused",
            metadata={},
            target_content_type=report_page_ct,
            target_spec={
                "title": "Annual Report 2023",
                "intro": "<p>Introduction to the annual report</p>",
                "body": "<p>This is the body of the annual report</p>",
                "date": "2023-12-31",
                "slug": "annual-report-2023",
                "__wagtail_parent_page": str(
                    Ref(Key.from_string(report_index_resource.key))
                ),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        report_page_resource.dependencies.add(report_index_resource)

        # Run the pipeline load operation
        now = timezone.now()
        with freeze_time(now):
            pipeline = Pipeline(
                seeders=[],
                extractors=[],
                miners=[],
                transformers=[],
                loaders=[PageLoader()],
            )
            result = pipeline.load()

        # Verify the operation was successful
        assert result.result == "success"

        # Verify the pages were created correctly
        assert ReportIndexPage.objects.filter(title="Reports").exists()
        assert ReportPage.objects.filter(title="Annual Report 2023").exists()

        # Verify parent-child relationship
        created_report_index = ReportIndexPage.objects.get(title="Reports")
        created_report_page = ReportPage.objects.get(title="Annual Report 2023")

        assert created_report_page.get_parent().specific == created_report_index
        assert (
            created_report_index.get_children()
            .filter(pk=created_report_page.pk)
            .exists()
        )

        # Verify page content
        assert created_report_index.intro == "<p>This is the reports index page</p>"
        assert created_report_page.intro == "<p>Introduction to the annual report</p>"
        assert (
            created_report_page.body == "<p>This is the body of the annual report</p>"
        )
        assert created_report_page.date == date(2023, 12, 31)

        # Verify URLs
        assert created_report_index.slug == "reports"
        assert created_report_page.slug == "annual-report-2023"

        # Verify resources are marked as loaded
        report_index_resource.refresh_from_db()
        report_page_resource.refresh_from_db()

        assert report_index_resource.status == ConcreteResource.Status.LOADED
        assert report_page_resource.status == ConcreteResource.Status.LOADED
        assert report_index_resource.target_object_id == created_report_index.pk
        assert report_page_resource.target_object_id == created_report_page.pk
        assert report_index_resource.loaded_at == now
        assert report_page_resource.loaded_at == now
