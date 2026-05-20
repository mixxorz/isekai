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
