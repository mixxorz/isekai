from typing import cast
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from isekai.types import BlobResource, Key, MinedResource, TextResource


class BaseMiner:
    def mine(
        self, key: Key, resource: TextResource | BlobResource
    ) -> list[MinedResource]:
        return []


class BaseHTMLMiner(BaseMiner):
    """
    Base class for HTML miners that extract URLs with common functionality.

    Provides shared functionality for:
    - URL resolution behavior (absolute/relative)
    - Base URL determination from Host headers or URL keys
    - Domain filtering with allowlists
    - Key type determination (url vs path)

    Subclasses must implement:
    - _extract_urls(): Extract URLs and metadata from parsed HTML
    """

    allowed_domains: list[str] = []

    def __init__(self, allowed_domains: list[str] | None = None):
        """
        Initialize BaseHTMLMiner.

        Args:
            allowed_domains: Optional list of allowed domains. If empty/None,
                           all URLs are denied. Use ['*'] to allow all domains.
        """
        self.allowed_domains = allowed_domains or self.allowed_domains

    def mine(
        self, key: Key, resource: TextResource | BlobResource
    ) -> list[MinedResource]:
        mined_resources = []

        if not isinstance(resource, TextResource):
            return mined_resources

        base_url = self._determine_base_url(key, resource)
        soup = BeautifulSoup(resource.text, "html.parser")
        url_data = self._extract_urls(soup)

        for url, metadata in url_data:
            parsed_url = urlparse(url)
            if parsed_url.scheme:
                resolved_url = url
            elif base_url is None:
                resolved_url = url
            else:
                resolved_url = urljoin(base_url, url)

            if self._is_domain_allowed(resolved_url) and resolved_url:
                parsed_resolved = urlparse(resolved_url)
                if parsed_resolved.scheme:
                    mined_key = Key(type="url", value=resolved_url)
                else:
                    mined_key = Key(type="path", value=resolved_url)

                mined_resources.append(MinedResource(key=mined_key, metadata=metadata))

        return mined_resources

    def _extract_urls(self, soup: BeautifulSoup) -> list[tuple[str, dict[str, str]]]:
        """
        Extract URLs and their metadata from parsed HTML.

        Subclasses should override this method to implement their specific URL extraction logic.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            List of (url, metadata_dict) tuples
        """
        return []

    def _determine_base_url(
        self, key: Key, resource: TextResource | BlobResource
    ) -> str | None:
        """Determine the best base URL for resolving relative URLs."""
        if "response_headers" in resource.metadata:
            response_headers = resource.metadata["response_headers"]
            if "Host" in response_headers:
                host = response_headers["Host"]
                if key.type == "url":
                    original_url = key.value
                    parsed_original = urlparse(original_url)
                    scheme = parsed_original.scheme or "https"
                    return f"{scheme}://{host}"
                else:
                    return f"https://{host}"

        if key.type == "url":
            return key.value

        return None

    def _is_domain_allowed(self, url: str) -> bool:
        """Check if URL's domain is allowed based on allowed_domains."""
        parsed_url = urlparse(url)

        if not parsed_url.netloc:
            return True

        if not self.allowed_domains:
            return False

        if "*" in self.allowed_domains:
            return True

        return parsed_url.netloc in self.allowed_domains


class HTMLImageMiner(BaseHTMLMiner):
    """
    Extracts image URLs from HTML content with accessibility metadata.

    Parses HTML using BeautifulSoup to find image URLs from:
    - <img> src attributes
    - <img> srcset attributes
    - <source> srcset attributes (inside <picture> elements only)

    Metadata extraction:
    - Alt text from <img> tags is captured and stored in metadata["alt_text"]
    """

    def _extract_urls(self, soup: BeautifulSoup) -> list[tuple[str, dict[str, str]]]:
        """Extract image URLs and alt text from HTML."""
        image_data = []

        for img in soup.find_all("img"):
            img_tag = cast(Tag, img)
            alt_text = str(img_tag.get("alt", ""))

            src = img_tag.get("src")
            if src:
                metadata = {"alt_text": alt_text} if alt_text else {}
                image_data.append((str(src), metadata))

            srcset = img_tag.get("srcset")
            if srcset:
                metadata = {"alt_text": alt_text} if alt_text else {}
                for url in self._parse_srcset(str(srcset)):
                    image_data.append((url, metadata))

        for picture in soup.find_all("picture"):
            picture_tag = cast(Tag, picture)
            for source in picture_tag.find_all("source"):
                source_tag = cast(Tag, source)
                srcset = source_tag.get("srcset")
                if srcset:
                    for url in self._parse_srcset(str(srcset)):
                        image_data.append((url, {}))

        return image_data

    def _parse_srcset(self, srcset: str) -> list[str]:
        """Parse srcset attribute and extract URLs."""
        urls = []
        for entry in srcset.split(","):
            entry = entry.strip()
            if entry:
                url_part = entry.split()[0]
                urls.append(url_part)
        return urls


