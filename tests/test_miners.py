import pytest
from django.utils import timezone
from freezegun import freeze_time

from isekai.miners import HTMLDocumentMiner, HTMLImageMiner, HTMLPageMiner
from isekai.pipelines import get_django_pipeline
from isekai.types import Key, TextResource
from tests.testapp.models import ConcreteResource


class TestHTMLImageMiner:
    def test_class_attrs(self):
        class Miner(HTMLImageMiner):
            allowed_domains = ["example.com", "cdn.example.com"]

        miner = Miner()

        assert miner.allowed_domains == ["example.com", "cdn.example.com"]

    def test_miner_finds_images(self):
        miner = HTMLImageMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com")
        text_data = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Image Test</title>
</head>
<body>
  <h1>Image test page</h1>

  <!-- Simple <img> -->
  <img src="images/cat.jpg" alt="Cat">

  <!-- <img> with srcset -->
  <img
    src="images/dog-small.jpg"
    srcset="images/dog-small.jpg 480w, images/dog-large.jpg 1024w"
    alt="Dog"
  >

  <!-- <picture> element with multiple <source> -->
  <picture>
    <source srcset="images/bird-small.jpg" media="(max-width: 600px)">
    <source srcset="images/bird-large.jpg" media="(min-width: 601px)">
    <img src="images/bird-fallback.jpg" alt="Bird">
  </picture>

  <!-- Another <picture> with absolute URLs -->
  <picture>
    <source srcset="https://example.com/images/flower-hd.jpg" media="(min-width: 800px)">
    <img src="https://example.com/images/flower-default.jpg" alt="Flower">
  </picture>
