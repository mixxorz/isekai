# Isekai Docs Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up a Zensical-powered documentation site for isekai-django, write comprehensive docs for library users, and deploy to GitHub Pages at `https://mitchel.me/isekai`.

**Architecture:** Zensical static site with `zensical.toml` at repo root, Markdown content in `docs/`, and a GitHub Actions workflow that builds and deploys to GitHub Pages on push to `main`. Navigation has five top-level sections: Get started, Concepts, Tutorial, How-to guides, and Reference.

**Tech Stack:** Zensical (static site generator), Markdown, GitHub Actions (`actions/upload-pages-artifact`, `actions/deploy-pages`), uv for dependency management.

---

### Task 1: Install Zensical and create zensical.toml

**Files:**
- Modify: `pyproject.toml`
- Create: `zensical.toml`

- [ ] **Step 1: Add zensical to dev dependencies**

Run:
```bash
uv add --dev zensical
```

Expected output: zensical added to `[dependency-groups] dev` in `pyproject.toml`.

- [ ] **Step 2: Verify zensical is available**

Run:
```bash
uv run zensical --version
```

Expected: prints a version number without errors.

- [ ] **Step 3: Create zensical.toml at repo root**

Create `/Users/mixxorz/Projects/isekai/zensical.toml` with this content:

```toml
[project]
site_name = "Isekai"
site_url = "https://mitchel.me/isekai"
site_description = "A Django ETL framework for migrating content into Django models using a pluggable pipeline."
site_author = "Mitchel Cabuloy"
copyright = "Copyright &copy; 2025 Mitchel Cabuloy"

nav = [
  { "Get started" = "index.md" },
  { "Concepts" = "concepts.md" },
  { "Tutorial" = "tutorial.md" },
  { "How-to guides" = [
    { "Overview" = "how-to/index.md" },
    { "Custom seeder" = "how-to/custom-seeder.md" },
    { "Custom extractor" = "how-to/custom-extractor.md" },
    { "Custom miner" = "how-to/custom-miner.md" },
    { "Custom transformer" = "how-to/custom-transformer.md" },
    { "Custom loader" = "how-to/custom-loader.md" },
  ]},
  { "Reference" = [
    { "Overview" = "reference/index.md" },
    { "Seeders" = "reference/seeders.md" },
    { "Extractors" = "reference/extractors.md" },
    { "Miners" = "reference/miners.md" },
    { "Transformers" = "reference/transformers.md" },
    { "Loaders" = "reference/loaders.md" },
    { "Wagtail" = "reference/wagtail.md" },
    { "Types" = "reference/types.md" },
  ]},
]

[project.theme]
language = "en"
features = [
  "announce.dismiss",
  "content.code.annotate",
  "content.code.copy",
  "content.code.select",
  "content.footnote.tooltips",
  "content.tabs.link",
  "content.tooltips",
  "navigation.footer",
  "navigation.indexes",
  "navigation.instant",
  "navigation.instant.prefetch",
  "navigation.path",
  "navigation.sections",
  "navigation.top",
  "navigation.tracking",
  "search.highlight",
]

[[project.theme.palette]]
scheme = "default"
toggle.icon = "lucide/sun"
toggle.name = "Switch to dark mode"

[[project.theme.palette]]
scheme = "slate"
toggle.icon = "lucide/moon"
toggle.name = "Switch to light mode"

[project.theme.icon]
logo = "lucide/package"

[project.repo]
url = "https://github.com/mixxorz/isekai"
name = "mixxorz/isekai"

[project.markdown_extensions.abbr]
[project.markdown_extensions.admonition]
[project.markdown_extensions.attr_list]
[project.markdown_extensions.def_list]
[project.markdown_extensions.footnotes]
[project.markdown_extensions.md_in_html]
[project.markdown_extensions.toc]
permalink = true
[project.markdown_extensions.pymdownx.betterem]
[project.markdown_extensions.pymdownx.caret]
[project.markdown_extensions.pymdownx.details]
[project.markdown_extensions.pymdownx.highlight]
anchor_linenums = true
line_spans = "__span"
pygments_lang_class = true
[project.markdown_extensions.pymdownx.inlinehilite]
[project.markdown_extensions.pymdownx.keys]
[project.markdown_extensions.pymdownx.mark]
[project.markdown_extensions.pymdownx.smartsymbols]
[project.markdown_extensions.pymdownx.superfences]
custom_fences = [
  { name = "mermaid", class = "mermaid", format = "pymdownx.superfences.fence_code_format" }
]
[project.markdown_extensions.pymdownx.tabbed]
alternate_style = true
combine_header_slug = true
[project.markdown_extensions.pymdownx.tasklist]
custom_checkbox = true
[project.markdown_extensions.pymdownx.tilde]
```

