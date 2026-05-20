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
