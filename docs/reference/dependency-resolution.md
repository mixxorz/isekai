---
icon: lucide/git-merge
---

# Dependency Resolution

!!! note "Coming soon"
    This page is a placeholder. Full documentation for isekai's dependency
    resolution and cycle-breaking strategy is coming soon.

When isekai loads a set of `Spec` objects, it analyses the cross-references
between them to determine the correct creation order. Objects that are
referenced by others are created first.

For cases where references form a cycle, isekai uses a partial construction
strategy: objects in the cycle are created with temporary placeholder values,
then updated once all objects in the cycle exist. This allows circular
dependencies to be resolved without manual intervention.
