from isekai.extractors import HTTPExtractor
from isekai.miners import HTMLImageMiner
from isekai.models import AbstractResource
from isekai.seeders import CSVSeeder, SitemapSeeder


class Seeder(CSVSeeder, SitemapSeeder):
    csv_filename = "tests/files/test_data.csv"
    sitemaps = [
        "https://example.com/sitemap.xml",
        "https://example.com/jp/sitemap.xml",
    ]


class Extractor(HTTPExtractor):
    pass


class Miner(HTMLImageMiner):
    pass


class ConcreteResource(AbstractResource):
    """Concrete implementation of AbstractResource for testing."""

    seeder = Seeder()
    extractor = Extractor()

    class Meta:
        app_label = "testapp"
        verbose_name = "Concrete Resource"
        verbose_name_plural = "Concrete Resources"
