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

Each list can contain multiple processors. The behavior depends on the stage:

- **Seeders** and **miners** run all processors and combine their results.
- **Extractors**, **transformers**, and **loaders** try processors in order and
  use the first one that returns a result for a given resource.

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