</body>
</html>
        """

        # Create TextResource object
        resource = TextResource(mime_type="text/html", text=text_data, metadata={})

        mined_resources = miner.mine(key, resource)

        # Check that we found all expected URLs (order doesn't matter)
        expected_keys = [
            Key(type="url", value="https://example.com/images/cat.jpg"),
            Key(type="url", value="https://example.com/images/dog-small.jpg"),
            Key(type="url", value="https://example.com/images/dog-small.jpg"),
            Key(type="url", value="https://example.com/images/dog-large.jpg"),
            Key(type="url", value="https://example.com/images/bird-small.jpg"),
            Key(type="url", value="https://example.com/images/bird-large.jpg"),
            Key(type="url", value="https://example.com/images/bird-fallback.jpg"),
            Key(type="url", value="https://example.com/images/flower-hd.jpg"),
            Key(type="url", value="https://example.com/images/flower-default.jpg"),
        ]

        assert len(mined_resources) == len(expected_keys)
        mined_keys = [mr.key for mr in mined_resources]
        assert sorted(mined_keys, key=str) == sorted(expected_keys, key=str)

        # Check that alt text is saved in metadata
        mined_by_url = {str(mr.key): mr for mr in mined_resources}

        expected_alt_texts = {
            "url:https://example.com/images/cat.jpg": "Cat",
            "url:https://example.com/images/dog-small.jpg": "Dog",
            "url:https://example.com/images/bird-fallback.jpg": "Bird",
            "url:https://example.com/images/flower-default.jpg": "Flower",
        }

        for url, expected_alt in expected_alt_texts.items():
            resource = mined_by_url[url]
            assert resource.metadata.get("alt_text") == expected_alt, (
                f"Alt text mismatch for {url}"
            )

    def test_miner_uses_host_header_from_metadata(self):
        """Test that HTMLImageMiner uses Host header from metadata for base URL."""
        miner = HTMLImageMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com")
        text_data = """
        <html>
        <body>
          <img src="/images/logo.png" alt="Logo">
          <img src="assets/icon.svg" alt="Icon">
        </body>
        </html>
        """

        # Create TextResource with Host header in metadata
        resource = TextResource(
            mime_type="text/html",
            text=text_data,
            metadata={
                "response_headers": {
                    "Host": "cdn.example.com",
                    "Content-Type": "text/html",
                }
            },
        )

        mined_resources = miner.mine(key, resource)

        # Should use Host header for base URL construction
        expected_keys = {
            Key(type="url", value="https://cdn.example.com/images/logo.png"),
            Key(type="url", value="https://cdn.example.com/assets/icon.svg"),
        }

        assert len(mined_resources) == 2
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_falls_back_to_url_when_no_host_header(self):
        """Test that HTMLImageMiner falls back to original URL when no Host header."""
        miner = HTMLImageMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com")
        text_data = """
        <html>
        <body>
          <img src="/images/fallback.png" alt="Fallback">
        </body>
        </html>
        """

        # Create TextResource without Host header in metadata
        resource = TextResource(
            mime_type="text/html",
            text=text_data,
            metadata={"response_headers": {"Content-Type": "text/html"}},
        )

        mined_resources = miner.mine(key, resource)

        # Should fall back to original URL from key
        expected_keys = {
            Key(type="url", value="https://example.com/images/fallback.png")
        }

        assert len(mined_resources) == 1
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_handles_non_url_keys(self):
        """Test that HTMLImageMiner handles non-URL keys properly."""
        miner = HTMLImageMiner(allowed_domains=["*"])

        # Test with a file: key
        key = Key(type="file", value="/path/to/local/file.html")
        text_data = """
        <html>
        <body>
          <img src="images/local-image.jpg" alt="Local">
          <img src="/absolute/path/image.png" alt="Absolute">
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})

        mined_resources = miner.mine(key, resource)

        # Should return relative URLs with path: prefix when no base URL is available for non-URL keys
        expected_keys = {
            Key(type="path", value="images/local-image.jpg"),
            Key(type="path", value="/absolute/path/image.png"),
        }

        assert len(mined_resources) == 2
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_handles_absolute_urls(self):
        """Test that HTMLImageMiner handles absolute URLs correctly."""
        miner = HTMLImageMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com")
        text_data = """
        <html>
        <body>
          <!-- Relative URL -->
          <img src="images/relative.jpg" alt="Relative">
          <!-- Absolute URLs with different schemes -->
          <img src="https://cdn.example.com/images/absolute.jpg" alt="Absolute HTTPS">
          <img src="http://old.example.com/images/http.jpg" alt="Absolute HTTP">
          <img src="//static.example.com/images/protocol-relative.jpg" alt="Protocol Relative">
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})

        mined_resources = miner.mine(key, resource)

        # Should preserve absolute URLs as-is and resolve relative ones
        expected_keys = {
            Key(type="url", value="https://example.com/images/relative.jpg"),
            Key(type="url", value="https://cdn.example.com/images/absolute.jpg"),
            Key(type="url", value="http://old.example.com/images/http.jpg"),
            Key(
                type="url",
                value="https://static.example.com/images/protocol-relative.jpg",
            ),  # Protocol-relative URLs get resolved
        }

        assert len(mined_resources) == 4
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_domain_allowlist(self):
        """Test that HTMLImageMiner filters URLs based on allowed_domains."""
        miner = HTMLImageMiner(allowed_domains=["example.com"])

        key = Key(type="file", value="/local/file.html")  # No base URL available
        text_data = """
        <html>
        <body>
          <img src="relative/path.jpg" alt="Relative">
          <img src="https://example.com/images/allowed.jpg" alt="Allowed">
          <img src="https://badsite.com/images/blocked.jpg" alt="Blocked">
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})

        mined_resources = miner.mine(key, resource)

        # Should return relative URLs with path: prefix and allowed domains with url: prefix
        expected_keys = {
            Key(
                type="path", value="relative/path.jpg"
            ),  # Relative URL gets path: prefix
            Key(
                type="url", value="https://example.com/images/allowed.jpg"
            ),  # Allowed domain gets url: prefix
        }

        assert len(mined_resources) == 2
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_allows_relative_urls_when_no_allowlist(self):
        """Test that relative URLs are allowed even when no allowed_domains is specified."""
        miner = HTMLImageMiner()  # No allowed_domains

        key = Key(type="file", value="/local/file.html")  # No base URL available
        text_data = """
        <html>
        <body>
          <img src="relative/path.jpg" alt="Relative">
          <img src="https://example.com/images/blocked.jpg" alt="Blocked">
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})

        mined_resources = miner.mine(key, resource)

        # Should return only relative URLs with path: prefix, absolute URLs should be blocked
        expected_keys = {Key(type="path", value="relative/path.jpg")}

        assert len(mined_resources) == 1
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys


@pytest.mark.django_db
class TestMine:
    def test_mine_creates_resources(self):
        text_data = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Image Test</title>
</head>
<body>
  <h1>Image test page</h1>

  <!-- Simple <img> -->
  <img src="images/cat.jpg" alt="Cat">

  <!-- <img> with srcset -->
  <img
    src="images/dog-small.jpg"
    srcset="images/dog-small.jpg 480w, images/dog-large.jpg 1024w"
    alt="Dog"
  >

  <!-- <picture> element with multiple <source> -->
  <picture>
    <source srcset="images/bird-small.jpg" media="(max-width: 600px)">
    <source srcset="images/bird-large.jpg" media="(min-width: 601px)">
    <img src="images/bird-fallback.jpg" alt="Bird">
  </picture>

  <!-- Another <picture> with absolute URLs -->
  <picture>
    <source srcset="https://example.com/images/flower-hd.jpg" media="(min-width: 800px)">
    <img src="https://example.com/images/flower-default.jpg" alt="Flower">
  </picture>
</body>
</html>
        """

        # Resource to mine
        original_resource = ConcreteResource.objects.create(
            key="url:https://example.com",
            data_type="text",
            mime_type="text/html",
            text_data=text_data,
            status=ConcreteResource.Status.EXTRACTED,
        )

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.mine()

        expected_resources = sorted(
            [
                "url:https://example.com/images/cat.jpg",
                "url:https://example.com/images/dog-small.jpg",
                "url:https://example.com/images/dog-large.jpg",
                "url:https://example.com/images/bird-small.jpg",
                "url:https://example.com/images/bird-large.jpg",
                "url:https://example.com/images/bird-fallback.jpg",
                "url:https://example.com/images/flower-hd.jpg",
                "url:https://example.com/images/flower-default.jpg",
            ]
        )

        resources = ConcreteResource.objects.filter(
            key__in=expected_resources
        ).order_by("key")

        # Check mined resources are created
        assert len(resources) == len(expected_resources)

        for resource, expected_key in zip(resources, expected_resources, strict=False):
            assert resource.key == expected_key
            assert resource.status == ConcreteResource.Status.SEEDED

        # Check that alt text is preserved in metadata for resources that came from img tags
        resources_by_key = {resource.key: resource for resource in resources}

        expected_alt_texts = {
            "url:https://example.com/images/cat.jpg": "Cat",
            "url:https://example.com/images/dog-small.jpg": "Dog",
            "url:https://example.com/images/bird-fallback.jpg": "Bird",
            "url:https://example.com/images/flower-default.jpg": "Flower",
        }

        for resource_key, expected_alt in expected_alt_texts.items():
            resource = resources_by_key[resource_key]
            assert resource.metadata is not None, (
                f"Metadata should not be None for {resource_key}"
            )
            assert resource.metadata.get("alt_text") == expected_alt, (
                f"Alt text mismatch for {resource_key}"
            )

        # Check original resource is updated
        original_resource.refresh_from_db()
        assert original_resource.status == ConcreteResource.Status.MINED
        assert original_resource.mined_at == now

    def test_mine_is_idempotent_with_duplicate_images(self):
        text_data_1 = """
<!DOCTYPE html>
<html lang="en">
<body>
  <img src="images/cat.jpg" alt="Cat">
  <img src="images/dog.jpg" alt="Dog">
</body>
</html>
        """

        text_data_2 = """
<!DOCTYPE html>
<html lang="en">
<body>
  <img src="images/cat.jpg" alt="Same Cat">
  <img src="images/bird.jpg" alt="Bird">
</body>
</html>
        """

        # Create two resources that contain overlapping images
        resource_1 = ConcreteResource.objects.create(
            key="url:https://example.com/page1",
            data_type="text",
            mime_type="text/html",
            text_data=text_data_1,
            status=ConcreteResource.Status.EXTRACTED,
        )

        resource_2 = ConcreteResource.objects.create(
            key="url:https://example.com/page2",
            data_type="text",
            mime_type="text/html",
            text_data=text_data_2,
            status=ConcreteResource.Status.EXTRACTED,
        )

        # Mine operation should create unique resources only
        pipeline = get_django_pipeline()
        pipeline.mine()

        # Should have: 2 HTML resources + 3 unique images (cat.jpg, dog.jpg, bird.jpg)
        total_count = ConcreteResource.objects.count()
        assert total_count == 5

        # Verify both original resources were mined
        resource_1.refresh_from_db()
        resource_2.refresh_from_db()
        assert resource_1.status == ConcreteResource.Status.MINED
        assert resource_2.status == ConcreteResource.Status.MINED

        # Verify the shared image exists only once
        cat_resources = ConcreteResource.objects.filter(
            key="url:https://example.com/images/cat.jpg"
        )
        assert cat_resources.count() == 1

        # The shared image exists only once in the database
        cat_resource = cat_resources.first()
        assert cat_resource is not None

        # Second mine operation - should not create duplicates
        pipeline = get_django_pipeline()
        pipeline.mine()
        second_count = ConcreteResource.objects.count()
        assert second_count == 5  # Same count, no new resources


