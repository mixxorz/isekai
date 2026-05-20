# Extractors

Extractors fetch raw data for SEEDED resources. They are registered on your
Resource model via the `extractors` class attribute.

```python
class Resource(AbstractResource):
    extractors = [HTTPExtractor()]
```

Isekai tries each extractor in order and uses the first one that returns a
non-`None` result.

---

## BaseExtractor

```python
class BaseExtractor:
    def extract(
        self, key: Key, metadata: dict | None = None
    ) -> TextResource | BlobResource | None: ...
```

Base class for all extractors. Subclass this and implement `extract()`.
See [Custom extractor](../how-to/custom-extractor.md).

**Methods:**

| Method | Description |
|--------|-------------|
| `extract(key, metadata) -> TextResource \| BlobResource \| None` | Fetches data for the given key. Return `None` to skip this extractor. |

---

## HTTPExtractor

```python
class HTTPExtractor(BaseExtractor):
    def __init__(
        self,
        max_retries: int = 3,
        max_delay: float = 60.0,
        timeout: int = 30,
        no_retry_status_codes: set[int] | None = None,
    ): ...
```

Makes HTTP GET requests for keys with `type="url"`. Detects whether the
response is text or binary by inspecting the `Content-Type` header.

- Text responses (`text/*`, `application/json`, `application/xml`, etc.) →
  `TextResource`
- Binary responses → `BlobResource` (stored as a temporary file)

The extractor stores response headers in `resource.metadata["response_headers"]`.

**Constructor parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_retries` | `int` | `3` | Number of retry attempts on failure. |
| `max_delay` | `float` | `60.0` | Maximum delay between retries (seconds). Uses exponential backoff. |
| `timeout` | `int` | `30` | Request timeout in seconds. |
| `no_retry_status_codes` | `set[int]` | `{404}` | HTTP status codes that should not be retried. |

**Usage:**

```python
# Default settings
HTTPExtractor()

# Custom retry settings
HTTPExtractor(max_retries=5, timeout=60, no_retry_status_codes={404, 410})
```
