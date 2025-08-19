import pytest

from isekai.extractors import HTTPExtractor


class TestHTTPExtractor:
    @pytest.mark.vcr
    def test_extract_returns_resource_data(self):
        """Test that HTTPExtractor.extract returns expected ResourceData."""
        extractor = HTTPExtractor()

        result = extractor.extract("url:https://www.jpl.nasa.gov/")

        assert result.mime_type == "text/html"
        assert result.data_type == "text"
        assert "Jet Propulsion Laboratory" in result.data
