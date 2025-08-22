from isekai.contrib.wagtail import ImageTransformer
from isekai.extractors import BaseExtractor, HTTPExtractor
from isekai.miners import HTMLImageMiner
from isekai.models import AbstractResource
from isekai.seeders import CSVSeeder, SitemapSeeder
from isekai.types import TextResource


class FooBarExtractor(BaseExtractor):
    def extract(self, key):
        if not key.type == "foo":
            return None

        return TextResource(mime_type="foo/bar", text="foo bar data", metadata={})


class ConcreteResource(AbstractResource):
    seeders = [
        CSVSeeder(csv_filename="tests/files/test_data.csv"),
        SitemapSeeder(sitemap_url="https://example.com/sitemap.xml"),
        SitemapSeeder(sitemap_url="https://example.com/jp/sitemap.xml"),
    ]
    extractors = [
        HTTPExtractor(),
        FooBarExtractor(),
    ]
    miners = [HTMLImageMiner(allowed_domains=["*"])]
    transformers = [ImageTransformer()]

    class Meta:
        app_label = "testapp"
        verbose_name = "Concrete Resource"
        verbose_name_plural = "Concrete Resources"
