from types import NoneType
from typing import Literal

import requests

from isekai.types import ResourceData


class BaseExtractor:
    def extract(self, key: str) -> ResourceData | NoneType:
        return None


class HTTPExtractor(BaseExtractor):
    def extract(self, key: str) -> ResourceData | NoneType:
        if not key.startswith("url:"):
            return super().extract(key)

        url = key.lstrip("url:")

        response = requests.get(url)

        content_type = response.headers.get("Content-Type", "application/octet-stream")
        mime_type = content_type.split(";")[0]
        data_type = self._detect_data_type(mime_type)

        return ResourceData(
            mime_type=mime_type,
            data_type=data_type,
            data=response.text if data_type == "text" else response.content,
        )

    def _detect_data_type(self, content_type: str) -> Literal["text", "blob"]:
        if content_type.startswith("text/"):
            return "text"
        elif "application/json" in content_type:
            return "text"
        else:
            return "blob"
