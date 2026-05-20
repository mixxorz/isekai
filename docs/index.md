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
