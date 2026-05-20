---
icon: lucide/git-merge
---

# Dependency Resolution

When importing data, it's inevitable that you will come across distinct pieces
of data that depend on each other. For example, a case study page references a
hero image. That image must exist in the media library before the page can point
to it. If you try to create the page first, you could get an integrity error.

When using the `ModelLoader` or `PageLoader`, isekai automatically determines
the correct creation order based on resource dependencies, and handles circular
dependencies as well.

## How dependencies are recorded

During Transform, isekai inspects every `Spec` for refs:

```python
refs = spec.find_refs()          # collects all ResourceRef and BlobRef
resource.dependencies.set(...)   # stored as a M2M relationship
```

## Building the load order

At the start of Load, isekai reads all `TRANSFORMED` resources and their
recorded dependencies, then runs them through `resolve_build_order` to produce
an ordered list of **build groups**. Resources in earlier groups are created
first. Resources within the same group are created together (see
[Circular dependencies](#circular-dependencies) below).

## The SCC DAG algorithm

`resolve_build_order` works in three steps. Take this dependency graph as an
example — arrows point from a resource to the resource it depends on:

```
  page:about ──────────────► img:logo
      │
      ▼
  page:team ──► page:contact
      ▲               │
      └───────────────┘
```

`page:team` and `page:contact` reference each other, forming a cycle.
`page:about` depends on both `img:logo` and `page:team`. `img:logo` has no
dependencies.

**1. Find strongly connected components (Tarjan's algorithm)**

[Tarjan's SCC algorithm](https://en.wikipedia.org/wiki/Tarjan%27s_strongly_connected_components_algorithm)
runs a depth-first search over the dependency graph and identifies every set of
nodes that form a cycle. Nodes with no cycle form their own singleton component.
The algorithm runs in O(V + E) time.

```
  ┌─────────────────┐     ┌───────────────────────────┐     ┌──────────┐
  │    page:about   │     │  page:team + page:contact │     │ img:logo │
  └─────────────────┘     └───────────────────────────┘     └──────────┘
       SCC A                         SCC B                      SCC C

```

**2. Build the condensation DAG**

Each strongly connected component is collapsed to a single node. The edges
between components form a directed acyclic graph (DAG) — the _condensation_ of
the original graph. Because all cycles have been absorbed into components, this
graph is guaranteed to be acyclic.

```
  SCC A ──► SCC B
    │
    └──────► SCC C
```

**3. Topological sort**

Python's `graphlib.TopologicalSorter` sorts the condensation DAG so that
dependencies come before the nodes that depend on them. The final build order
maps each sorted component back to its original resource keys.

```
  ┌───────────┐     ┌─────────────────────────────┐     ┌─────────────┐
  │  Group 1  │     │           Group 2           │     │   Group 3   │
  │───────────│     │─────────────────────────────│     │─────────────│
  │ img:logo  │ ──► │ page:team  +  page:contact  │ ──► │ page:about  │
  └───────────┘     └─────────────────────────────┘     └─────────────┘
```

`img:logo` is created first. Then `page:team` and `page:contact` are created
together using two-phase loading. Then `page:about` is created last.

## Circular dependencies

When two or more resources reference each other — directly or through a chain —
they end up in the same strongly connected component. Isekai loads them together
using a two-phase process:

**Phase 1 — create with placeholders**

All resources in the cycle are created at once. Fields that reference another
resource in the same cycle are filled with a temporary placeholder value
appropriate for the field type (a negative integer for integer foreign keys, a
random UUID for UUID foreign keys, `"temp_value"` for string fields, and so on).
This satisfies database `NOT NULL` constraints while the objects are being
created.

**Phase 2 — resolve and update**

Once every object in the cycle exists, isekai goes back and replaces all
placeholder values with the real foreign keys. The entire operation runs inside
a single database transaction with constraint checks disabled until the end, so
no partial state is ever committed.

```python
# Example: two pages that reference each other
with transaction.atomic(), connection.constraint_checks_disabled():
    # Phase 1: create all objects with temp placeholder values
    page_a = Page(related_page_id=-1000000)
    page_a.save()
    page_b = Page(related_page_id=-1000001)
    page_b.save()

    # Phase 2: fix the placeholders
    page_a.related_page = page_b
    page_a.save()
    page_b.related_page = page_a
    page_b.save()

    connection.check_constraints()
```

## Already-loaded dependencies

If a dependency was loaded in a previous pipeline run, it is not included in
the current build graph. The loader resolves it immediately by fetching the
existing `target_object` from the database, so it has no effect on ordering.

## Skipped resources

If any resource in a build group cannot be loaded (for example, because one of
its dependencies failed to load in an earlier run), the entire group is skipped.
Because the build order is topological, all downstream resources that depend on
the skipped group are also skipped automatically.