class TestHTMLDocumentMiner:
    def test_miner_finds_document_links(self):
        """Test that HTMLDocumentMiner finds various document links in HTML."""
        miner = HTMLDocumentMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com")
        text_data = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Document Links Test</title>
</head>
<body>
  <h1>Document download page</h1>

  <!-- PDF documents -->
  <a href="documents/report.pdf">Annual Report (PDF)</a>
  <a href="/files/manual.pdf">User Manual</a>

  <!-- Word documents -->
  <a href="documents/proposal.docx">Project Proposal</a>
  <a href="https://example.com/files/memo.doc">Company Memo</a>

  <!-- Excel spreadsheets -->
  <a href="data/budget.xlsx">Budget Spreadsheet</a>
  <a href="/reports/sales.xls">Sales Report</a>

  <!-- PowerPoint presentations -->
  <a href="presentations/slides.pptx">Company Presentation</a>
  <a href="meeting/deck.ppt">Meeting Deck</a>

  <!-- Other document formats -->
  <a href="documents/readme.txt">ReadMe File</a>
  <a href="/archive/data.csv">CSV Data</a>
  <a href="specs/architecture.rtf">Architecture Specs</a>

  <!-- Non-document links (should be ignored) -->
  <a href="page.html">HTML Page</a>
  <a href="image.jpg">Image File</a>
  <a href="video.mp4">Video File</a>
  <a href="https://example.com">Website Link</a>
