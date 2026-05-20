# Isekai Docs Site — Design Spec

**Date:** 2026-05-20
**Status:** Approved

## Overview

Set up a Zensical-powered documentation site for the `isekai-django` library, deploy it to GitHub Pages at `https://mitchel.me/isekai`, and write comprehensive docs targeting library users.

## Site URL

`https://mitchel.me/isekai`

GitHub account is already configured for this custom domain.

## Tool

[Zensical](https://github.com/zensical/zensical) — modern static site generator (successor to MkDocs / Material for MkDocs). Config format: `zensical.toml`. Content format: Markdown in `docs/`.

## Docs Structure

```
docs/
  index.md                  # What is Isekai, install, 30-second example
  concepts.md               # Pipeline stages, Resource lifecycle, mental models
  tutorial.md               # (existing) Full Wagtail migration walkthrough
  how-to/
    index.md                # Overview of how-to guides
    custom-seeder.md        # Writing a custom seeder
    custom-extractor.md     # Writing a custom extractor
    custom-miner.md         # Writing a custom miner
    custom-transformer.md   # Writing a custom transformer
    custom-loader.md        # Writing a custom loader
  reference/
    index.md                # Reference overview
    seeders.md              # CSVSeeder, SitemapSeeder, BaseSeeder
    extractors.md           # HTTPExtractor, BaseExtractor
    miners.md               # HTMLImageMiner, HTMLDocumentMiner, HTMLPageMiner
    transformers.md         # BaseTransformer
    loaders.md              # ModelLoader, BaseLoader
    wagtail.md              # Wagtail contrib (loaders, transformers)
    types.md                # Spec, Key, ModelRef, BlobRef, ResourceRef, etc.
zensical.toml
```

## Navigation

```toml
nav = [
  { "Get started" = "index.md" },
  { "Concepts" = "concepts.md" },
  { "Tutorial" = "tutorial.md" },
  { "How-to guides" = [
    { "Overview" = "how-to/index.md" },
    { "Custom seeder" = "how-to/custom-seeder.md" },
    { "Custom extractor" = "how-to/custom-extractor.md" },
    { "Custom miner" = "how-to/custom-miner.md" },
    { "Custom transformer" = "how-to/custom-transformer.md" },
    { "Custom loader" = "how-to/custom-loader.md" },
  ]},
  { "Reference" = [
    { "Overview" = "reference/index.md" },
    { "Seeders" = "reference/seeders.md" },
    { "Extractors" = "reference/extractors.md" },
    { "Miners" = "reference/miners.md" },
    { "Transformers" = "reference/transformers.md" },
    { "Loaders" = "reference/loaders.md" },
    { "Wagtail" = "reference/wagtail.md" },
    { "Types" = "reference/types.md" },
  ]},
]
```

## zensical.toml Config

- `site_name = "Isekai"`
- `site_url = "https://mitchel.me/isekai"`
- `site_description = "A Django ETL framework for migrating content into Django models using a pluggable pipeline."`
- GitHub repo link in header
- Light/dark palette toggle
- Standard Zensical features: instant navigation, code copy, search highlight, navigation sections, footer nav, breadcrumbs

## Documentation Content

### `index.md` — Get Started
- One-paragraph pitch: what Isekai does and why
- Install instructions (`pip install isekai-django` and `[wagtail]` extra)
- Minimal working example (seed → extract → transform → load in ~20 lines)
- Links to Concepts and Tutorial

### `concepts.md` — Concepts
- The five pipeline stages: Seed, Extract, Mine, Transform, Load
- The Resource model: what it is, how it moves through stages
- The status lifecycle: SEEDED → EXTRACTED → MINED → TRANSFORMED → LOADED
- Processors: what they are, how they're registered
- Key types: Key, Spec, ModelRef, BlobRef, ResourceRef — brief explanations

### `tutorial.md` — Tutorial (existing, keep as-is)
The existing `docs/tutorial.md` is already complete. Move to `docs/tutorial.md` (already there).

### `how-to/` — How-to Guides
Short, task-focused guides. Each follows the pattern:
1. When to use this
2. Minimal code example
3. Key options/attributes

- `custom-seeder.md`: subclass `BaseSeeder`, implement `get_keys()`
- `custom-extractor.md`: subclass `BaseExtractor`, implement `extract()`
- `custom-miner.md`: subclass `BaseMiner`, implement `mine()`
- `custom-transformer.md`: subclass `BaseTransformer`, implement `transform()`
- `custom-loader.md`: subclass `BaseLoader`, implement `load()`

### `reference/` — API Reference
One page per module. For each class:
- One-line description
- Class signature / attributes
- Methods with signatures and brief descriptions
- Example usage where helpful

### README Update
- Keep: project name, one-paragraph description, pipeline overview
- Add: link to full docs at `https://mitchel.me/isekai`
- Trim: detailed concept explanations (now in docs), replace with "See the docs"

## GitHub Actions Deployment

File: `.github/workflows/docs.yml`

Trigger: push to `main`

Steps:
1. Checkout repo
2. Install uv
3. `uv run zensical build`
4. Deploy `site/` to GitHub Pages using `actions/upload-pages-artifact` + `actions/deploy-pages`

Permissions: `pages: write`, `id-token: write`

## Zensical Installation

Add `zensical` to the dev dependency group in `pyproject.toml` using `uv add --dev zensical`.
