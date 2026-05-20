from isekai.seeders import SitemapSeeder
from isekai.types import SeededResource

CASE_STUDIES_PATH = "/our-impact/case-studies/"


class CaseStudySeeder(SitemapSeeder):
    """Seeds only case study URLs from the Cairngorm Foundation sitemap."""

    sitemap_url = "https://cairngormfoundation.org.uk/sitemap.xml"

    def seed(self) -> list[SeededResource]:
        all_resources = super().seed()
        return [
            r
            for r in all_resources
            if CASE_STUDIES_PATH in r.key.value
            and r.key.value.rstrip("/") != CASE_STUDIES_PATH.rstrip("/")
        ]