- [ ] **Step 4: Verify zensical can parse the config**

Run:
```bash
uv run zensical build --help
```

Expected: help text printed, no config errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock zensical.toml
git commit -m "chore: install zensical and add zensical.toml"
```

---

### Task 2: Write docs/index.md (Get started)

**Files:**
- Create: `docs/index.md`

- [ ] **Step 1: Create docs/index.md**

Create `/Users/mixxorz/Projects/isekai/docs/index.md`:

```markdown
---
icon: lucide/rocket
---

# Get started

Isekai is a Django library for migrating content into Django models using a
pluggable ETL pipeline. It handles the plumbing — fetching pages, managing
resource state, resolving cross-references — so you can focus on writing the
code that is specific to your migration.

## Install

```bash
pip install isekai-django
```

If you're migrating into Wagtail, install the optional Wagtail extra:

```bash
pip install "isekai-django[wagtail]"
```

## Quick example

Here's the minimal setup for a pipeline that seeds URLs from a CSV, fetches
each page over HTTP, transforms the HTML into a Django model, and saves it.

**1. Create your Resource model:**

```python
# myapp/models.py
from isekai.models import AbstractResource
from isekai.extractors import HTTPExtractor
from isekai.seeders import CSVSeeder
from isekai.transformers import BaseTransformer
from isekai.loaders import ModelLoader
from isekai.types import Key, Spec, TextResource, BlobResource


class MyTransformer(BaseTransformer):
    def transform(self, key: Key, resource: TextResource | BlobResource) -> Spec | None:
        return Spec(
            content_type="myapp.article",
            attributes={"title": "Imported article", "body": resource.text},
        )


class Resource(AbstractResource):
    seeders = [CSVSeeder(csv_filename="urls.csv")]
    extractors = [HTTPExtractor()]
    transformers = [MyTransformer()]
    loaders = [ModelLoader()]

    class Meta:
        app_label = "myapp"
```

**2. Run the pipeline:**

```bash
python manage.py isekai
```

Isekai seeds resources from the CSV, fetches each URL, runs your transformer,
and loads the resulting objects into the database.

## Next steps

- Read [Concepts](concepts.md) to understand how the pipeline works.
- Follow the [Tutorial](tutorial.md) for a complete real-world walkthrough.
- Browse [How-to guides](how-to/index.md) for task-specific instructions.
- See the [Reference](reference/index.md) for full API documentation.
```

- [ ] **Step 2: Verify the file renders**

Run:
```bash
uv run zensical build 2>&1 | head -30
```

Expected: build succeeds or shows only "missing file" warnings for pages not yet created (not a config parse error).

- [ ] **Step 3: Commit**

```bash
git add docs/index.md
git commit -m "docs: add get started page"
```

---

### Task 3: Write docs/concepts.md

**Files:**
- Create: `docs/concepts.md`

- [ ] **Step 1: Create docs/concepts.md**

Create `/Users/mixxorz/Projects/isekai/docs/concepts.md`:

```markdown
---
icon: lucide/layers
---

# Concepts

## The Resource

A **Resource** represents a single piece of data to migrate. Each resource has
a unique **Key** — a `type:value` string like `url:https://example.com` or
`file:document.pdf` — and tracks its own progress through the pipeline.

Every resource eventually resolves to one Django model instance. If your
pipeline migrates 500 pages, you end up with 500 Resource rows in the database,
each pointing at the page it created.

## The Key

A `Key` is a `type:value` pair:

```python
Key(type="url", value="https://example.com/about/")
# String form: "url:https://example.com/about/"
```

Built-in key types are `url` (HTTP resources) and `path` (local filesystem
paths). You can define any type you like in a custom seeder.

## The Pipeline