class HTMLDocumentMiner(BaseHTMLMiner):
    """
    Extracts document URLs from HTML content with link metadata.

    Parses HTML using BeautifulSoup to find document URLs from:
    - <a> href attributes pointing to document files

    Default supported document formats:
    - PDF: pdf
    - Word documents: doc, docx
    - Excel spreadsheets: xls, xlsx
    - PowerPoint presentations: ppt, pptx
    - Text files: txt
    - CSV files: csv
    - RTF files: rtf

    Metadata extraction:
    - Link text from <a> tags is captured and stored in metadata["link_text"]
    """

    document_extensions: list[str] = [
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "txt",
        "csv",
        "rtf",
    ]

    def __init__(
        self,
        allowed_domains: list[str] | None = None,
        document_extensions: list[str] | None = None,
    ):
        """
        Initialize HTMLDocumentMiner.

        Args:
            allowed_domains: Optional list of allowed domains. If empty/None,
                           all URLs are denied. Use ['*'] to allow all domains.
            document_extensions: Optional list of document file extensions to look for.
                               Should be lowercase without dots (e.g., ['pdf', 'docx']).
                               If None, uses default extensions.
        """
        super().__init__(allowed_domains)
        self.document_extensions = document_extensions or self.document_extensions

    def _extract_urls(self, soup: BeautifulSoup) -> list[tuple[str, dict[str, str]]]:
        """Extract document URLs and link text from HTML."""
        document_data = []

        for link in soup.find_all("a", href=True):
            link_tag = cast(Tag, link)
            href = str(link_tag.get("href", ""))

            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue

            if self._is_document_url(href):
                link_text = link_tag.get_text(separator=" ", strip=True)
                metadata = {"link_text": link_text}
                document_data.append((href, metadata))

        return document_data

    def _is_document_url(self, url: str) -> bool:
        """Check if URL points to a document file based on file extension."""
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()

        if "." in path:
            extension = path.split(".")[-1]
            return extension in self.document_extensions

        return False


class HTMLPageMiner(BaseHTMLMiner):
    """
    Extracts page URLs from HTML content for web scraping.

    Parses HTML using BeautifulSoup to find page URLs from:
    - <a> href attributes pointing to HTML pages

    Ignores links with file extensions (any link ending with .something)
    Ignores email/telephone/javascript/fragment links

    URL normalization:
    - Adds trailing slashes
    - Removes query parameters and fragments

    Dependency logic:
    - Only direct parent (immediate ancestor) is marked as dependency
    - Only applies to URL keys, non-URL keys mark all as dependencies

    Metadata extraction:
    - Link text from <a> tags is captured and stored in metadata["link_text"]
    """

    def _extract_urls(self, soup: BeautifulSoup) -> list[tuple[str, dict[str, str]]]:
        """Extract page URLs and link text from HTML."""
        page_data = []
        seen_urls = set()

        for link in soup.find_all("a", href=True):
            link_tag = cast(Tag, link)
            href = str(link_tag.get("href", ""))

            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            if self._is_page_url(href):
                normalized_href = self._normalize_url(href)

                # Skip if we've already seen this URL
                if normalized_href in seen_urls:
                    continue

                seen_urls.add(normalized_href)
                link_text = link_tag.get_text(separator=" ", strip=True)
                metadata = {"link_text": link_text}
                page_data.append((normalized_href, metadata))

        return page_data

    def mine(
        self, key: Key, resource: TextResource | BlobResource
    ) -> list[MinedResource]:
        mined_resources = []

        if not isinstance(resource, TextResource):
            return mined_resources

        base_url = self._determine_base_url(key, resource)
        soup = BeautifulSoup(resource.text, "html.parser")
        url_data = self._extract_urls(soup)

        for url, metadata in url_data:
            parsed_url = urlparse(url)
            if parsed_url.scheme:
                resolved_url = url
            elif base_url is None:
                resolved_url = url
            else:
                resolved_url = urljoin(base_url, url)
                resolved_url = self._normalize_url(resolved_url)

            if self._is_domain_allowed(resolved_url) and resolved_url:
                parsed_resolved = urlparse(resolved_url)
                if parsed_resolved.scheme:
                    mined_key = Key(type="url", value=resolved_url)
                else:
                    mined_key = Key(type="path", value=resolved_url)

                mined_resources.append(MinedResource(key=mined_key, metadata=metadata))

        return mined_resources

    def _is_page_url(self, url: str) -> bool:
        """Check if URL points to a page (no file extension)."""
        parsed_url = urlparse(url)
        path = parsed_url.path

        # If path has a file extension, it's not a page
        if path and "." in path.split("/")[-1]:
            return False

        return True

    def _normalize_url(self, url: str) -> str:
        """Normalize URL by adding trailing slash and removing query/fragment."""
        parsed = urlparse(url)

        # Remove query parameters and fragments
        path = parsed.path

        # Add trailing slash if not present and path doesn't end with a file extension
        if path and not path.endswith("/") and "." not in path.split("/")[-1]:
            path += "/"
        elif not path:
            path = "/"

        # Reconstruct URL without query/fragment
        normalized = parsed._replace(path=path, query="", fragment="").geturl()
        return normalized
