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
