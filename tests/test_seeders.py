import responses

from isekai.seeders import CSVSeeder, SitemapSeeder


class TestCSVSeeder:
    def test_csv_seeder(self):
        seeder = CSVSeeder(filename="tests/files/test_data.csv")

        keys = seeder.seed()

        assert len(keys) == 5
        assert keys[0] == "url:https://example.com/data1.csv"
        assert keys[1] == "url:https://example.com/page1"
        assert keys[2] == "url:https://example.com/image.png"
        assert keys[3] == "file:my_files/foo.txt"
        assert keys[4] == 'json:{"key": "value"}'

    def test_class_attrs(self):
        class Seeder(CSVSeeder):
            filename = "tests/files/test_data.csv"

        seeder = Seeder()

        assert seeder.filename == "tests/files/test_data.csv"


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

        seeder = SitemapSeeder(
            sitemaps=[
                "https://example.com/sitemap.xml",
                "https://example.com/jp/sitemap.xml",
            ]
        )

        keys = seeder.seed()

        assert len(keys) == 10
        assert keys[0] == "url:https://example.com/page1"
        assert keys[1] == "url:https://example.com/page2"
        assert keys[2] == "url:https://example.com/page3"
        assert keys[3] == "url:https://example.com/page4"
        assert keys[4] == "url:https://example.com/page5"
        assert keys[5] == "url:https://example.com/jp/page1"
        assert keys[6] == "url:https://example.com/jp/page2"
        assert keys[7] == "url:https://example.com/jp/page3"
        assert keys[8] == "url:https://example.com/jp/page4"
        assert keys[9] == "url:https://example.com/jp/page5"

    def test_class_attrs(self):
        class Seeder(SitemapSeeder):
            sitemaps = [
                "https://example.com/sitemap.xml",
                "https://example.com/jp/sitemap.xml",
            ]

        seeder = Seeder()

        assert seeder.sitemaps == [
            "https://example.com/sitemap.xml",
            "https://example.com/jp/sitemap.xml",
        ]
