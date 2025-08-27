import csv
from xml.etree import ElementTree as ET

import requests

from isekai.types import Key, SeededResource


class BaseSeeder:
    def seed(self) -> list[SeededResource]:
        return []


class CSVSeeder(BaseSeeder):
    """A seeder that reads resource keys from a CSV file.

    The CSV file should have 'type' and 'value' columns where:
    - 'type' specifies the resource key prefix (e.g., 'url', 'file')
    - 'value' contains the resource value

    Keys will be formatted as '{type}:{value}'.
    """

    csv_filename: str | None = None

    def __init__(self, csv_filename: str | None = None):
        self.csv_filename = csv_filename or self.csv_filename
        if self.csv_filename is None:
            raise ValueError(
                "csv_filename must be provided either as parameter or class attribute"
            )

    def seed(self) -> list[SeededResource]:
        resources = []

        if self.csv_filename:
            with open(self.csv_filename) as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if "type" in row and "value" in row:
                        key = Key(type=row["type"], value=row["value"])
                        resources.append(SeededResource(key=key, metadata={}))

        return resources


class SitemapSeeder(BaseSeeder):
    """A seeder that reads URLs from XML sitemap files.

    Fetches sitemap XML files and extracts URL locations,
    returning them as 'url:{url}' keys.
    """

    sitemap_url: str | None = None

    def __init__(self, sitemap_url: str | None = None):
        self.sitemap_url = sitemap_url or self.sitemap_url

        if self.sitemap_url is None:
            raise ValueError(
                "sitemap must be provided either as parameter or class attribute"
            )

    def seed(self) -> list[SeededResource]:
        resources = []

        if self.sitemap_url:
            response = requests.get(self.sitemap_url)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            # Handle XML namespace for sitemap
            namespaces = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            for url_elem in root.findall("sitemap:url", namespaces):
                loc_elem = url_elem.find("sitemap:loc", namespaces)
                if loc_elem is not None and loc_elem.text:
                    key = Key(type="url", value=loc_elem.text)
                    resources.append(SeededResource(key=key, metadata={}))

        return resources
