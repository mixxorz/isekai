from typing import cast
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from isekai.types import BlobResource, Key, MinedResource, TextResource


class BaseMiner:
    def mine(
        self, key: Key, resource: TextResource | BlobResource
    ) -> list[MinedResource]:
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

    Domain filtering:
    - Relative URLs without domains are always allowed (assumed local)
    - If allowed_domains is empty/None, all domain URLs are denied (default: deny all)
    - If allowed_domains contains '*', all URLs are allowed
    - Otherwise, only URLs from allowed domains are returned
    """

    def __init__(self, allowed_domains: list[str] | None = None):
        """
        Initialize HTMLImageMiner.

        Args:
            allowed_domains: Optional list of allowed domains. If empty/None,
                           all URLs are denied. Use ['*'] to allow all domains.
        """
        # Support both constructor parameter and class attribute
        domains = allowed_domains or getattr(self.__class__, "allowed_domains", None)
        self.allowed_domains = domains

    def mine(
        self, key: Key, resource: TextResource | BlobResource
    ) -> list[MinedResource]:
        mined_resources = super().mine(key, resource)

        # Only process text resources
        if not isinstance(resource, TextResource):
            return []

        base_url = self._determine_base_url(key, resource)
        soup = BeautifulSoup(resource.text, "html.parser")
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
        resolved_urls = []
        for url in image_urls:
            # If the URL is already absolute (has scheme), keep it as-is
            parsed_url = urlparse(url)
            if parsed_url.scheme:
                resolved_urls.append(url)
            # If we don't have a base URL, keep the relative URL as-is
            elif base_url is None:
                resolved_urls.append(url)
            # Use urljoin to resolve relative URLs against the base URL
            else:
                resolved_urls.append(urljoin(base_url, url))

        # Filter URLs by domain allowlist and deduplicate
        final_urls = []
        for url in resolved_urls:
            if self._is_domain_allowed(url) and url:
                final_urls.append(url)

        # Convert to MinedResource objects with appropriate key prefixes
        for url in final_urls:
            parsed_url = urlparse(url)
            if parsed_url.scheme:
                # Absolute URL gets "url" type
                mined_key = Key(type="url", value=url)
            else:
                # Relative URL gets "path" type
                mined_key = Key(type="path", value=url)

            mined_resources.append(MinedResource(key=mined_key, metadata={}))

        return mined_resources

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

    def _determine_base_url(
        self, key: Key, resource: TextResource | BlobResource
    ) -> str | None:
        """Determine the best base URL for resolving relative image URLs."""
        # First priority: Host header from response metadata
        if "response_headers" in resource.metadata:
            response_headers = resource.metadata["response_headers"]
            if "Host" in response_headers:
                host = response_headers["Host"]
                # If we have a URL key, preserve its scheme
                if key.type == "url":
                    original_url = key.value
                    parsed_original = urlparse(original_url)
                    scheme = parsed_original.scheme or "https"
                    return f"{scheme}://{host}"
                else:
                    # For non-URL keys, default to https
                    return f"https://{host}"

        # Second priority: Extract URL from key if it's a URL key
        if key.type == "url":
            return key.value

        # No base URL available for non-URL keys without Host header
        return None

    def _is_domain_allowed(self, url: str) -> bool:
        """Check if URL's domain is allowed based on allowed_domains."""
        # Parse URL to get the domain
        parsed_url = urlparse(url)

        # For relative URLs without a domain, always allow them (assume local)
        if not parsed_url.netloc:
            return True

        # If no allowed domains specified, deny all domains (but relative URLs already passed)
        if not self.allowed_domains:
            return False

        # If allowed domains contains '*', allow all domains
        if "*" in self.allowed_domains:
            return True

        # Check if the domain is in the allowed domains
        return parsed_url.netloc in self.allowed_domains
