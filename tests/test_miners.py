from isekai.miners import HTMLImageMiner
from isekai.types import ResourceData


class TestHTMLImageMiner:
    def test_miner_finds_images(self):
        miner = HTMLImageMiner()

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
        miner = HTMLImageMiner()

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
        miner = HTMLImageMiner()

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
        miner = HTMLImageMiner()

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

        # Should return relative URLs as-is when no base URL is available for non-URL keys
        expected_urls = {"url:images/local-image.jpg", "url:/absolute/path/image.png"}

        assert len(keys) == 2
        assert set(keys) == expected_urls

    def test_miner_handles_absolute_urls(self):
        """Test that HTMLImageMiner handles absolute URLs correctly."""
        miner = HTMLImageMiner()

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
