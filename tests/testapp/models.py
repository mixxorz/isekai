from isekai.contrib.wagtail import ImageTransformer
from isekai.extractors import HTTPExtractor
from isekai.miners import HTMLImageMiner
from isekai.models import AbstractResource
from isekai.seeders import CSVSeeder, SitemapSeeder


class Extractor(HTTPExtractor):
    pass


class Miner(HTMLImageMiner):
    allowed_domains = ["*"]


class Transformer(ImageTransformer):
    pass


class ConcreteResource(AbstractResource):
    seeders = [
        CSVSeeder(csv_filename="tests/files/test_data.csv"),
        SitemapSeeder(
            sitemaps=[
                "https://example.com/sitemap.xml",
                "https://example.com/jp/sitemap.xml",
            ]
        ),
    ]
    extractors = [HTTPExtractor()]
    miners = [HTMLImageMiner(allowed_domains=["*"])]
    transformers = [ImageTransformer()]

    class Meta:
        app_label = "testapp"
        verbose_name = "Concrete Resource"
        verbose_name_plural = "Concrete Resources"
