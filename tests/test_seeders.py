import pytest
import responses
from django.utils import timezone
from freezegun import freeze_time

from isekai.pipelines import get_django_pipeline
from isekai.seeders import CSVSeeder, SitemapSeeder
from tests.test_extractors import ConcreteResource


class TestCSVSeeder:
    def test_csv_seeder(self):
        seeder = CSVSeeder(csv_filename="tests/files/test_data.csv")

        seeded_resources = seeder.seed()

        assert len(seeded_resources) == 5
        assert str(seeded_resources[0].key) == "url:https://example.com/data1.csv"
        assert str(seeded_resources[1].key) == "url:https://example.com/csv-page1"
        assert str(seeded_resources[2].key) == "url:https://example.com/image.png"
        assert str(seeded_resources[3].key) == "file:my_files/foo.txt"
        assert str(seeded_resources[4].key) == 'json:{"key": "value"}'

    def test_class_attrs(self):
        class Seeder(CSVSeeder):
            csv_filename = "tests/files/test_data.csv"

        seeder = Seeder()

        assert seeder.csv_filename == "tests/files/test_data.csv"


class TestSitemapSeeder:
    @responses.activate
    def test_sitemap_seeder(self):
        # Mock sitemap responses
        responses.add(
            responses.GET,
            "https://example.com/sitemap.xml",
            body="""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://example.com/page1</loc></url>
    <url><loc>https://example.com/page2</loc></url>
    <url><loc>https://example.com/page3</loc></url>
    <url><loc>https://example.com/page4</loc></url>
    <url><loc>https://example.com/page5</loc></url>
</urlset>""",
            status=200,
        )

        seeder = SitemapSeeder(
            sitemap_url="https://example.com/sitemap.xml",
        )

        seeded_resources = seeder.seed()

        assert len(seeded_resources) == 5
        assert str(seeded_resources[0].key) == "url:https://example.com/page1"
        assert str(seeded_resources[1].key) == "url:https://example.com/page2"
        assert str(seeded_resources[2].key) == "url:https://example.com/page3"
        assert str(seeded_resources[3].key) == "url:https://example.com/page4"
        assert str(seeded_resources[4].key) == "url:https://example.com/page5"

    def test_class_attrs(self):
        class Seeder(SitemapSeeder):
            sitemap_url = "https://example.com/sitemap.xml"

        seeder = Seeder()

        assert seeder.sitemap_url == "https://example.com/sitemap.xml"


@pytest.mark.django_db
class TestSeed:
    @responses.activate
    def test_seed_creates_resources(self):
        # Mock sitemap responses
        responses.add(
            responses.GET,
            "https://example.com/sitemap.xml",
            body="""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://example.com/page1</loc></url>
    <url><loc>https://example.com/page2</loc></url>
    <url><loc>https://example.com/page3</loc></url>
    <url><loc>https://example.com/page4</loc></url>
    <url><loc>https://example.com/page5</loc></url>
</urlset>""",
            status=200,
        )

        responses.add(
            responses.GET,
            "https://example.com/jp/sitemap.xml",
            body="""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://example.com/jp/page1</loc></url>
    <url><loc>https://example.com/jp/page2</loc></url>
    <url><loc>https://example.com/jp/page3</loc></url>
    <url><loc>https://example.com/jp/page4</loc></url>
    <url><loc>https://example.com/jp/page5</loc></url>
</urlset>""",
            status=200,
        )

        now = timezone.now()
        with freeze_time(now):
            pipeline = get_django_pipeline()
            pipeline.seed()

        resources = ConcreteResource.objects.all().order_by("key")

        assert len(resources) == 15

        assert resources[0].key == "file:my_files/foo.txt"
        assert resources[1].key == 'json:{"key": "value"}'
        assert resources[2].key == "url:https://example.com/csv-page1"
        assert resources[3].key == "url:https://example.com/data1.csv"
        assert resources[4].key == "url:https://example.com/image.png"
        assert resources[5].key == "url:https://example.com/jp/page1"
        assert resources[6].key == "url:https://example.com/jp/page2"
        assert resources[7].key == "url:https://example.com/jp/page3"
        assert resources[8].key == "url:https://example.com/jp/page4"
        assert resources[9].key == "url:https://example.com/jp/page5"
        assert resources[10].key == "url:https://example.com/page1"
        assert resources[11].key == "url:https://example.com/page2"
        assert resources[12].key == "url:https://example.com/page3"
        assert resources[13].key == "url:https://example.com/page4"
        assert resources[14].key == "url:https://example.com/page5"

        assert all(resource.seeded_at == now for resource in resources)

    @responses.activate
    def test_seed_is_idempotent(self):
        # Mock sitemap responses
        responses.add(
            responses.GET,
            "https://example.com/sitemap.xml",
            body="""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://example.com/page1</loc></url>
    <url><loc>https://example.com/page2</loc></url>
    <url><loc>https://example.com/page3</loc></url>
    <url><loc>https://example.com/page4</loc></url>
    <url><loc>https://example.com/page5</loc></url>
</urlset>""",
            status=200,
        )

        responses.add(
            responses.GET,
            "https://example.com/jp/sitemap.xml",
            body="""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://example.com/jp/page1</loc></url>
    <url><loc>https://example.com/jp/page2</loc></url>
    <url><loc>https://example.com/jp/page3</loc></url>
    <url><loc>https://example.com/jp/page4</loc></url>
    <url><loc>https://example.com/jp/page5</loc></url>
</urlset>""",
            status=200,
        )

        # First seed operation
        pipeline = get_django_pipeline()
        pipeline.seed()
        first_count = ConcreteResource.objects.count()
        assert first_count == 15

        # Second seed operation - should not create duplicates
        pipeline.seed()
        second_count = ConcreteResource.objects.count()
        assert second_count == 15  # Same count, no new resources
