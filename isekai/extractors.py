import mimetypes
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import requests

from isekai.types import BlobResource, Key, PathFileProxy, TextResource

# Text MIME types that should be treated as text data
TEXT_MIME_TYPES = {
    "application/json",
    "application/xml",
    "application/javascript",
}


class BaseExtractor:
    def extract(
        self, key: Key, metadata: dict[str, Any] | None = None
    ) -> TextResource | BlobResource | None:
        return None


class HTTPExtractor(BaseExtractor):
    def __init__(
        self,
        max_retries: int = 3,
        max_delay: float = 60.0,
        timeout: int = 30,
        no_retry_status_codes: set[int] | None = None,
    ):
        self.max_retries = max_retries
        self.max_delay = max_delay
        self.timeout = timeout
        self.no_retry_status_codes = no_retry_status_codes or {404}

    def extract(
        self, key: Key, metadata: dict[str, Any] | None = None
    ) -> TextResource | BlobResource | None:
        # We only handle keys of type "url"
        if key.type != "url":
            return None

        url = key.value

        response = self._make_request_with_backoff(url)

        content_type = response.headers.get("Content-Type", "application/octet-stream")
        mime_type = content_type.split(";")[0]
        data_type = self._detect_data_type(mime_type)

        # Create metadata with response headers
        metadata = {"response_headers": dict(response.headers)}

        if data_type == "text":
            return TextResource(
                mime_type=mime_type, text=response.text, metadata=metadata
            )
        else:
            filename = self._infer_filename(url, response, mime_type)
            # Create a temporary file to store the blob data
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}")
            temp_file.write(response.content)
            temp_file.close()

            return BlobResource(
                mime_type=mime_type,
                filename=filename,
                file_ref=PathFileProxy(path=Path(temp_file.name)),
                metadata=metadata,
            )

    def _make_request_with_backoff(self, url: str) -> requests.Response:
        """Make HTTP request with exponential backoff retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                # Don't retry configured status codes, raise immediately
                if (
                    e.response is not None
                    and e.response.status_code in self.no_retry_status_codes
                ):
                    raise e

                if attempt < self.max_retries:
                    delay = min(2**attempt, self.max_delay)
                    time.sleep(delay)
                    continue

                # Last attempt failed, re-raise the exception
                raise e
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    delay = min(2**attempt, self.max_delay)
                    time.sleep(delay)
                    continue

                # Last attempt failed, re-raise the exception
                raise e

        # This is mostly for type checkers; we should never reach here
        raise RuntimeError("Unreachable code reached in _make_request_with_backoff")

    def _detect_data_type(self, content_type: str) -> Literal["text", "blob"]:
        # Check if it's a text MIME type
        if content_type.startswith("text/") or content_type in TEXT_MIME_TYPES:
            return "text"

        # Otherwise, treat it as binary data
        return "blob"

    def _infer_filename(
        self, url: str, response: requests.Response, mime_type: str
    ) -> str:
        """Infer filename from URL, response headers, or MIME type."""

        # 1. Try Content-Disposition header
        content_disposition = response.headers.get("Content-Disposition", "")
        if content_disposition:
            filename_match = re.search(
                r'filename[*]?=(?:"([^"]+)"|\'([^\']+)\'|([^;\s]+))',
                content_disposition,
            )
            if filename_match:
                filename = (
                    filename_match.group(1)
                    or filename_match.group(2)
                    or filename_match.group(3)
                )
                if filename:
                    return filename

        # 2. Try URL path
        parsed_url = urlparse(url)
        if parsed_url.path:
            path_parts = parsed_url.path.split("/")
            for part in reversed(path_parts):
                if part and "." in part:
                    return part

        # 3. Generate from MIME type
        extension = mimetypes.guess_extension(mime_type)
        if extension:
            # Remove the leading dot and handle some common cases
            extension = extension.lstrip(".")
            # mimetypes sometimes returns .jpe for image/jpeg, prefer .jpg
            if extension == "jpe":
                extension = "jpg"
        else:
            extension = "bin"

        # Try to use the last path segment as base filename
        parsed_url = urlparse(url)
        if parsed_url.path:
            path_parts = parsed_url.path.strip("/").split("/")
            if path_parts and path_parts[-1]:
                base_name = path_parts[-1]
                # Remove existing extension if present
                if "." in base_name:
                    base_name = base_name.rsplit(".", 1)[0]
                return f"{base_name}.{extension}"

        return f"file.{extension}"
