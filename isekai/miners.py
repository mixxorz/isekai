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
    Extracts image URLs from HTML content with accessibility metadata.

    Parses HTML using BeautifulSoup to find image URLs from:
    - <img> src attributes
    - <img> srcset attributes
    - <source> srcset attributes (inside <picture> elements only)

    Metadata extraction:
    - Alt text from <img> tags is captured and stored in metadata["alt_text"]

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
            return mined_resources

        base_url = self._determine_base_url(key, resource)
        soup = BeautifulSoup(resource.text, "html.parser")
        image_data = []  # List of (url, alt_text) tuples

        # Find all <img> tags
        for img in soup.find_all("img"):
            img_tag = cast(Tag, img)
            alt_text = img_tag.get("alt", "")

            # Handle src attribute
            src = img_tag.get("src")
            if src:
                image_data.append((str(src), str(alt_text)))

            # Handle srcset attribute
            srcset = img_tag.get("srcset")
            if srcset:
                for url in self._parse_srcset(str(srcset)):
                    image_data.append((url, str(alt_text)))

        # Find all <source> tags inside <picture> elements
        for picture in soup.find_all("picture"):
            for source in picture.find_all("source"):
                source_tag = cast(Tag, source)
                srcset = source_tag.get("srcset")
                if srcset:
                    # Source tags don't have alt text - that's only for img tags
                    for url in self._parse_srcset(str(srcset)):
                        image_data.append((url, ""))

        # Make URLs absolute and create MinedResource objects
        for url, alt_text in image_data:
            # Make URL absolute if possible
            parsed_url = urlparse(url)
            if parsed_url.scheme:
                # Already absolute
                resolved_url = url
            elif base_url is None:
                # Keep relative URL as-is
                resolved_url = url
            else:
                # Use urljoin to resolve relative URLs against the base URL
                resolved_url = urljoin(base_url, url)

            # Filter by domain allowlist
            if self._is_domain_allowed(resolved_url) and resolved_url:
                # Create appropriate key
                parsed_resolved = urlparse(resolved_url)
                if parsed_resolved.scheme:
                    # Absolute URL gets "url" type
                    mined_key = Key(type="url", value=resolved_url)
                else:
                    # Relative URL gets "path" type
                    mined_key = Key(type="path", value=resolved_url)

                # Create metadata with alt text
                metadata = {}
                if alt_text:
                    metadata["alt_text"] = alt_text

                mined_resources.append(MinedResource(key=mined_key, metadata=metadata))

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
