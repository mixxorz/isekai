# Tutorial Production Restructure Design

**Date:** 2026-05-28
**Approach:** Keep the Cairngorm tutorial, add production hardening from real isekai usage

## Goal

Restructure `docs/tutorial.md` so it remains an approachable Cairngorm case study while teaching the production patterns that surfaced from the MAP website migration in `../map-website`.

The tutorial should stay narrative and readable, but the examples must be accurate enough for a real Wagtail migration. It should cover URL normalization, image variants, body image references, Wagtail rich text conversion, metadata-only resources, failed resource inspection, and restart behavior.

This work also includes a small library correction: increase the default `AbstractResource.key` length from 255 to 1024 characters. URL-based resource keys are a core use case, and real migrations can exceed 255 characters. Since `AbstractResource` is abstract, user projects will generate migrations for their concrete `Resource` models.

## Scope

In scope:

- Update `AbstractResource.key` to `max_length=1024` by default.
- Revise `docs/tutorial.md` around the existing Cairngorm case study.
- Add production hardening sections and callouts where they naturally fit.
- Correct inaccurate tutorial claims about processor ordering, command behavior, references, and Wagtail handling.
- Add examples inspired by `../map-website` without switching the tutorial scenario to MAP.

Out of scope:

- Replacing the Cairngorm tutorial with a MAP news migration tutorial.
- Adding new reusable framework APIs for image fallback, URL normalization, or parser reports.
- Changing pipeline behavior beyond the `Resource.key` field length.
- Writing a full sample Django project under the repository.

## Architecture

The work has two units.

### Core library correction

Change `isekai.models.AbstractResource.key` from:

```python
key = models.CharField(max_length=255, primary_key=True, db_index=True)
```

to:

```python
key = models.CharField(max_length=1024, primary_key=True, db_index=True)
```

The tutorial should no longer recommend overriding `key` for normal URL-heavy migrations. It can mention that users may still override the field if their database or source data needs a different limit.

### Tutorial restructure

Keep the existing stage-based flow:

1. Planning
2. Destination model
3. Resource model
4. Seeding
5. Extracting
6. Parsing
7. Mining
8. Transforming
9. Running the pipeline
10. Troubleshooting and production hardening

The main path should remain clear enough for a first-time reader. Advanced material should appear as short optional sections or callouts, not as a second parallel tutorial.

## Tutorial Changes

### Opening and prerequisites

Keep the current narrative opening, but tighten any claims that overpromise. The tutorial should say the pipeline handles hero images and body images where present, not that every imported page necessarily has every field populated.

Recommend installing the base package:

```bash
pip install isekai-django
```

The tutorial uses Wagtail integrations, but the install guidance should not recommend `isekai-django[wagtail]`. Since BeautifulSoup is already a dependency of isekai, the tutorial may still mention it explicitly for parser code, but should avoid implying it is a separate hard requirement unless the user has installed isekai without dependencies.

### Destination model

Update the example `CaseStudyPage.body` to support both rich text sections and image blocks. This lets the tutorial demonstrate body image migration with real Wagtail references instead of leaving old `<img src="...">` tags inside imported HTML.

The model can remain simple. It does not need to model every possible block from the source site.

### Resource model

Show the concrete `Resource` model with processors in order:

- Custom/no-op extractors before generic extractors when relevant.
- Image transformer before page transformer.
- `PageLoader` before `ModelLoader`.

Explain processor ordering precisely:

- Seeders all run.
- Miners all run.
- Extractors are tried in order until one returns a resource.
- Transformers are tried in order until one returns a spec.
- Loaders are tried in order until one returns created objects for the current load node.

Add `AbstractResourceAdmin` registration so readers can inspect status and errors in Django admin.

### Seeding

Keep sitemap filtering. Make URL normalization rules explicit where they apply to page URLs: lowercase only if safe for the source site, strip known tracking query strings if they appear in the sitemap or CSV input, and avoid changing URLs blindly.

The tutorial should distinguish exact duplicate resource keys from different URL strings that point to the same underlying item.

### Extracting

Keep `HTTPExtractor` as the main extractor.

Add an optional image fallback extractor section after the basic extractor explanation. This should be based on the MAP pattern:

- Try the canonical image URL first.
- If it 404s, try `original_src` from metadata.
- Optionally try known source-site variants such as `_cropped` or dimension-suffixed URLs.

This section should be framed as source-site-specific hardening, not required isekai boilerplate.

### Parsing

Keep fixture-first parser development. Add parser helpers for image URL handling:

- Resolve relative URLs to absolute URLs.
- Normalize known image variant suffixes to canonical keys.
- Preserve `original_src` in metadata.
- Capture `alt_text` and captions when available.

Add an optional parser report command inspired by MAP's `test_news_page_parser` command. The report should print parsed titles, metadata, image counts, body block counts, and suspicious missing fields for fixture pages. This complements pytest because visual inspection often catches parser mistakes that simple assertions miss.

### Mining

Emit mined image resources using normalized absolute keys. Include metadata such as `alt_text`, `caption`, and `original_src`.