Resources move through five stages in order:

```
SEEDED → EXTRACTED → MINED → TRANSFORMED → LOADED
```

Each stage is handled by a **processor** registered on your Resource model.

### 1. Seed

Seeders create the initial set of resources by generating Keys. The
`CSVSeeder` reads a `type,value` CSV. The `SitemapSeeder` parses an XML
sitemap. You can also write a custom seeder to generate keys from any source.

### 2. Extract

Extractors fetch raw data for each SEEDED resource and store it on the
resource. `HTTPExtractor` makes an HTTP GET request and stores the response
as text (for HTML/JSON) or as a file (for images, PDFs, etc.).

After extraction, a resource holds its raw data and transitions to EXTRACTED.

### 3. Mine

Miners inspect an EXTRACTED resource and discover related resources. For
example, `HTMLImageMiner` finds all `<img>` tags and creates new SEEDED
resources for each image URL. Those new resources then flow through the
pipeline themselves.

Mining is optional — if none of your resources need it, you can omit miners.

### 4. Transform

Transformers read a MINED resource and produce a **Spec**: a model-shaped
description of the object to create. A Spec names the target content type and
provides its field values.

Field values in a Spec can include **refs** — references to other resources or
to existing database objects:

- `ResourceRef(key)` — points at another resource in this pipeline; resolved
  to the created model instance during Load.
- `BlobRef(key)` — points at a blob resource; resolved to the uploaded file
  during Load.
- `ModelRef("app.Model", pk=42)` — points at an existing database object;
  resolved immediately during Load.

### 5. Load

Loaders take all TRANSFORMED resources and create the Django model instances.
`ModelLoader` handles the dependency ordering automatically: it creates all
objects, sets temporary values for cross-references, then resolves them in a
second pass.

The Wagtail `PageLoader` extends `ModelLoader` to add Wagtail-specific tree
placement, so pages are created under the right parent.

## Processors

Processors are registered on the Resource model as class attributes:

```python
class Resource(AbstractResource):
    seeders = [CSVSeeder(csv_filename="urls.csv")]
    extractors = [HTTPExtractor()]
    miners = [HTMLImageMiner(allowed_domains=["example.com"])]
    transformers = [MyTransformer()]
    loaders = [ModelLoader()]
```

Each list can contain multiple processors. Isekai tries them in order and uses
the first one that returns a result for a given resource.

## The AbstractResource model

Your app must subclass `AbstractResource` to create a concrete Resource model:

```python
from isekai.models import AbstractResource

class Resource(AbstractResource):
    class Meta:
        app_label = "myapp"
```

Isekai discovers your model at runtime using `get_resource_model()`. There
must be exactly one concrete subclass of `AbstractResource` in your project.
```

- [ ] **Step 2: Commit**

```bash
git add docs/concepts.md
git commit -m "docs: add concepts page"
```

---

### Task 4: How-to guides

**Files:**
- Create: `docs/how-to/index.md`
- Create: `docs/how-to/custom-seeder.md`
- Create: `docs/how-to/custom-extractor.md`
- Create: `docs/how-to/custom-miner.md`
- Create: `docs/how-to/custom-transformer.md`
- Create: `docs/how-to/custom-loader.md`

- [ ] **Step 1: Create docs/how-to/index.md**

```markdown
---
icon: lucide/book-open
---

# How-to guides

Task-focused guides for common Isekai customization scenarios.

- [Custom seeder](custom-seeder.md) — generate resource keys from any source
- [Custom extractor](custom-extractor.md) — fetch data from non-HTTP sources
- [Custom miner](custom-miner.md) — discover related resources from extracted data
- [Custom transformer](custom-transformer.md) — produce a Spec from extracted data
- [Custom loader](custom-loader.md) — create Django objects in a custom way
```

- [ ] **Step 2: Create docs/how-to/custom-seeder.md**

```markdown
# Custom seeder

Use a custom seeder when you want to generate resource keys from a source that
the built-in seeders don't support — a database query, an API response, a
directory of files, etc.

## When to use this

- Seeding from a database table
- Seeding from an API that lists items to migrate
- Seeding from a directory of files

## How to write one

Subclass `BaseSeeder` and implement `seed()`. Return a list of `SeededResource`
objects, each wrapping a `Key`.

