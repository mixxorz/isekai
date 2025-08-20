import csv
from xml.etree import ElementTree as ET

import requests


class BaseSeeder:
    def seed(self) -> list[str]:
        return []


class CSVSeeder(BaseSeeder):
    """A seeder that reads resource keys from a CSV file.

    The CSV file should have 'type' and 'value' columns where:
    - 'type' specifies the resource key prefix (e.g., 'url', 'file')
    - 'value' contains the resource value

    Keys will be formatted as '{type}:{value}'.
    """

    def __init__(self, filename: str | None = None):
        self.filename = filename or getattr(self.__class__, "filename", None)
        if self.filename is None:
            raise ValueError(
                "filename must be provided either as parameter or class attribute"
            )

    def seed(self) -> list[str]:
        keys = []

        if self.filename:
            with open(self.filename) as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if "type" in row and "value" in row:
                        keys.append(f"{row['type']}:{row['value']}")

        return keys


class SitemapSeeder(BaseSeeder):
    """A seeder that reads URLs from XML sitemap files.

    Fetches sitemap XML files and extracts URL locations,
    returning them as 'url:{url}' keys.
    """

    def __init__(self, sitemaps: list[str] | None = None):
        self.sitemaps = sitemaps or getattr(self.__class__, "sitemaps", [])

    def seed(self) -> list[str]:
        keys = []
        for sitemap_url in self.sitemaps:
            response = requests.get(sitemap_url)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            # Handle XML namespace for sitemap
            namespaces = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            for url_elem in root.findall("sitemap:url", namespaces):
                loc_elem = url_elem.find("sitemap:loc", namespaces)
                if loc_elem is not None and loc_elem.text:
                    keys.append(f"url:{loc_elem.text}")

        return keys