Explain that resource keys are deduplicated by the database and `bulk_create(..., ignore_conflicts=True)`. Do not add a manual `seen` set unless the parser needs it for its own output shape.

Add an optional metadata-only resource pattern:

- Miners can emit non-URL keys such as `tag:*`, `form:*`, or `category:*`.
- Those resources need a no-op extractor that returns a `TextResource` from metadata so they can continue through the pipeline.

This should be a callout, not part of the main Cairngorm implementation unless the tutorial adds categories as real related objects.

### Transforming

Convert Wagtail rich text using `EditorHTMLConverter().to_database_format(...)` before storing source HTML in rich text fields or rich text StreamField blocks.

Use the same normalized keys in `BlobRef` or `ResourceRef` that the miner emitted. The tutorial should call out this rule directly: if the miner normalizes a URL but the transformer references the raw URL, dependency validation fails.

Use references for body image blocks rather than preserving old image HTML:

```python
("image", {"image": ResourceRef(image_key)})
```

Explain reference types briefly:

- `BlobRef` resolves to a file-like object and is useful for file fields.
- `ResourceRef` resolves lazily to the model object created from another resource. Dot notation such as `ResourceRef(image_key).pk` resolves to the eventual attribute value after the resource is loaded.
- `ModelRef` resolves lazily to an existing database object. Dot notation such as `ModelRef("images.CustomImage", pk=1).file.url` resolves to the requested attribute path at load time.

### Running the pipeline

Correct command behavior:

- The `isekai` management command runs the whole configured pipeline.
- The underlying `Pipeline` methods are separate, but the tutorial does not ask users to run stages manually.
- The extract/mine loop repeats until no new resources are seeded.

Explain loader ordering and dependency resolution without overclaiming. Isekai computes dependencies from refs and orders loading so referenced resources are ready first. For circular dependencies, it uses grouped loading and partial construction behavior described in the dependency resolution reference.

### Troubleshooting and hardening

Add a final practical section covering:

- Inspecting failed resources in admin.
- Querying resources with `last_error` in Django shell.
- Understanding automatic reference validation during transform: if a `BlobRef` or `ResourceRef` points at a key that was never seeded or mined, transform fails with an invalid-ref error.
- Understanding load-time dependency readiness: resources with failed dependencies will not load successfully.
- Handling 404 images by skipping nullable fields, leaving image refs out, or using a fallback extractor.
- Missing Wagtail parent page IDs.
- Content type string mistakes.
- Parser output reports for fixture inspection.

## Data Flow

The revised tutorial should teach this flow:

1. Seeder emits canonical page URL resources.
2. `HTTPExtractor` fetches page HTML and stores it as text.
3. Parser extracts title, metadata, intro, body blocks, hero image, and body images.
4. Parser or miner normalizes image URLs. Relative URLs become absolute, variant URLs become canonical keys, and original URLs are kept in metadata.
5. Miner emits image resources using the same normalized keys the transformer will reference.
6. Extractors fetch image blobs.
7. `ImageTransformer` creates Wagtail `Image` specs from image blobs, including metadata where applicable.
8. `CaseStudyTransformer` creates a page spec with the Wagtail parent page ID, page fields, body StreamField blocks, hero image reference, and body image references.
9. Loaders resolve dependencies so images load before pages that reference them.
10. Re-running the command skips resources already past completed stages.

## Error Handling

The tutorial should be explicit about which checks are automatic and which are user responsibilities.

Automatic:

- Duplicate resource keys collapse to one row.
- Refs in specs are checked during transform. Missing referenced resource keys raise `TransformError("Invalid refs found in spec")`.
- Load ordering follows the dependency graph derived from refs.
- Resources already past a stage are skipped on the next run.

User responsibilities:

- Use the same normalized keys in miners and transformers.
- Decide how to handle failed optional resources such as 404 images.
- Check parser output before running the full migration.
- Configure correct parent page IDs and content type strings.

## Testing And Verification

Implementation should verify:

- `uv run pytest`
- `uv run tox -e lint,type` because library code changes are included.
- A focused assertion that `AbstractResource._meta.get_field("key").max_length == 1024`, either in an existing model test file or a new minimal test.

Docs should be self-checked for:

- Code examples that use imports only at the top of files.
- Consistent normalized key usage between miner and transformer examples.
- Correct processor ordering descriptions.
- No overclaims that every page has every optional field.
- No stale references to Foundation Scotland in the Cairngorm tutorial.

## Acceptance Criteria

- `AbstractResource.key` defaults to 1024 characters.
- Tests cover the default key length.
- The tutorial install command recommends `pip install isekai-django`, not the Wagtail extra.
- The tutorial explains exact processor ordering behavior.
- The tutorial resolves relative image URLs before emitting `url:` keys.
- The tutorial normalizes image variant URLs and preserves `original_src` metadata.
- The tutorial uses matching normalized keys in mined resources and transformer refs.
- Body images are represented as Wagtail image blocks or the tutorial explicitly states any limitation.
- Rich text examples mention Wagtail database-format conversion.
- The tutorial includes admin/error inspection guidance.
- The tutorial includes optional real migration patterns: image fallback extractor, no-op extractor for metadata-only resources, parser report command, and reference type summary.
