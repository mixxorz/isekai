import pytest
from django.utils import timezone
from freezegun import freeze_time

from isekai.extractors import HTTPExtractor
from isekai.operations import extract
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
