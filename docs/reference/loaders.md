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