```python
from isekai.seeders import BaseSeeder
from isekai.types import Key, SeededResource


class DatabaseSeeder(BaseSeeder):
    def seed(self) -> list[SeededResource]:
        from myapp.models import LegacyArticle

        resources = []
        for article in LegacyArticle.objects.all():
            key = Key(type="db", value=str(article.pk))
            resources.append(SeededResource(key=key, metadata={"title": article.title}))
        return resources
```

Register it on your Resource model:

```python
class Resource(AbstractResource):
    seeders = [DatabaseSeeder()]
```

## Key types

The `type` field of a `Key` is a free-form string. It is used by extractors to
decide whether they can handle a given key. Pick a type that matches what your
extractor expects. For example, `HTTPExtractor` only processes keys with
`type="url"`.

## Passing metadata

The `metadata` dict on `SeededResource` is stored on the Resource and available
to later processors. Use it to carry any context you want downstream.
```

- [ ] **Step 3: Create docs/how-to/custom-extractor.md**

```markdown
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
```

- [ ] **Step 4: Create docs/how-to/custom-miner.md**

```markdown
# Custom miner

Use a custom miner when you want to discover related resources from extracted
content — links to follow, images to download, sub-pages to process.

## When to use this

- Extracting linked resources from a custom data format (XML, JSON, etc.)
- Filtering which URLs to follow with custom logic
- Extracting embedded resources that the built-in miners don't handle

## How to write one

Subclass `BaseMiner` and implement `mine()`. Return a list of `MinedResource`
objects for each discovered resource. Return an empty list if there is nothing
to mine.

```python
import json

from isekai.miners import BaseMiner
from isekai.types import BlobResource, Key, MinedResource, TextResource


class JSONLinkMiner(BaseMiner):
    def mine(
        self, key: Key, resource: TextResource | BlobResource
    ) -> list[MinedResource]:
        if not isinstance(resource, TextResource):
            return []

        if resource.mime_type != "application/json":
            return []

        try:
            data = json.loads(resource.text)
        except ValueError:
            return []

        mined = []
        for item in data.get("links", []):
            mined_key = Key(type="url", value=item["url"])
            mined.append(MinedResource(key=mined_key, metadata={"label": item.get("label", "")}))

        return mined
```

Register it on your Resource model:

```python
class Resource(AbstractResource):
    miners = [JSONLinkMiner()]
```

## Notes

- Miners run after extraction. The `resource` argument contains the raw
  extracted data.
- New resources created by miners start at SEEDED and flow through the full
  pipeline.
- The `metadata` dict on `MinedResource` is stored on the new resource and
  available to downstream processors.
```

- [ ] **Step 5: Create docs/how-to/custom-transformer.md**

```markdown
# Custom transformer

A transformer reads an extracted resource and produces a **Spec** — a
description of the Django model object to create.

## When to use this

Always. Every pipeline needs at least one custom transformer to tell Isekai
what model to create and what fields to populate.

## How to write one

Subclass `BaseTransformer` and implement `transform()`. Return a `Spec` or
`None`. Return `None` if your transformer does not handle the given resource
(e.g., wrong MIME type).

```python
from bs4 import BeautifulSoup

from isekai.transformers import BaseTransformer
from isekai.types import BlobResource, Key, Spec, TextResource


class ArticleTransformer(BaseTransformer):
    def transform(
        self, key: Key, resource: TextResource | BlobResource
    ) -> Spec | None:
        if not isinstance(resource, TextResource):
            return None

        if "text/html" not in resource.mime_type:
            return None

        soup = BeautifulSoup(resource.text, "html.parser")
        title = soup.find("h1")

        return Spec(
            content_type="myapp.article",
            attributes={
                "title": title.get_text(strip=True) if title else "Untitled",
                "body": str(soup.find("main") or soup.body or ""),
                "source_url": key.value,
            },
        )
```

Register it on your Resource model:

```python
class Resource(AbstractResource):
    transformers = [ArticleTransformer()]
```

## The Spec object

`Spec(content_type, attributes)` describes one model instance:

- `content_type` — Django app label and model name, e.g. `"myapp.article"`.
- `attributes` — dict of field names to values. Values can be plain Python
  types, or any of the ref types: `ResourceRef`, `BlobRef`, `ModelRef`.

