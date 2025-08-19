from isekai.extractors import HTTPExtractor
from isekai.models import AbstractResource


class Extractor(HTTPExtractor):
    pass


class ConcreteResource(AbstractResource):
    """Concrete implementation of AbstractResource for testing."""

    extractor = Extractor()

    class Meta:
        app_label = "testapp"
        verbose_name = "Concrete Resource"
        verbose_name_plural = "Concrete Resources"
