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