</body>
</html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        # Check that we found all expected document URLs
        expected_keys = [
            Key(type="url", value="https://example.com/documents/report.pdf"),
            Key(type="url", value="https://example.com/files/manual.pdf"),
            Key(type="url", value="https://example.com/documents/proposal.docx"),
            Key(type="url", value="https://example.com/files/memo.doc"),
            Key(type="url", value="https://example.com/data/budget.xlsx"),
            Key(type="url", value="https://example.com/reports/sales.xls"),
            Key(type="url", value="https://example.com/presentations/slides.pptx"),
            Key(type="url", value="https://example.com/meeting/deck.ppt"),
            Key(type="url", value="https://example.com/documents/readme.txt"),
            Key(type="url", value="https://example.com/archive/data.csv"),
            Key(type="url", value="https://example.com/specs/architecture.rtf"),
        ]

        assert len(mined_resources) == len(expected_keys)
        mined_keys = [mr.key for mr in mined_resources]
        assert sorted(mined_keys, key=str) == sorted(expected_keys, key=str)

        # Check that link text is saved in metadata
        mined_by_url = {str(mr.key): mr for mr in mined_resources}

        expected_link_texts = {
            "url:https://example.com/documents/report.pdf": "Annual Report (PDF)",
            "url:https://example.com/files/manual.pdf": "User Manual",
            "url:https://example.com/documents/proposal.docx": "Project Proposal",
            "url:https://example.com/files/memo.doc": "Company Memo",
        }

        for url, expected_text in expected_link_texts.items():
            resource = mined_by_url[url]
            assert resource.metadata.get("link_text") == expected_text, (
                f"Link text mismatch for {url}"
            )

    def test_miner_handles_absolute_urls(self):
        """Test that HTMLDocumentMiner handles absolute document URLs correctly."""

        miner = HTMLDocumentMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com")
        text_data = """
        <html>
        <body>
          <!-- Relative URL -->
          <a href="docs/relative.pdf">Relative PDF</a>
          <!-- Absolute URLs with different schemes -->
          <a href="https://cdn.example.com/docs/absolute.pdf">Absolute HTTPS PDF</a>
          <a href="http://old.example.com/docs/http.pdf">Absolute HTTP PDF</a>
          <a href="//static.example.com/docs/protocol-relative.docx">Protocol Relative DOCX</a>
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        # Should preserve absolute URLs as-is and resolve relative ones
        expected_keys = {
            Key(type="url", value="https://example.com/docs/relative.pdf"),
            Key(type="url", value="https://cdn.example.com/docs/absolute.pdf"),
            Key(type="url", value="http://old.example.com/docs/http.pdf"),
            Key(
                type="url",
                value="https://static.example.com/docs/protocol-relative.docx",
            ),
        }

        assert len(mined_resources) == 4
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_domain_allowlist(self):
        """Test that HTMLDocumentMiner filters URLs based on allowed_domains."""

        miner = HTMLDocumentMiner(allowed_domains=["example.com"])

        key = Key(type="file", value="/local/file.html")
        text_data = """
        <html>
        <body>
          <a href="relative/document.pdf">Relative PDF</a>
          <a href="https://example.com/docs/allowed.pdf">Allowed PDF</a>
          <a href="https://badsite.com/docs/blocked.pdf">Blocked PDF</a>
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        # Should return relative URLs with path: prefix and allowed domains with url: prefix
        expected_keys = {
            Key(type="path", value="relative/document.pdf"),
            Key(type="url", value="https://example.com/docs/allowed.pdf"),
        }

        assert len(mined_resources) == 2
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_handles_non_url_keys(self):
        """Test that HTMLDocumentMiner handles non-URL keys properly."""

        miner = HTMLDocumentMiner(allowed_domains=["*"])

        # Test with a file: key
        key = Key(type="file", value="/path/to/local/file.html")
        text_data = """
        <html>
        <body>
          <a href="docs/local-doc.pdf">Local PDF</a>
          <a href="/absolute/path/doc.docx">Absolute Path DOCX</a>
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        # Should return relative URLs with path: prefix when no base URL is available for non-URL keys
        expected_keys = {
            Key(type="path", value="docs/local-doc.pdf"),
            Key(type="path", value="/absolute/path/doc.docx"),
        }

        assert len(mined_resources) == 2
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_ignores_non_document_links(self):
        """Test that HTMLDocumentMiner ignores links that are not documents."""

        miner = HTMLDocumentMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com")
        text_data = """
        <html>
        <body>
          <!-- Document links (should be found) -->
          <a href="document.pdf">PDF Document</a>
          <a href="spreadsheet.xlsx">Excel File</a>

          <!-- Non-document links (should be ignored) -->
          <a href="page.html">HTML Page</a>
          <a href="image.jpg">JPEG Image</a>
          <a href="video.mp4">MP4 Video</a>
          <a href="audio.mp3">MP3 Audio</a>
          <a href="archive.zip">ZIP Archive</a>
          <a href="script.js">JavaScript File</a>
          <a href="style.css">CSS File</a>
          <a href="https://example.com">Website Link</a>
          <a href="mailto:test@example.com">Email Link</a>
          <a href="javascript:void(0)">JavaScript Link</a>
          <a href="#section">Fragment Link</a>
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        # Should only find document links
        expected_keys = {
            Key(type="url", value="https://example.com/document.pdf"),
            Key(type="url", value="https://example.com/spreadsheet.xlsx"),
        }

        assert len(mined_resources) == 2
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_handles_links_without_text(self):
        """Test that HTMLDocumentMiner handles links without text content."""

        miner = HTMLDocumentMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com")
        text_data = """
        <html>
        <body>
          <!-- Link with text -->
          <a href="with-text.pdf">Document with text</a>

          <!-- Link without text -->
          <a href="no-text.pdf"></a>

          <!-- Link with only whitespace -->
          <a href="whitespace.pdf">   </a>

          <!-- Link with nested elements but no text -->
          <a href="nested.pdf"><img src="icon.png" alt="PDF"></a>

          <!-- Link with nested text -->
          <a href="nested-text.pdf"><span>Nested</span> Document</a>
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        assert len(mined_resources) == 5

        mined_by_url = {str(mr.key): mr for mr in mined_resources}

        # Check metadata for different cases
        assert (
            mined_by_url["url:https://example.com/with-text.pdf"].metadata.get(
                "link_text"
            )
            == "Document with text"
        )
        assert (
            mined_by_url["url:https://example.com/no-text.pdf"].metadata.get(
                "link_text"
            )
            == ""
        )
        assert (
            mined_by_url["url:https://example.com/whitespace.pdf"].metadata.get(
                "link_text"
            )
            == ""
        )
        assert (
            mined_by_url["url:https://example.com/nested.pdf"].metadata.get("link_text")
            == ""
        )
        assert (
            mined_by_url["url:https://example.com/nested-text.pdf"].metadata.get(
                "link_text"
            )
            == "Nested Document"
        )

    def test_miner_uses_host_header_from_metadata(self):
        """Test that HTMLDocumentMiner uses Host header from metadata for base URL."""

        miner = HTMLDocumentMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com")
        text_data = """
        <html>
        <body>
          <a href="/docs/report.pdf">Report PDF</a>
          <a href="files/manual.docx">Manual DOCX</a>
        </body>
        </html>
        """

        # Create TextResource with Host header in metadata
        resource = TextResource(
            mime_type="text/html",
            text=text_data,
            metadata={
                "response_headers": {
                    "Host": "cdn.example.com",
                    "Content-Type": "text/html",
                }
            },
        )

        mined_resources = miner.mine(key, resource)

        # Should use Host header for base URL construction
        expected_keys = {
            Key(type="url", value="https://cdn.example.com/docs/report.pdf"),
            Key(type="url", value="https://cdn.example.com/files/manual.docx"),
        }

        assert len(mined_resources) == 2
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_configurable_document_extensions(self):
        """Test that HTMLDocumentMiner respects custom document extensions."""

        # Only look for PDF and TXT files
        miner = HTMLDocumentMiner(
            allowed_domains=["*"], document_extensions=["pdf", "txt"]
        )

        key = Key(type="url", value="https://example.com")
        text_data = """
        <html>
        <body>
          <a href="document.pdf">PDF Document</a>
          <a href="readme.txt">Text File</a>
          <a href="spreadsheet.xlsx">Excel File</a>
          <a href="presentation.pptx">PowerPoint File</a>
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        # Should only find PDF and TXT files
        expected_keys = {
            Key(type="url", value="https://example.com/document.pdf"),
            Key(type="url", value="https://example.com/readme.txt"),
        }

        assert len(mined_resources) == 2
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_class_attrs(self):
        """Test that HTMLDocumentMiner class attributes work like HTMLImageMiner."""

        class CustomMiner(HTMLDocumentMiner):
            allowed_domains = ["example.com", "cdn.example.com"]
            document_extensions = ["pdf", "docx"]

        miner = CustomMiner()

        assert miner.allowed_domains == ["example.com", "cdn.example.com"]
        assert miner.document_extensions == ["pdf", "docx"]


