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

        assert len(keys) == 8
        assert set(keys) == expected_urls
