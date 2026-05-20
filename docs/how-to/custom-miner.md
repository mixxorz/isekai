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