## Using refs in a Spec

Cross-reference another resource in this pipeline:

```python
from isekai.types import BlobRef, ModelRef, ResourceRef

Spec(
    content_type="myapp.article",
    attributes={
        "title": "My article",
        # Attach an image resource from this same pipeline
        "hero_image": BlobRef(Key(type="url", value="https://example.com/hero.jpg")),
        # Point at the parent section (also migrated in this pipeline)
        "section": ResourceRef(Key(type="url", value="https://example.com/section/")),
        # Point at an existing author in the database
        "author": ModelRef("myapp.author", slug="jane-smith"),
    },
)
```
```

- [ ] **Step 6: Create docs/how-to/custom-loader.md**

```markdown
# Custom loader

Use a custom loader when `ModelLoader` doesn't cover your use case — for
example, when you need to call a custom save method, use a manager method, or
apply extra logic after creation.

## When to use this

- Calling `Page.add_child()` or similar tree-insert methods (see `PageLoader`)
- Using a custom manager method instead of `Model(**fields).save()`
- Applying post-save logic

## How to write one

Subclass `BaseLoader` and implement `load()`. Return a list of
`(Key, model_instance)` tuples — one for each spec that was processed.

```python
from django.db import models

from isekai.loaders import BaseLoader
from isekai.types import Key, Resolver, Spec


class CustomLoader(BaseLoader):
    def load(
        self, specs: list[tuple[Key, Spec]], resolver: Resolver
    ) -> list[tuple[Key, models.Model]]:
        results = []
        for key, spec in specs:
            # Only handle a specific content type
            if spec.content_type != "myapp.specialarticle":
                continue

            from myapp.models import SpecialArticle

            obj = SpecialArticle.create_via_manager(**spec.attributes)
            results.append((key, obj))

        return results
```

Register it on your Resource model:

```python
class Resource(AbstractResource):
    loaders = [CustomLoader(), ModelLoader()]
```

Isekai tries each loader in order. A loader that returns an empty list is
skipped and the next one is tried. `ModelLoader` is a good fallback for any
specs your custom loader doesn't handle.

## Notes

- The `resolver` argument resolves `BlobRef`, `ResourceRef`, and `ModelRef`
  values in spec attributes. If you process specs manually, call
  `resolver(ref)` to get the resolved value.
- For Wagtail pages, use the built-in `PageLoader` from
  `isekai.contrib.wagtail.loaders` instead of writing a custom loader.
```

- [ ] **Step 7: Commit**

```bash
git add docs/how-to/
git commit -m "docs: add how-to guides"
```

---

### Task 5: Reference — Seeders, Extractors, Miners

**Files:**
- Create: `docs/reference/index.md`
- Create: `docs/reference/seeders.md`
- Create: `docs/reference/extractors.md`
- Create: `docs/reference/miners.md`

- [ ] **Step 1: Create docs/reference/index.md**

```markdown
---
icon: lucide/book
---

# Reference

Complete API reference for all built-in Isekai classes.

- [Seeders](seeders.md) — `BaseSeeder`, `CSVSeeder`, `SitemapSeeder`
- [Extractors](extractors.md) — `BaseExtractor`, `HTTPExtractor`
- [Miners](miners.md) — `BaseMiner`, `BaseHTMLMiner`, `HTMLImageMiner`, `HTMLDocumentMiner`, `HTMLPageMiner`
- [Transformers](transformers.md) — `BaseTransformer`
- [Loaders](loaders.md) — `BaseLoader`, `ModelLoader`
- [Wagtail](wagtail.md) — `PageLoader`, `ImageTransformer`, `DocumentTransformer`
- [Types](types.md) — `Key`, `Spec`, `ResourceRef`, `BlobRef`, `ModelRef`, and more
```

- [ ] **Step 2: Create docs/reference/seeders.md**

```markdown
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
```

- [ ] **Step 3: Create docs/reference/extractors.md**

```markdown
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
```

- [ ] **Step 4: Create docs/reference/miners.md**

```markdown
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
```

- [ ] **Step 5: Commit**

```bash
git add docs/reference/
git commit -m "docs: add reference pages for seeders, extractors, miners"
```

---

### Task 6: Reference — Transformers, Loaders, Wagtail, Types

**Files:**
- Create: `docs/reference/transformers.md`
- Create: `docs/reference/loaders.md`
- Create: `docs/reference/wagtail.md`
- Create: `docs/reference/types.md`

- [ ] **Step 1: Create docs/reference/transformers.md**

```markdown
# Transformers

