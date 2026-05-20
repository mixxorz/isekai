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
