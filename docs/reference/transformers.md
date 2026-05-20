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
