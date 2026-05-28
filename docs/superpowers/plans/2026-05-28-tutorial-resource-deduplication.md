# Tutorial Resource Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify the tutorial miner example so it relies on isekai's resource key deduplication instead of teaching manual exact-URL deduplication.

**Architecture:** Keep deduplication responsibility in the pipeline/database layer, where `Resource.key` is the primary key and mined resources are saved with `ignore_conflicts=True`. The tutorial miner should emit discovered resources directly, while docs explain that normalization is only needed when different URL strings should map to the same key.

**Tech Stack:** Python, Django model primary keys, Markdown tutorial docs, pytest.

---

### Task 1: Simplify the Tutorial Miner

**Files:**
- Modify: `tutorial/miners.py`
- Modify: `docs/tutorial.md`

- [ ] **Step 1: Update the runnable miner**

Replace the `seen` set in `tutorial/miners.py` with direct emission of hero and body image resources:

```python
        parser = CaseStudyParser(resource.text)
        mined: list[MinedResource] = []

        hero_url = parser.get_hero_image_url()
        if hero_url:
            mined.append(
                MinedResource(key=Key(type="url", value=hero_url), metadata={})
            )

        for image_url in parser.get_body_image_urls():
            mined.append(
                MinedResource(key=Key(type="url", value=image_url), metadata={})
            )

        return mined
```

- [ ] **Step 2: Update the tutorial code sample**

Make the `docs/tutorial.md` Step 6 code sample match `tutorial/miners.py` exactly for the `mine()` body.

- [ ] **Step 3: Replace the `seen` note**

Replace the note titled `Why we track seen URLs` with a note titled `Resource keys are deduplicated`:

```markdown
!!! note "Resource keys are deduplicated"
    If the miner emits the same `url:` key more than once, isekai still creates
    only one Resource row. Resource keys are primary keys, and the pipeline
    ignores conflicts when saving newly mined resources.
```

- [ ] **Step 4: Keep URL variant guidance precise**

Keep the image variant warning, but make sure it distinguishes exact duplicate keys from different URL strings that represent the same image. The production checklist should say to normalize variants so they share the same resource key.

- [ ] **Step 5: Verify**

Run:

```bash
uv run pytest tests/test_miners.py::TestMine::test_mine_is_idempotent_with_duplicate_images
```

Expected: the test passes, showing duplicate mined keys remain idempotent at the pipeline layer.

Run:

```bash
git diff -- docs/tutorial.md tutorial/miners.py docs/superpowers/plans/2026-05-28-tutorial-resource-deduplication.md
```

Expected: the diff only contains the tutorial/example simplification and this plan.

## Self-Review

- Spec coverage: The plan updates both the runnable miner and tutorial prose/code sample as requested.
- Placeholder scan: No placeholders remain.
- Type consistency: The miner still returns `list[MinedResource]` and uses existing `Key`, `TextResource`, and `BlobResource` imports.