Transformers read an EXTRACTED resource and produce a `Spec` describing the
Django model object to create. They are registered on your Resource model via
the `transformers` class attribute.

```python
class Resource(AbstractResource):
    transformers = [MyTransformer()]
```

Isekai tries each transformer in order and uses the first one that returns a
non-`None` result.

---

## BaseTransformer

```python
class BaseTransformer:
    def transform(
        self, key: Key, resource: TextResource | BlobResource
    ) -> Spec | None: ...
```

Base class for all transformers. Subclass this and implement `transform()`.
See [Custom transformer](../how-to/custom-transformer.md).

**Methods:**

| Method | Description |
|--------|-------------|
| `transform(key, resource) -> Spec \| None` | Produces a `Spec` for the given resource. Return `None` to skip this transformer. |
```

- [ ] **Step 2: Create docs/reference/loaders.md**

```markdown
# Loaders

Loaders take TRANSFORMED resources and create Django model instances. They are
registered on your Resource model via the `loaders` class attribute.

```python
class Resource(AbstractResource):
    loaders = [ModelLoader()]
```

Isekai tries each loader in order. A loader returns an empty list to indicate
it did not handle a spec; the next loader is tried.

---

## BaseLoader

```python
class BaseLoader:
    def load(
        self, specs: list[tuple[Key, Spec]], resolver: Resolver
    ) -> list[tuple[Key, models.Model]]: ...
```

Base class for all loaders. Subclass this and implement `load()`.
See [Custom loader](../how-to/custom-loader.md).

---

## ModelLoader

```python
class ModelLoader(BaseLoader): ...
```

Creates Django model instances from `(Key, Spec)` tuples. Handles:

- **Cross-reference resolution** — `ResourceRef`, `BlobRef`, and `ModelRef`
  values in spec attributes are resolved to model instances or files.
- **Dependency ordering** — objects are created in the right order when specs
  reference each other.
- **Two-phase creation** — objects with circular FK dependencies are created
  with temporary values, then updated in a second pass.
- **M2M fields** — `ManyToManyField` and Wagtail `ParentalManyToManyField`
  values are set after all objects exist.
- **JSON fields** — nested refs in JSON fields are resolved after creation.
- **String interpolation** — refs embedded in string fields via `ref()` are
  resolved after creation.

All objects are created inside a single database transaction with constraint
checks disabled until the end.

**Usage:**

```python
ModelLoader()
```

No configuration is required. Register it as the last loader (or only loader)
on your Resource model.
```

- [ ] **Step 3: Create docs/reference/wagtail.md**

```markdown
# Wagtail

Isekai includes Wagtail-specific processors in `isekai.contrib.wagtail`. Install
the Wagtail extra to use them:

```bash
pip install "isekai-django[wagtail]"
```

---

## PageLoader

```python
from isekai.contrib.wagtail.loaders import PageLoader
```

Extends `ModelLoader` to support Wagtail page tree placement. Pages are created
under a parent page specified in the spec.

**Usage:**

Register `PageLoader` in your `loaders` list:

```python
from isekai.contrib.wagtail.loaders import PageLoader
from isekai.loaders import ModelLoader

class Resource(AbstractResource):
    loaders = [PageLoader(), ModelLoader()]
```

In your transformer, add the parent page to the spec using the special
`__wagtail_parent_page` key:

```python
from isekai.contrib.wagtail.loaders import PageLoader
from isekai.types import Key, ResourceRef, Spec

Spec(
    content_type="myapp.casestudypage",
    attributes={
        "title": "My Case Study",
        "slug": "my-case-study",
        # The parent page — either an integer PK or a ResourceRef
        "__wagtail_parent_page": 3,  # Wagtail page PK
    },
)
```

The `__wagtail_parent_page` value can be:

- An `int` — the PK of the parent page
- A `ResourceRef` — a reference to another resource in this pipeline (useful
  when both parent and child pages are being migrated together)