class TestHTMLPageMiner:
    def test_miner_finds_page_links(self):
        """Test that HTMLPageMiner finds page links in HTML."""
        miner = HTMLPageMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com/about/")
        text_data = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>About Us</title>
</head>
<body>
  <nav>
    <a href="/">Home</a>
    <a href="/about/">About</a>
    <a href="/about/team/">Our Team</a>
    <a href="/about/history/">History</a>
    <a href="/services/">Services</a>
    <a href="/contact/">Contact</a>
  </nav>

  <main>
    <h1>About Us</h1>
    <p>Learn more about <a href="/about/team/">our team</a> or <a href="/about/history/">our history</a>.</p>

    <!-- External link -->
    <a href="https://partner.com/info/">Partner Info</a>

    <!-- Non-page links (should be ignored) -->
    <a href="/documents/report.pdf">Annual Report</a>
    <a href="/images/logo.png">Logo</a>
    <a href="mailto:info@example.com">Email Us</a>
    <a href="#section1">Jump to Section</a>
    <a href="javascript:void(0)">JS Link</a>
  </main>
</body>
</html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        # Should find page links with normalized URLs (trailing slashes, no query params)
        expected_keys = [
            Key(type="url", value="https://example.com/"),
            Key(type="url", value="https://example.com/about/"),
            Key(type="url", value="https://example.com/about/team/"),
            Key(type="url", value="https://example.com/about/history/"),
            Key(type="url", value="https://example.com/services/"),
            Key(type="url", value="https://example.com/contact/"),
            Key(type="url", value="https://partner.com/info/"),
        ]

        assert len(mined_resources) == len(expected_keys)
        mined_keys = [mr.key for mr in mined_resources]
        assert sorted(mined_keys, key=str) == sorted(expected_keys, key=str)

        # Check that link text is saved in metadata
        mined_by_url = {str(mr.key): mr for mr in mined_resources}

        expected_link_texts = {
            "url:https://example.com/": "Home",
            "url:https://example.com/about/": "About",
            "url:https://example.com/about/team/": "Our Team",
            "url:https://example.com/services/": "Services",
        }

        for url, expected_text in expected_link_texts.items():
            resource = mined_by_url[url]
            assert resource.metadata.get("link_text") == expected_text, (
                f"Link text mismatch for {url}"
            )

    def test_miner_normalizes_urls(self):
        """Test that HTMLPageMiner normalizes URLs by adding trailing slashes and removing query params."""
        miner = HTMLPageMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com/")
        text_data = """
        <html>
        <body>
          <!-- URLs without trailing slashes -->
          <a href="/about">About</a>
          <a href="/services">Services</a>

          <!-- URLs with query parameters -->
          <a href="/search?q=test&page=1">Search</a>
          <a href="/products/?category=electronics&sort=price">Products</a>

          <!-- URLs with fragments -->
          <a href="/help#faq">Help</a>

          <!-- Already normalized URLs -->
          <a href="/contact/">Contact</a>
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        expected_keys = {
            Key(type="url", value="https://example.com/about/"),
            Key(type="url", value="https://example.com/services/"),
            Key(
                type="url", value="https://example.com/search/"
            ),  # Query params removed
            Key(
                type="url", value="https://example.com/products/"
            ),  # Query params removed
            Key(type="url", value="https://example.com/help/"),  # Fragment removed
            Key(type="url", value="https://example.com/contact/"),
        }

        assert len(mined_resources) == 6
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_ignores_non_page_links(self):
        """Test that HTMLPageMiner ignores non-page links."""
        miner = HTMLPageMiner(allowed_domains=["*"])

        key = Key(type="url", value="https://example.com/")
        text_data = """
        <html>
        <body>
          <!-- Page links (should be found) -->
          <a href="/about/">About</a>
          <a href="/services/">Services</a>

          <!-- Non-page links (should be ignored) -->
          <a href="/documents/report.pdf">PDF Report</a>
          <a href="/files/data.xlsx">Excel File</a>
          <a href="/images/logo.png">Logo</a>
          <a href="/videos/demo.mp4">Demo Video</a>
          <a href="/archive.zip">Archive</a>
          <a href="/styles.css">CSS</a>
          <a href="/script.js">JavaScript</a>
          <a href="mailto:test@example.com">Email</a>
          <a href="tel:+1234567890">Phone</a>
          <a href="javascript:void(0)">JS Link</a>
          <a href="#section">Fragment</a>
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        # Should only find page links
        expected_keys = {
            Key(type="url", value="https://example.com/about/"),
            Key(type="url", value="https://example.com/services/"),
        }

        assert len(mined_resources) == 2
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_domain_allowlist(self):
        """Test that HTMLPageMiner filters URLs based on allowed_domains."""
        miner = HTMLPageMiner(allowed_domains=["example.com"])

        key = Key(type="file", value="/local/file.html")
        text_data = """
        <html>
        <body>
          <a href="relative/page/">Relative Page</a>
          <a href="https://example.com/allowed/">Allowed Page</a>
          <a href="https://badsite.com/blocked/">Blocked Page</a>
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        # Should return relative URLs with path: prefix and allowed domains with url: prefix
        expected_keys = {
            Key(type="path", value="relative/page/"),
            Key(type="url", value="https://example.com/allowed/"),
        }

        assert len(mined_resources) == 2
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys

    def test_miner_handles_non_url_keys(self):
        """Test that HTMLPageMiner handles non-URL keys properly."""
        miner = HTMLPageMiner(allowed_domains=["*"])

        # Test with a file: key - no hierarchy logic applies
        key = Key(type="file", value="/path/to/local/file.html")
        text_data = """
        <html>
        <body>
          <a href="pages/local-page/">Local Page</a>
          <a href="/absolute/path/page/">Absolute Path Page</a>
        </body>
        </html>
        """

        resource = TextResource(mime_type="text/html", text=text_data, metadata={})
        mined_resources = miner.mine(key, resource)

        # Should return relative URLs with path: prefix
        expected_keys = {
            Key(type="path", value="pages/local-page/"),
            Key(type="path", value="/absolute/path/page/"),
        }

        assert len(mined_resources) == 2
        mined_keys = {mr.key for mr in mined_resources}
        assert mined_keys == expected_keys
