import pytest
from django.utils import timezone

from isekai.miners import HTMLImageMiner
from isekai.operations import mine
from isekai.types import ResourceData
from tests.test_seeders import freeze_time
from tests.testapp.models import ConcreteResource


class TestHTMLImageMiner:
    def test_miner_finds_images(self):
        miner = HTMLImageMiner(allowed_domains=["*"])

        key = "url:https://example.com"
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

        # Create ResourceData object
        data = ResourceData(mime_type="text/html", data_type="text", data=text_data)

        keys = miner.mine(key, data)

        # Check that we found all expected URLs (order doesn't matter)
        expected_urls = {
            "url:https://example.com/images/cat.jpg",
            "url:https://example.com/images/dog-small.jpg",
            "url:https://example.com/images/dog-large.jpg",
            "url:https://example.com/images/bird-small.jpg",
            "url:https://example.com/images/bird-large.jpg",
            "url:https://example.com/images/bird-fallback.jpg",
            "url:https://example.com/images/flower-hd.jpg",
            "url:https://example.com/images/flower-default.jpg",
        }

        assert len(keys) == 9
        assert set(keys) == expected_urls

    def test_miner_uses_host_header_from_metadata(self):
        """Test that HTMLImageMiner uses Host header from metadata for base URL."""
        miner = HTMLImageMiner(allowed_domains=["*"])

        key = "url:https://example.com"
        text_data = """
        <html>
        <body>
          <img src="/images/logo.png" alt="Logo">
          <img src="assets/icon.svg" alt="Icon">
        </body>
        </html>
        """

        # Create ResourceData with Host header in metadata
        data = ResourceData(mime_type="text/html", data_type="text", data=text_data)
        data.metadata["response_headers"] = {
            "Host": "cdn.example.com",
            "Content-Type": "text/html",
        }

        keys = miner.mine(key, data)

        # Should use Host header for base URL construction
        expected_urls = {
            "url:https://cdn.example.com/images/logo.png",
            "url:https://cdn.example.com/assets/icon.svg",
        }

        assert len(keys) == 2
        assert set(keys) == expected_urls

    def test_miner_falls_back_to_url_when_no_host_header(self):
        """Test that HTMLImageMiner falls back to original URL when no Host header."""
        miner = HTMLImageMiner(allowed_domains=["*"])

        key = "url:https://example.com"
        text_data = """
        <html>
        <body>
          <img src="/images/fallback.png" alt="Fallback">
        </body>
        </html>
        """

        # Create ResourceData without Host header in metadata
        data = ResourceData(mime_type="text/html", data_type="text", data=text_data)
        data.metadata["response_headers"] = {"Content-Type": "text/html"}

        keys = miner.mine(key, data)

        # Should fall back to original URL from key
        expected_urls = {"url:https://example.com/images/fallback.png"}

        assert len(keys) == 1
        assert set(keys) == expected_urls

    def test_miner_handles_non_url_keys(self):
        """Test that HTMLImageMiner handles non-URL keys properly."""
        miner = HTMLImageMiner(allowed_domains=["*"])

        # Test with a file: key
        key = "file:/path/to/local/file.html"
        text_data = """
        <html>
        <body>
          <img src="images/local-image.jpg" alt="Local">
          <img src="/absolute/path/image.png" alt="Absolute">
        </body>
        </html>
        """

        data = ResourceData(mime_type="text/html", data_type="text", data=text_data)

        keys = miner.mine(key, data)

        # Should return relative URLs with path: prefix when no base URL is available for non-URL keys
        expected_urls = {"path:images/local-image.jpg", "path:/absolute/path/image.png"}

        assert len(keys) == 2
        assert set(keys) == expected_urls

    def test_miner_handles_absolute_urls(self):
        """Test that HTMLImageMiner handles absolute URLs correctly."""
        miner = HTMLImageMiner(allowed_domains=["*"])

        key = "url:https://example.com"
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

        data = ResourceData(mime_type="text/html", data_type="text", data=text_data)

        keys = miner.mine(key, data)

        # Should preserve absolute URLs as-is and resolve relative ones
        expected_urls = {
            "url:https://example.com/images/relative.jpg",
            "url:https://cdn.example.com/images/absolute.jpg",
            "url:http://old.example.com/images/http.jpg",
            "url:https://static.example.com/images/protocol-relative.jpg",  # Protocol-relative URLs get resolved
        }

        assert len(keys) == 4
        assert set(keys) == expected_urls

    def test_miner_domain_allowlist(self):
        """Test that HTMLImageMiner filters URLs based on allowed_domains."""
        miner = HTMLImageMiner(allowed_domains=["example.com"])

        key = "file:/local/file.html"  # No base URL available
        text_data = """
        <html>
        <body>
          <img src="relative/path.jpg" alt="Relative">
          <img src="https://example.com/images/allowed.jpg" alt="Allowed">
          <img src="https://badsite.com/images/blocked.jpg" alt="Blocked">
        </body>
        </html>
        """

        data = ResourceData(mime_type="text/html", data_type="text", data=text_data)

        keys = miner.mine(key, data)

        # Should return relative URLs with path: prefix and allowed domains with url: prefix
        expected_urls = {
            "path:relative/path.jpg",  # Relative URL gets path: prefix
            "url:https://example.com/images/allowed.jpg",  # Allowed domain gets url: prefix
        }

        assert len(keys) == 2
        assert set(keys) == expected_urls

    def test_miner_allows_relative_urls_when_no_allowlist(self):
        """Test that relative URLs are allowed even when no allowed_domains is specified."""
        miner = HTMLImageMiner()  # No allowed_domains

        key = "file:/local/file.html"  # No base URL available
        text_data = """
        <html>
        <body>
          <img src="relative/path.jpg" alt="Relative">
          <img src="https://example.com/images/blocked.jpg" alt="Blocked">
        </body>
        </html>
        """

        data = ResourceData(mime_type="text/html", data_type="text", data=text_data)

        keys = miner.mine(key, data)

        # Should return only relative URLs with path: prefix, absolute URLs should be blocked
        expected_urls = {"path:relative/path.jpg"}

        assert len(keys) == 1
        assert set(keys) == expected_urls

    def test_class_attrs(self):
        class Miner(HTMLImageMiner):
            allowed_domains = ["example.com", "cdn.example.com"]

        miner = Miner()

        assert miner.allowed_domains == ["example.com", "cdn.example.com"]


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
            mine()

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

        # Check original resource is updated
        original_resource.refresh_from_db()
        assert set(original_resource.dependencies.values_list("pk", flat=True)) == set(
            resources.values_list("pk", flat=True)
        ), "Dependencies should match mined resources"

        assert original_resource.status == ConcreteResource.Status.MINED
        assert original_resource.mined_at == now

    def test_should_fail_to_transition(self):
        # TODO: Move this to the test_models perhaps
        pass