---

## ImageTransformer

```python
from isekai.contrib.wagtail.transformers import ImageTransformer
```

Transforms blob resources into Wagtail `Image` specs. Only processes resources
whose MIME type is in the allowed list.

**Default allowed MIME types:** `image/avif`, `image/gif`, `image/jpeg`,
`image/png`, `image/webp`, `image/svg+xml`.

**Constructor parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `allowed_mime_types` | `list[str]` | Override the allowed MIME type list. |

**Usage:**

```python
from isekai.contrib.wagtail.transformers import ImageTransformer

class Resource(AbstractResource):
    transformers = [ImageTransformer(), MyPageTransformer()]
```

The produced Spec sets `title` to the filename and `file` to a `BlobRef`
pointing at the image resource.

---

## DocumentTransformer

```python
from isekai.contrib.wagtail.transformers import DocumentTransformer
```

Transforms blob resources into Wagtail `Document` specs.

**Default allowed MIME types:** PDF, Word, Excel, PowerPoint, text, CSV, RTF,
and ZIP archive types.

**Constructor parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `allowed_mime_types` | `list[str]` | Override the allowed MIME type list. |

**Usage:**

```python
from isekai.contrib.wagtail.transformers import DocumentTransformer

class Resource(AbstractResource):
    transformers = [DocumentTransformer(), MyPageTransformer()]
```
```

- [ ] **Step 4: Create docs/reference/types.md**

```markdown
# Types

Core data types used throughout Isekai.

---

## Key

```python
@dataclass(frozen=True, slots=True)
class Key:
    type: str
    value: str
```

Uniquely identifies a resource. `type` is a free-form string (e.g. `"url"`,
`"file"`, `"db"`). `value` is the resource identifier within that type.

```python
Key(type="url", value="https://example.com/about/")
str(key)  # "url:https://example.com/about/"
Key.from_string("url:https://example.com/about/")
```

---

## Spec

```python
@dataclass(frozen=True, slots=True)
class Spec:
    content_type: str
    attributes: dict[str, Any]
```

Describes a Django model instance to create. `content_type` is
`"app_label.ModelName"`. `attributes` maps field names to values.

Attribute values may include `ResourceRef`, `BlobRef`, and `ModelRef` objects
which are resolved to model instances or files during Load.

---

## ResourceRef

```python
class ResourceRef:
    def __init__(self, key: Key, attr_path: tuple[str, ...] = ()): ...
```

Reference to another resource in the current pipeline. Resolved to the created
model instance during Load. Supports lazy attribute chaining:

```python
ref = ResourceRef(Key(type="url", value="https://example.com/section/"))
ref.pk         # resolves to section_instance.pk
ref.slug       # resolves to section_instance.slug
```

---

## BlobRef

```python
@dataclass(frozen=True, slots=True)
class BlobRef:
    key: Key
```

Reference to a blob resource. Resolved to a file upload during Load. Used for
file fields:

```python
Spec(
    content_type="wagtailimages.image",
    attributes={
        "title": "Hero image",
        "file": BlobRef(Key(type="url", value="https://example.com/hero.jpg")),
    },
)
```

---

## ModelRef

```python
class ModelRef:
    def __init__(self, content_type: str, attr_path: tuple[str, ...] = (), **lookup_kwargs): ...
```

Reference to an existing database object (not being migrated). Resolved
immediately during Load by querying the database. Supports lazy attribute
chaining:

```python
ModelRef("myapp.author", slug="jane-smith")
ModelRef("myapp.author", slug="jane-smith").pk  # resolves to author.pk
```

---

## TextResource

```python
@dataclass(frozen=True, slots=True)
class TextResource:
    mime_type: str
    text: str
    metadata: Mapping[str, Any]
```

Holds text data from an extractor. Passed to miners and transformers.

---

## BlobResource

```python
@dataclass(frozen=True, slots=True)
class BlobResource:
    mime_type: str
    filename: str
    file_ref: FileProxy
    metadata: Mapping[str, Any]
```

Holds binary data from an extractor. `file_ref` provides access to the file
contents.

---

## SeededResource

```python
@dataclass(frozen=True, slots=True)
class SeededResource:
    key: Key
    metadata: Mapping[str, Any]
```

