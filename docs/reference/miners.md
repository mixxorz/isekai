# Miners

Miners inspect EXTRACTED resources and discover related resources. They are
registered on your Resource model via the `miners` class attribute.

```python
class Resource(AbstractResource):
    miners = [HTMLImageMiner(allowed_domains=["example.com"])]
```

---

## BaseMiner

```python
class BaseMiner:
    def mine(
        self, key: Key, resource: TextResource | BlobResource
    ) -> list[MinedResource]: ...
```

Base class for all miners. Subclass this and implement `mine()`.
See [Custom miner](../how-to/custom-miner.md).

---

## BaseHTMLMiner

```python
class BaseHTMLMiner(BaseMiner):
    allowed_domains: list[str] = []
```

Base class for miners that extract URLs from HTML. Handles URL resolution,
domain filtering, and key type determination.

**Configuration:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `allowed_domains` | `list[str]` | Domains whose URLs are allowed. Use `["*"]` to allow all domains. Empty list denies all external URLs. |

Subclasses implement `_extract_urls(soup) -> list[tuple[str, dict]]` to return
raw `(url, metadata)` pairs from the parsed HTML.

---

## HTMLImageMiner

```python
class HTMLImageMiner(BaseHTMLMiner): ...
```

Extracts image URLs from HTML. Finds:

- `<img src="...">` — `src` attribute
- `<img srcset="...">` — all URLs in `srcset`
- `<source srcset="...">` inside `<picture>` — all URLs in `srcset`

Alt text is stored in `metadata["alt_text"]`.

**Usage:**

```python
HTMLImageMiner(allowed_domains=["example.com", "cdn.example.com"])
```

---

## HTMLDocumentMiner

```python
class HTMLDocumentMiner(BaseHTMLMiner):
    document_extensions: list[str] = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "rtf"]
```

Extracts document download links from HTML `<a href="...">` tags. Only
follows links whose path ends with a known document extension.

Link text is stored in `metadata["link_text"]`.

**Constructor parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `allowed_domains` | `list[str]` | Allowed domains (inherited from `BaseHTMLMiner`). |
| `document_extensions` | `list[str]` | File extensions to match (without dots). |

---

## HTMLPageMiner

```python
class HTMLPageMiner(BaseHTMLMiner): ...
```

Extracts internal page links from HTML `<a href="...">` tags. Ignores links
with file extensions, fragments, `mailto:`, `javascript:`, and `tel:` links.

URL normalization:

- Adds trailing slashes
- Removes query parameters and fragments

Link text is stored in `metadata["link_text"]`.

**Usage:**

```python
HTMLPageMiner(allowed_domains=["example.com"])
```
