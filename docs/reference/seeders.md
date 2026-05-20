# Seeders

Seeders generate the initial set of resources. They are registered on your
Resource model via the `seeders` class attribute.

```python
class Resource(AbstractResource):
    seeders = [CSVSeeder(csv_filename="urls.csv")]
```

---

## BaseSeeder

```python
class BaseSeeder:
    def seed(self) -> list[SeededResource]: ...
```

Base class for all seeders. Subclass this and implement `seed()` to create
a custom seeder. See [Custom seeder](../how-to/custom-seeder.md).

**Methods:**

| Method | Description |
|--------|-------------|
| `seed() -> list[SeededResource]` | Returns the list of resources to seed. Default returns `[]`. |

---

## CSVSeeder

```python
class CSVSeeder(BaseSeeder):
    csv_filename: str | None = None
```

Reads resource keys from a CSV file. The file must have `type` and `value`
columns.

**Example CSV (`urls.csv`):**

```csv
type,value
url,https://example.com/page-1/
url,https://example.com/page-2/
```

**Configuration:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `csv_filename` | `str` | Path to the CSV file. Required. |

**Usage:**

```python
# Via constructor
CSVSeeder(csv_filename="urls.csv")

# Via subclass
class MySeeder(CSVSeeder):
    csv_filename = "urls.csv"
```

---

## SitemapSeeder

```python
class SitemapSeeder(BaseSeeder):
    sitemap_url: str | None = None
```

Fetches an XML sitemap and creates one `url:` resource per `<loc>` entry.

**Configuration:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `sitemap_url` | `str` | URL of the XML sitemap. Required. |

**Usage:**

```python
# Via constructor
SitemapSeeder(sitemap_url="https://example.com/sitemap.xml")

# Via subclass
class MySeeder(SitemapSeeder):
    sitemap_url = "https://example.com/sitemap.xml"
```
