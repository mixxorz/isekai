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
    allowed_domains = ["*"]


class ConcreteResource(AbstractResource):
    seeder = Seeder()
    extractor = Extractor()
    miner = Miner()

    class Meta:
        app_label = "testapp"
        verbose_name = "Concrete Resource"
        verbose_name_plural = "Concrete Resources"
