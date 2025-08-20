from typing import cast
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from isekai.types import ResourceData


class BaseMiner:
    def mine(self, key: str, data: ResourceData) -> list[str]:
        return []


class HTMLImageMiner(BaseMiner):
    """
    Extracts image URLs from HTML content.

    Parses HTML using BeautifulSoup to find image URLs from:
    - <img> src attributes
    - <img> srcset attributes
    - <source> srcset attributes (inside <picture> elements)

    URL resolution behavior:
    - Absolute URLs (with scheme) are returned as-is
    - Relative URLs are resolved against a base URL when available
    - If no base URL can be determined, relative URLs are returned unchanged

    Base URL determination priority:
    1. Host header from response metadata (preserves original scheme)
    2. URL extracted from resource key (for url: keys)
    3. None (relative URLs kept as-is)
    """

    def mine(self, key: str, data: ResourceData) -> list[str]:
        keys = super().mine(key, data)

        # Only process text data
        if data.data_type != "text" or not isinstance(data.data, str):
            return []

        base_url = self._determine_base_url(key, data)
        soup = BeautifulSoup(data.data, "html.parser")
        image_urls = []

        # Find all <img> tags
        for img in soup.find_all("img"):
            img_tag = cast(Tag, img)
            # Handle src attribute
            src = img_tag.get("src")
            if src:
                image_urls.append(str(src))

            # Handle srcset attribute
            srcset = img_tag.get("srcset")
            if srcset:
                image_urls.extend(self._parse_srcset(str(srcset)))

        # Find all <source> tags (inside <picture> elements)
        for source in soup.find_all("source"):
            source_tag = cast(Tag, source)
            srcset = source_tag.get("srcset")
            if srcset:
                image_urls.extend(self._parse_srcset(str(srcset)))

        # Make URLs absolute if possible, otherwise keep as-is
        final_urls = []
        for url in image_urls:
            # If the URL is already absolute (has scheme), keep it as-is
            parsed_url = urlparse(url)
            if parsed_url.scheme:
                final_urls.append(url)
            # If we don't have a base URL, keep the relative URL as-is
            elif base_url is None:
                final_urls.append(url)
            # Use urljoin to resolve relative URLs against the base URL
            else:
                final_urls.append(urljoin(base_url, url))

        # Convert to resource keys with "url:" prefix
        return keys + [f"url:{url}" for url in final_urls]

    def _parse_srcset(self, srcset: str) -> list[str]:
        """Parse srcset attribute and extract URLs."""
        urls = []
        for entry in srcset.split(","):
            entry = entry.strip()
            if entry:
                # srcset entries are in format "URL [width]w" or "URL [pixel]x" or just "URL"
                url_part = entry.split()[0]  # Take first part (URL)
                urls.append(url_part)
        return urls

    def _determine_base_url(self, key: str, data: ResourceData) -> str | None:
        """Determine the best base URL for resolving relative image URLs."""
        # First priority: Host header from response metadata
        if "response_headers" in data.metadata:
            response_headers = data.metadata["response_headers"]
            if "Host" in response_headers:
                host = response_headers["Host"]
                # If we have a URL key, preserve its scheme
                if key.startswith("url:"):
                    original_url = key[4:]
                    parsed_original = urlparse(original_url)
                    scheme = parsed_original.scheme or "https"
                    return f"{scheme}://{host}"
                else:
                    # For non-URL keys, default to https
                    return f"https://{host}"

        # Second priority: Extract URL from key if it's a URL key
        if key.startswith("url:"):
            return key[4:]

        # No base URL available for non-URL keys without Host header
        return None
