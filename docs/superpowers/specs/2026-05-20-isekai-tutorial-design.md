# Isekai Tutorial Design

**Date:** 2026-05-20
**Status:** Approved

## Overview

A full end-to-end tutorial for the isekai library, written for developers who have already built a Wagtail site and are now tasked with migrating content from an old website. The tutorial lives in the isekai repo as both a narrative doc (`docs/tutorial.md`) and a runnable example app (`tutorial/`).

## Fictional Scenario

**Source site:** Cairngorm Foundation (`cairngormfoundation.org.uk`) — a fictional Scottish community foundation, modelled on the structure of foundationscotland.org.uk.

**Target:** Migrate their case studies section (`/our-impact/case-studies/`, ~260 pages) into a new Wagtail site.

**Destination model:** `CaseStudyPage` — already built by the Wagtail developer before the migration starts.

## Deliverables

### 1. Narrative doc — `docs/tutorial.md`

Tone: practical and first-person ("here's what you can do and why"), not API reference. Each step has:

- The problem being solved
- The code with inline explanation
- A checkpoint — what to run and what to expect

### 2. Example app — `tutorial/`

A Django app that plugs into the existing `dev/` project. Added to `INSTALLED_APPS` in `dev/settings.py`. Runnable with the same `manage.py` commands documented in `CLAUDE.md`.

```
tutorial/
├── __init__.py
├── models.py          # CaseStudyPage + concrete Resource model
├── migrations/
├── parsers.py         # CaseStudyParser (BeautifulSoup)
├── seeders.py         # CaseStudySeeder (subclass of SitemapSeeder)
├── miners.py          # CaseStudyMiner
├── transformers.py    # CaseStudyTransformer
└── tests/
    ├── fixtures/
    │   └── case_studies/   # 5-10 sample HTML files (varied content)
    └── test_parser.py      # Parser tests against fixtures
```

## Tutorial Steps

### Step 0: Planning — What to migrate

**Problem:** Given a source website, decide which section is worth migrating.

**Approach:** Fetch the sitemap XML and count direct children per URL prefix. The section with the most direct children is likely serialized content (blog, news, case studies) and the best migration candidate.

The tutorial shows a short Python script that:

1. Fetches `sitemap.xml`
2. Parses the XML
3. Counts URLs per top-level section path
4. Prints a ranked table

Output shows case studies (~260) dwarfs news (~50), making the choice obvious.

Then: inspect a real case study page. Map HTML elements → Wagtail fields. Document what can be extracted and what will be lost.

### Step 1: The Wagtail destination model

**Problem:** Understand the shape of what we're building into.

Define `CaseStudyPage` with fields derived from the HTML inspection:

- `title` — from `<h1>`
- `category` — CharField (e.g., "Community Funds", "Charity Funds")
- `fund_name` — CharField (name of the related fund)
- `hero_image` — ForeignKey to Wagtail `Image`
- `introduction` — RichTextField (first paragraph)
- `body` — StreamField (subsequent sections as RichTextBlock)

Also define the concrete `Resource` model that wires up all processors.

### Step 2: Seeding

**Problem:** Get the list of URLs into the database — but only the case study URLs, not the entire sitemap.

Write a `CaseStudySeeder` that subclasses `SitemapSeeder` and overrides the URL filter to include only paths matching `/our-impact/case-studies/`. The tutorial explains why this matters: a full sitemap includes funding pages, community fund pages, news, etc.

Also introduce a `CASE_STUDIES_PARENT_PAGE_ID` Django setting — the Wagtail page ID of the case studies index page, looked up from the Wagtail admin. This will be used in the transformer to position new pages in the tree.

Show the Resource model with `seeders = [CaseStudySeeder()]`. Run `manage.py isekai` and show only case study resources created in SEEDED status.

### Step 3: Extracting

**Problem:** Fetch the HTML for each URL.

Use `HTTPExtractor`. No custom code needed — show that the built-in handles retries, MIME type detection, and storing the HTML as `text_data`. Run and show resources in EXTRACTED status.

### Step 4: Parsing — with sample pages and tests

**Problem:** Before wiring parsing into the pipeline, validate that it works across different content variations.

**Fixture setup:** Save 5–10 real case study HTML pages locally in `tutorial/tests/fixtures/case_studies/`. Choose samples that vary:

- Page with a hero image vs. without
- Page with multiple body sections vs. minimal content
- Different category values
- Different fund names

**Write `CaseStudyParser`** (BeautifulSoup) with methods:

- `get_title()` → str
- `get_category()` → str
- `get_fund_name()` → str | None
- `get_hero_image_url()` → str | None
- `get_introduction()` → str
- `get_body_sections()` → list[str] (HTML per section)

**Write `test_parser.py`** testing each method against each fixture. This catches edge cases before the pipeline runs.

### Step 5: Mining

**Problem:** Discover related resources (images) embedded in each case study page.

Write `CaseStudyMiner` using the parser:

- Call `parser.get_hero_image_url()` → emit `url:<image_url>` resource
- Call `parser.get_body_sections()`, find `<img>` tags → emit `url:<image_url>` resources

Wire into Resource model: `miners = [CaseStudyMiner()]`.

### Step 6: Transforming

**Problem:** Convert extracted HTML into a `Spec` shaped like `CaseStudyPage`.

Write `CaseStudyTransformer` using the parser:

- Parse HTML from `resource.text_data`
- Build `Spec` for `CaseStudyPage` with:
  - Scalar fields (title, category, fund_name, introduction, body)
  - `BlobRef` for hero image → resolves to Wagtail Image after load
  - `__wagtail_parent_page` from `settings.CASE_STUDIES_PARENT_PAGE_ID`

Also wire `ImageTransformer` from `isekai.contrib.wagtail` to handle the mined image resources.

### Step 7: Loading

**Problem:** Write specs to the database as real Django/Wagtail objects.

Use `PageLoader` from `isekai.contrib.wagtail`. Show the Resource model fully assembled with all processors. Run `manage.py isekai` end-to-end and show the pages appearing in the Wagtail admin.

## Key Design Decisions

### Parser-first, pipeline-second

The parser is written and tested before it's wired into the miner or transformer. This isolates HTML parsing concerns and makes it easy to validate against real fixture HTML before running the full pipeline.

### Fixtures over VCR cassettes for tutorial code

Sample HTML files in `tutorial/tests/fixtures/` are simple, readable, and don't require network recording infrastructure to understand. The tutorial reader can open an HTML file and see exactly what the parser is working with.

### Tutorial app separate from `dev/` testapp

`tutorial/` is a clean, self-contained app that demonstrates one specific use case. It plugs into `dev/` for running but doesn't pollute the existing testapp.

### Fictional but plausible content

All URLs, page titles, fund names, and content examples reference Cairngorm Foundation. This avoids any dependency on the real foundationscotland.org.uk site remaining stable while keeping the examples realistic.
