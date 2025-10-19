from datetime import date

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from freezegun import freeze_time
from wagtail.models import Site

from isekai.contrib.wagtail.loaders import PageLoader
from isekai.contrib.wagtail.transformers import DocumentTransformer, ImageTransformer
from isekai.pipelines import Pipeline
from isekai.types import BlobRef, BlobResource, InMemoryFileProxy, Key, ResourceRef
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
    def test_page_loader_creates_parent_child_pages(self):
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
                    ResourceRef(Key.from_string(report_index_resource.key))
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
        assert report_index_resource.target_object_id == str(created_report_index.pk)
        assert report_page_resource.target_object_id == str(created_report_page.pk)
        assert report_index_resource.loaded_at == now
        assert report_page_resource.loaded_at == now

    def test_page_loader_creates_complex_page_hierarchy(self):
        """Test PageLoader with multiple depths, siblings, and complex hierarchy."""

        report_index_ct = ContentType.objects.get_for_model(ReportIndexPage)
        report_page_ct = ContentType.objects.get_for_model(ReportPage)

        site_root = Site.objects.get(is_default_site=True).root_page

        # Level 1: Top-level sections (siblings under site root)
        reports_section = ConcreteResource.objects.create(
            key="url:https://example.com/reports",
            target_content_type=report_index_ct,
            target_spec={
                "title": "Reports Section",
                "intro": "<p>All company reports</p>",
                "slug": "reports",
                "__wagtail_parent_page": site_root.pk,
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        news_section = ConcreteResource.objects.create(
            key="url:https://example.com/news",
            target_content_type=report_index_ct,
            target_spec={
                "title": "News Section",
                "intro": "<p>Company news and updates</p>",
                "slug": "news",
                "__wagtail_parent_page": site_root.pk,
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # Level 2: Sub-sections under Reports (siblings)
        annual_reports = ConcreteResource.objects.create(
            key="url:https://example.com/reports/annual",
            target_content_type=report_index_ct,
            target_spec={
                "title": "Annual Reports",
                "intro": "<p>Yearly financial reports</p>",
                "slug": "annual",
                "__wagtail_parent_page": str(
                    ResourceRef(Key.from_string(reports_section.key))
                ),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        quarterly_reports = ConcreteResource.objects.create(
            key="url:https://example.com/reports/quarterly",
            target_content_type=report_index_ct,
            target_spec={
                "title": "Quarterly Reports",
                "intro": "<p>Quarterly business updates</p>",
                "slug": "quarterly",
                "__wagtail_parent_page": str(
                    ResourceRef(Key.from_string(reports_section.key))
                ),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # Level 2: Pages under News (siblings)
        press_releases = ConcreteResource.objects.create(
            key="url:https://example.com/news/press",
            target_content_type=report_page_ct,
            target_spec={
                "title": "Press Releases",
                "intro": "<p>Official company announcements</p>",
                "body": "<p>Latest press releases and media coverage</p>",
                "date": "2023-01-15",
                "slug": "press-releases",
                "__wagtail_parent_page": str(
                    ResourceRef(Key.from_string(news_section.key))
                ),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        company_blog = ConcreteResource.objects.create(
            key="url:https://example.com/news/blog",
            target_content_type=report_page_ct,
            target_spec={
                "title": "Company Blog",
                "intro": "<p>Insights from our team</p>",
                "body": "<p>Regular updates and insights from our company</p>",
                "date": "2023-02-01",
                "slug": "company-blog",
                "__wagtail_parent_page": str(
                    ResourceRef(Key.from_string(news_section.key))
                ),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # Level 3: Individual reports under Annual Reports (siblings)
        annual_2023 = ConcreteResource.objects.create(
            key="url:https://example.com/reports/annual/2023",
            target_content_type=report_page_ct,
            target_spec={
                "title": "Annual Report 2023",
                "intro": "<p>Financial performance for 2023</p>",
                "body": "<p>Detailed financial analysis and company performance for fiscal year 2023</p>",
                "date": "2023-12-31",
                "slug": "annual-report-2023",
                "__wagtail_parent_page": str(
                    ResourceRef(Key.from_string(annual_reports.key))
                ),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        annual_2022 = ConcreteResource.objects.create(
            key="url:https://example.com/reports/annual/2022",
            target_content_type=report_page_ct,
            target_spec={
                "title": "Annual Report 2022",
                "intro": "<p>Financial performance for 2022</p>",
                "body": "<p>Comprehensive review of company achievements in fiscal year 2022</p>",
                "date": "2022-12-31",
                "slug": "annual-report-2022",
                "__wagtail_parent_page": str(
                    ResourceRef(Key.from_string(annual_reports.key))
                ),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # Level 3: Individual reports under Quarterly Reports (siblings)
        q4_2023 = ConcreteResource.objects.create(
            key="url:https://example.com/reports/quarterly/q4-2023",
            target_content_type=report_page_ct,
            target_spec={
                "title": "Q4 2023 Report",
                "intro": "<p>Fourth quarter results</p>",
                "body": "<p>Q4 2023 quarterly business performance and highlights</p>",
                "date": "2023-12-31",
                "slug": "q4-2023-report",
                "__wagtail_parent_page": str(
                    ResourceRef(Key.from_string(quarterly_reports.key))
                ),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        q3_2023 = ConcreteResource.objects.create(
            key="url:https://example.com/reports/quarterly/q3-2023",
            target_content_type=report_page_ct,
            target_spec={
                "title": "Q3 2023 Report",
                "intro": "<p>Third quarter results</p>",
                "body": "<p>Q3 2023 quarterly performance analysis and market outlook</p>",
                "date": "2023-09-30",
                "slug": "q3-2023-report",
                "__wagtail_parent_page": str(
                    ResourceRef(Key.from_string(quarterly_reports.key))
                ),
            },
            status=ConcreteResource.Status.TRANSFORMED,
        )

        # Set up dependency relationships (children depend on parents)
        annual_reports.dependencies.add(reports_section)
        quarterly_reports.dependencies.add(reports_section)
        press_releases.dependencies.add(news_section)
        company_blog.dependencies.add(news_section)
        annual_2023.dependencies.add(annual_reports)
        annual_2022.dependencies.add(annual_reports)
        q4_2023.dependencies.add(quarterly_reports)
        q3_2023.dependencies.add(quarterly_reports)

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

        # Verify all pages were created
        assert ReportIndexPage.objects.filter(title="Reports Section").exists()
        assert ReportIndexPage.objects.filter(title="News Section").exists()
        assert ReportIndexPage.objects.filter(title="Annual Reports").exists()
        assert ReportIndexPage.objects.filter(title="Quarterly Reports").exists()
        assert ReportPage.objects.filter(title="Press Releases").exists()
        assert ReportPage.objects.filter(title="Company Blog").exists()
        assert ReportPage.objects.filter(title="Annual Report 2023").exists()
        assert ReportPage.objects.filter(title="Annual Report 2022").exists()
        assert ReportPage.objects.filter(title="Q4 2023 Report").exists()
        assert ReportPage.objects.filter(title="Q3 2023 Report").exists()

        # Get created pages for relationship verification
        reports_section_page = ReportIndexPage.objects.get(title="Reports Section")
        news_section_page = ReportIndexPage.objects.get(title="News Section")
        annual_reports_page = ReportIndexPage.objects.get(title="Annual Reports")
        quarterly_reports_page = ReportIndexPage.objects.get(title="Quarterly Reports")
        press_releases_page = ReportPage.objects.get(title="Press Releases")
        company_blog_page = ReportPage.objects.get(title="Company Blog")
        annual_2023_page = ReportPage.objects.get(title="Annual Report 2023")
        annual_2022_page = ReportPage.objects.get(title="Annual Report 2022")
        q4_2023_page = ReportPage.objects.get(title="Q4 2023 Report")
        q3_2023_page = ReportPage.objects.get(title="Q3 2023 Report")

        # Verify Level 1: Top-level sections are children of site root
        assert reports_section_page.get_parent() == site_root
        assert news_section_page.get_parent() == site_root

        # Verify Level 2: Sub-sections have correct parents
        assert annual_reports_page.get_parent().specific == reports_section_page
        assert quarterly_reports_page.get_parent().specific == reports_section_page
        assert press_releases_page.get_parent().specific == news_section_page
        assert company_blog_page.get_parent().specific == news_section_page

        # Verify Level 3: Individual reports have correct parents
        assert annual_2023_page.get_parent().specific == annual_reports_page
        assert annual_2022_page.get_parent().specific == annual_reports_page
        assert q4_2023_page.get_parent().specific == quarterly_reports_page
        assert q3_2023_page.get_parent().specific == quarterly_reports_page

        # Verify sibling relationships at Level 1
        # Refresh site_root to get the latest children
        site_root.refresh_from_db()
        level1_children = site_root.get_children().specific()
        level1_titles = {page.title for page in level1_children}
        assert "Reports Section" in level1_titles
        assert "News Section" in level1_titles

        # Verify sibling relationships at Level 2 under Reports
        reports_children = reports_section_page.get_children().specific()
        reports_children_titles = {page.title for page in reports_children}
        assert reports_children_titles == {"Annual Reports", "Quarterly Reports"}

        # Verify sibling relationships at Level 2 under News
        news_children = news_section_page.get_children().specific()
        news_children_titles = {page.title for page in news_children}
        assert news_children_titles == {"Press Releases", "Company Blog"}

        # Verify sibling relationships at Level 3 under Annual Reports
        annual_children = annual_reports_page.get_children().specific()
        annual_children_titles = {page.title for page in annual_children}
        assert annual_children_titles == {"Annual Report 2023", "Annual Report 2022"}

        # Verify sibling relationships at Level 3 under Quarterly Reports
        quarterly_children = quarterly_reports_page.get_children().specific()
        quarterly_children_titles = {page.title for page in quarterly_children}
        assert quarterly_children_titles == {"Q4 2023 Report", "Q3 2023 Report"}

        # Verify depths are correct (Wagtail manages this automatically)
        assert reports_section_page.depth == site_root.depth + 1
        assert annual_reports_page.depth == reports_section_page.depth + 1
        assert annual_2023_page.depth == annual_reports_page.depth + 1

        # Verify all resources are marked as loaded
        all_resources = [
            reports_section,
            news_section,
            annual_reports,
            quarterly_reports,
            press_releases,
            company_blog,
            annual_2023,
            annual_2022,
            q4_2023,
            q3_2023,
        ]

        for resource in all_resources:
            resource.refresh_from_db()
            assert resource.status == ConcreteResource.Status.LOADED
            assert resource.loaded_at == now
            assert resource.target_object_id is not None
