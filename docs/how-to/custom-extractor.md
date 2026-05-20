# Custom extractor

Use a custom extractor when you need to fetch data from a non-HTTP source —
a local file, a database, an internal API, etc.

## When to use this

- Reading files from the filesystem
- Fetching from an internal database using a custom key type
- Calling an authenticated API that `HTTPExtractor` can't handle

## How to write one

Subclass `BaseExtractor` and implement `extract()`. Return a `TextResource` for
text data or a `BlobResource` for binary data. Return `None` if your extractor
does not handle the given key.

```python
from pathlib import Path

from isekai.extractors import BaseExtractor
from isekai.types import BlobResource, Key, PathFileProxy, TextResource


class FileExtractor(BaseExtractor):
    def extract(
        self, key: Key, metadata: dict | None = None
    ) -> TextResource | BlobResource | None:
        # Only handle keys with type "file"
        if key.type != "file":
            return None

        path = Path(key.value)
        if not path.exists():
            return None

        # Read text files as TextResource
        if path.suffix in {".html", ".txt", ".json"}:
            return TextResource(
                mime_type="text/html",
                text=path.read_text(),
                metadata={},
            )

        # Read binary files as BlobResource
        return BlobResource(
            mime_type="application/octet-stream",
            filename=path.name,
            file_ref=PathFileProxy(path=path),
            metadata={},
        )
```

Register it on your Resource model:

```python
class Resource(AbstractResource):
    extractors = [FileExtractor(), HTTPExtractor()]
```

Isekai tries each extractor in order and uses the first one that returns a
non-`None` result.

## TextResource vs BlobResource

- Use `TextResource` when the content is readable text (HTML, JSON, plain text).
  Downstream processors receive `resource.text`.
- Use `BlobResource` when the content is binary (images, PDFs, archives).
  Downstream processors receive a file reference via `resource.file_ref`.