Returned by seeders. The `metadata` dict is stored on the Resource and
available to later processors.

---

## MinedResource

```python
@dataclass(frozen=True, slots=True)
class MinedResource:
    key: Key
    metadata: Mapping[str, Any]
```

Returned by miners. Creates a new SEEDED resource that flows through the
pipeline.

---

## ref()

```python
def ref(reference: ResourceRef | ModelRef | BlobRef) -> str: ...
```

Embeds a ref in a string for interpolation. Use this in f-strings to safely
include a ref in a text field:

```python
from isekai.types import ResourceRef, ref

Spec(
    content_type="myapp.article",
    attributes={
        "body": f"Read more at {ref(ResourceRef(key).get_absolute_url())}",
    },
)
```

The loader resolves the ref and replaces the placeholder with the resolved
value when saving the field.
```

- [ ] **Step 5: Commit**

```bash
git add docs/reference/transformers.md docs/reference/loaders.md docs/reference/wagtail.md docs/reference/types.md
git commit -m "docs: add reference pages for transformers, loaders, wagtail, types"
```

---

### Task 7: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README.md content**

Replace the full content of `README.md` with:

```markdown
# ISEKAI

**ISEKAI** is a general-purpose ETL framework for Django. It helps you migrate
any data — including files — from any source into your Django models using a
clear, pluggable pipeline.

## Documentation

Full documentation at **[mitchel.me/isekai](https://mitchel.me/isekai)**.

- [Get started](https://mitchel.me/isekai/) — install and quick example
- [Concepts](https://mitchel.me/isekai/concepts/) — how the pipeline works
- [Tutorial](https://mitchel.me/isekai/tutorial/) — real-world walkthrough
- [Reference](https://mitchel.me/isekai/reference/) — full API docs

## Install

```bash
pip install isekai-django
pip install "isekai-django[wagtail]"  # Wagtail support
```

## License

MIT
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README to link to docs site"
```

---

### Task 8: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/docs.yml`

- [ ] **Step 1: Check if .github/workflows exists**

Run:
```bash
ls .github/workflows/
```

Expected: directory exists (it's a real repo with CI). If it doesn't exist, create it: `mkdir -p .github/workflows`.

- [ ] **Step 2: Create .github/workflows/docs.yml**

Create `/Users/mixxorz/Projects/isekai/.github/workflows/docs.yml`:

```yaml
name: Deploy docs

on:
  push:
    branches:
      - main

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install dependencies
        run: uv sync --group dev

      - name: Build docs
        run: uv run zensical build

      - name: Upload pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site/

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 3: Verify the workflow YAML is valid**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/docs.yml'))" && echo "YAML valid"
```

Expected: `YAML valid`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/docs.yml
git commit -m "ci: add GitHub Actions workflow to deploy docs to GitHub Pages"
```

---

### Task 9: Add site/ to .gitignore and do a local build

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add site/ to .gitignore**

Check if `site/` is already in `.gitignore`:
```bash
grep "site/" .gitignore
```

If not found, add it:
```bash
echo "site/" >> .gitignore
```

- [ ] **Step 2: Do a full local build to verify everything works**

Run:
```bash
uv run zensical build 2>&1
```

Expected: build completes successfully. Warnings about missing nav pages are acceptable only if all pages listed in `zensical.toml` nav actually exist (they should all exist after Tasks 2–6).

- [ ] **Step 3: Spot-check the output**

Run:
```bash
ls site/
```

Expected: `index.html`, `concepts/`, `tutorial/`, `how-to/`, `reference/` directories.

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: add site/ to .gitignore"
```

---

### Task 10: Enable GitHub Pages in repo settings

This task is manual — it cannot be automated via git commits.

- [ ] **Step 1: Go to repo settings**

Open: `https://github.com/mixxorz/isekai/settings/pages`

- [ ] **Step 2: Set source to GitHub Actions**

Under "Build and deployment", set Source to **GitHub Actions**.

- [ ] **Step 3: Push to main and verify deployment**

Run:
```bash
git push origin main
```

Then watch the Actions tab at `https://github.com/mixxorz/isekai/actions` for
the "Deploy docs" workflow to complete. Once it succeeds, open
`https://mitchel.me/isekai` to verify the site is live.
```
