from typing import cast
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from isekai.types import ResourceData


class BaseMiner:
    def mine(self, key: str, data: ResourceData) -> list[str]:
        return []


class HTMLImageMiner(BaseMiner):
    def mine(self, key: str, data: ResourceData) -> list[str]:
        # Only process text data
        if data.data_type != "text" or not isinstance(data.data, str):
            return []

        # Extract base URL from the resource key
        if not key.startswith("url:"):
            return []

        base_url = key[4:]  # Remove "url:" prefix

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(data.data, "html.parser")

        image_urls = []

        # Find all <img> tags
        for img in soup.find_all("img"):
            img_tag = cast(Tag, img)
            # Handle src attribute
            src = img_tag.get("src")
            if src:
                image_urls.append(self._make_absolute_url(base_url, str(src)))

            # Handle srcset attribute
            srcset = img_tag.get("srcset")
            if srcset:
                image_urls.extend(self._parse_srcset(base_url, str(srcset)))

        # Find all <source> tags (inside <picture> elements)
        for source in soup.find_all("source"):
            source_tag = cast(Tag, source)
            srcset = source_tag.get("srcset")
            if srcset:
                image_urls.extend(self._parse_srcset(base_url, str(srcset)))

        # Deduplicate URLs while preserving order
        seen = set()
        unique_urls = []
        for url in image_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        # Convert to resource keys with "url:" prefix
        return [f"url:{url}" for url in unique_urls]

    def _parse_srcset(self, base_url: str, srcset: str) -> list[str]:
        """Parse srcset attribute and extract URLs."""
        urls = []
        for entry in srcset.split(","):
            entry = entry.strip()
            if entry:
                # srcset entries are in format "URL [width]w" or "URL [pixel]x" or just "URL"
                url_part = entry.split()[0]  # Take first part (URL)
                urls.append(self._make_absolute_url(base_url, url_part))
        return urls

    def _make_absolute_url(self, base_url: str, url: str) -> str:
        """Convert relative URLs to absolute URLs."""
        return urljoin(base_url, url)
