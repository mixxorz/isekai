# Tutorial Two Scoops Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `docs/tutorial.md` so it reads like a chapter from *Two Scoops of Django* — warm, opinionated, first-person plural, with a narrative arc that earns the pipeline before showing it.

**Architecture:** Single file rewrite of `docs/tutorial.md`. No code changes. A placeholder reference page `docs/reference/dependency-resolution.md` is created to support a link in Step 8. All other doc files are untouched.

**Tech Stack:** Markdown, MkDocs (existing docs site)

---

## File Map

| Action | File | Purpose |
|---|---|---|
| Modify | `docs/tutorial.md` | Full rewrite per spec |
| Create | `docs/reference/dependency-resolution.md` | Placeholder page linked from Step 8 |

---

### Task 1: Write the new opening

**Files:**
- Modify: `docs/tutorial.md` (replace everything from `# Tutorial` through the Prerequisites section)

- [ ] **Step 1: Replace the title and introduction**

Replace from the top of `docs/tutorial.md` through the end of the Prerequisites section with:

```markdown
# Tutorial: Migrating Content into Wagtail with Isekai

## The Migration That's Been Sitting on Your Todo List

You're near the end of the project. The new Wagtail site looks great. The
design is done, the custom page types are in place, the CMS is configured.
There's just one thing left — the thing you've been quietly pushing to the
bottom of the sprint: moving the content over from the old site.

It's time.

Your first instinct is to write a script. Fetch the pages, parse the HTML,
save the records. How hard could it be?

Pretty hard, it turns out.

The HTML is inconsistent — some pages have an introduction paragraph, others
don't. Images appear at unpredictable URLs, sometimes as cropped variants
rather than the originals. Case study pages reference hero images that need
to exist in the Wagtail image library *before* the page can be created — but
those images come from the same pages you're still fetching. By page 51 your
script throws a `KeyError` you didn't anticipate, and you realise you don't
know the full shape of the data until you're already deep in it.

The root problem is that a content migration isn't a single task. It's a
*pipeline*: fetch the pages, discover what they reference, download those
references, parse everything into structured data, then write it all to the
database in the right order. Each of those stages has its own failure modes.
When something breaks on stage three, you don't want to re-fetch two hundred
pages to try again.

That's what isekai gives you. A structured pipeline where each resource moves
through defined stages — **SEEDED → EXTRACTED → MINED → TRANSFORMED →
LOADED** — and where a failed or interrupted run can always pick up from
where it stopped.

In this tutorial we'll build a real migration: moving 260 case study pages
from the Cairngorm Foundation website into a new Wagtail site, complete with
hero images, body images, categories, and fund names. By the end you'll have
a pipeline that handles all of that — and if it stops halfway through, you
can run it again and it'll skip everything that already worked.

## Prerequisites

- A working Django + Wagtail project
- Python 3.10+
- isekai installed: `pip install isekai-django[wagtail]`
- BeautifulSoup4 installed: `pip install beautifulsoup4`
```

- [ ] **Step 2: Verify the file looks right**

Read `docs/tutorial.md` lines 1–60 and confirm the new opening is in place and the old introduction is gone.

- [ ] **Step 3: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: rewrite tutorial opening with Two Scoops narrative arc"
```

---

### Task 2: Rewrite Step 0 (Planning)

**Files:**
- Modify: `docs/tutorial.md` (Step 0 section)

- [ ] **Step 1: Replace the Step 0 section**

Find the `## Step 0: Planning — What to migrate` heading and replace the entire section (through the paragraph ending "Older pages have a simpler flat structure...") with:

```markdown
## Step 0: Planning — Understand the data before you write a line

Before writing any code, spend five minutes understanding what you're
actually migrating. The shape of the data determines every parser and
transformer you'll write. Skipping this step means discovering surprises
in the middle of a run instead of at the start.

!!! tip "Five minutes with a sitemap saves hours of surprised parsing code"
    The most common mistake in content migrations is diving straight into
    code. A quick look at the sitemap and a few representative pages will
    tell you what fields exist, how consistent the HTML is, and what edge
    cases to design for.

This script analyses a sitemap and counts pages per section:

```python
import requests
from xml.etree import ElementTree as ET
from urllib.parse import urlparse
from collections import Counter

response = requests.get("https://cairngormfoundation.org.uk/sitemap.xml")
root = ET.fromstring(response.content)
ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

section_counts = Counter()
for url_elem in root.findall("s:url", ns):
    loc = url_elem.find("s:loc", ns).text
    path = urlparse(loc).path
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) >= 2:
        section = "/" + "/".join(parts[:2]) + "/"
        section_counts[section] += 1

for section, count in section_counts.most_common(10):
    print(f"{count:4d}  {section}")
```

Output:

```
 260  /our-impact/case-studies/
  53  /about-us/our-news/
  42  /apply-for-funding/funding-available/
 ...
```

260 case study pages — each with a consistent structure. That's our target.

Inspect one page manually and list what you can extract:

- **Title** — from `<h1 class="heading-primary">`
- **Category** — from the metadata list (`<ul class="list-meta">`)
- **Fund name** — from the same metadata list, under "Related fund"
- **Hero image** — from `<figure class="wide"> img`
- **Introduction** — from `<p class="text-lead">` (newer pages only)
- **Body sections** — from `<p class="red-brown">` headings inside `<div class="editor">`

Older pages have a simpler flat structure with no introduction or sections.
Your parser needs to handle both gracefully — we'll come back to that in
Step 5.
```

- [ ] **Step 2: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: rewrite tutorial Step 0 with tip callout and warmer prose"
```

---

### Task 3: Rewrite Steps 1–2 (Destination model + Resource model)

**Files:**
- Modify: `docs/tutorial.md` (Steps 1 and 2)

- [ ] **Step 1: Replace Step 1**

Find `## Step 1: The Wagtail destination model` and replace the entire section with:

```markdown
## Step 1: The destination — your CaseStudyPage model

You already have a `CaseStudyPage` model. You built it earlier in the
project when you were defining the site's page types. Here's what it
looks like:

```python
# tutorial/models.py
from django.db import models
from wagtail import blocks
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page


class CaseStudyPage(Page):
    category = models.CharField(max_length=100, blank=True)
    fund_name = models.CharField(max_length=255, blank=True)
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    introduction = RichTextField(blank=True)
    body = StreamField(
        [("section", blocks.RichTextBlock())],
        blank=True,
        use_json_field=True,
    )

    content_panels = Page.content_panels + [
        "category",
        "fund_name",
        "hero_image",
        "introduction",
        "body",
    ]

    class Meta:
        verbose_name = "Case Study Page"
```

This is the destination. Everything the pipeline does — fetching, parsing,
downloading images — is in service of populating these fields.

The `body` StreamField uses `RichTextBlock` for each section, which
preserves the HTML from the source page. The `hero_image` FK points at
Wagtail's built-in `Image` model — isekai will create those `Image` objects
automatically when it processes the mined image resources.

Find the parent page ID in the Wagtail admin by navigating to the page you
want case studies nested under and noting the ID in the URL
(e.g. `/cms/pages/3/`). Add it to your settings:

```python
# settings.py
CASE_STUDIES_PARENT_PAGE_ID = 3
```
```

- [ ] **Step 2: Replace Step 2**

Find `## Step 2: Setting up isekai — the Resource model` and replace the entire section with:

```markdown
## Step 2: Setting up isekai — the Resource model

Every isekai pipeline needs a concrete `Resource` model. Think of it as
the pipeline's ledger: one database row per piece of content, each row
tracking exactly where that content is in its journey from the old site
to Wagtail.

Start with the minimal version:

```python
# tutorial/models.py (continued)
from isekai.models import AbstractResource


class Resource(AbstractResource):
    class Meta:
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
```

!!! note "One concrete subclass, exactly"
    Isekai discovers your `Resource` model at runtime using
    `get_resource_model()`. There must be exactly one concrete subclass of
    `AbstractResource` in your project — isekai will raise an error if it
    finds zero or more than one.

As we build each component in the steps below, we'll wire it in here. By
the end of this tutorial, `Resource` will look like this:

```python
# tutorial/models.py (final form)
from isekai.contrib.wagtail.loaders import PageLoader
from isekai.contrib.wagtail.transformers import ImageTransformer
from isekai.extractors import HTTPExtractor
from isekai.loaders import ModelLoader
from isekai.models import AbstractResource

from tutorial.miners import CaseStudyMiner
from tutorial.seeders import CaseStudySeeder
from tutorial.transformers import CaseStudyTransformer


class Resource(AbstractResource):
    seeders = [CaseStudySeeder()]
    extractors = [HTTPExtractor()]
    miners = [CaseStudyMiner()]
    transformers = [
        ImageTransformer(),
        CaseStudyTransformer(),
    ]
    loaders = [
        PageLoader(),
        ModelLoader(),
    ]

    class Meta:
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
```

Each list is a set of processors for that pipeline stage:

- **seeders** — generate the initial list of resource keys (URLs to migrate)
- **extractors** — fetch raw data for each resource (HTTP requests)
- **miners** — discover related resources from extracted content (images)
- **transformers** — convert extracted content into a `Spec` describing what Django model to create
- **loaders** — write the `Spec` to the database

When a stage has multiple processors, isekai tries them in order and uses
the first one that returns a result. This is how `ImageTransformer` and
`CaseStudyTransformer` coexist: each handles a different type of resource
and returns `None` for the other.
```

- [ ] **Step 3: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: rewrite tutorial Steps 1-2 with existing-model framing and Resource ledger intro"
```

---

### Task 4: Rewrite Steps 3–4 (Seeder + Extractor)

**Files:**
- Modify: `docs/tutorial.md` (Steps 3 and 4)

- [ ] **Step 1: Replace Step 3**

Find `## Step 3: Seeding — getting the URL list` and replace the entire section with:

```markdown
## Step 3: Seeding — building the list of what to migrate

The seeder's job is simple: generate the initial set of resource keys.
Those keys are what the rest of the pipeline works from.

`SitemapSeeder` is built into isekai. It fetches a sitemap XML and creates
a `Resource` for every URL it finds. We only want case study URLs, not the
whole site, so we subclass it and add a filter:

```python
# tutorial/seeders.py
from isekai.seeders import SitemapSeeder
from isekai.types import SeededResource

CASE_STUDIES_PATH = "/our-impact/case-studies/"


class CaseStudySeeder(SitemapSeeder):
    """Seeds only case study URLs from the Cairngorm Foundation sitemap."""

    sitemap_url = "https://cairngormfoundation.org.uk/sitemap.xml"

    def seed(self) -> list[SeededResource]:
        all_resources = super().seed()
        return [
            r
            for r in all_resources
            if CASE_STUDIES_PATH in r.key.value
            and r.key.value.rstrip("/") != CASE_STUDIES_PATH.rstrip("/")
        ]
```

The filter keeps only URLs that contain `/our-impact/case-studies/` and
strips the index page itself — we want the individual case studies, not
the listing page.

Wire it into your `Resource` model:

```python
from tutorial.seeders import CaseStudySeeder

class Resource(AbstractResource):
    seeders = [CaseStudySeeder()]
    # ... rest of processors
```

Individual pipeline stages can't be run in isolation — the full pipeline
runs together in Step 8. Continue to the next step.
```

- [ ] **Step 2: Replace Step 4**

Find `## Step 4: Extracting — fetching the HTML` and replace the entire section with:

```markdown
## Step 4: Extracting — fetching the raw content

The extractor's job is to fetch raw data for each seeded resource and
store it. `HTTPExtractor` is built in: it makes an HTTP GET request,
detects the content type from the response headers, and stores the result
as text (for HTML and JSON) or as a binary file (for images, PDFs, and
other non-text formats). It handles redirects and basic retries
automatically.

No custom code needed here. It's already in your `Resource` model:

```python
extractors = [HTTPExtractor()]
```

That one line handles fetching all 260 case study HTML pages and, later
in the pipeline, all the image files the miner discovers.

Individual pipeline stages can't be run in isolation — the full pipeline
runs together in Step 8. Continue to the next step.
```

- [ ] **Step 3: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: rewrite tutorial Steps 3-4 with warmer prose and clearer stage framing"
```

---

### Task 5: Rewrite Step 5 (Parser)

**Files:**
- Modify: `docs/tutorial.md` (Step 5)

- [ ] **Step 1: Replace Step 5**

Find `## Step 5: Parsing — understanding the HTML before wiring it in` and replace the entire section with:

```markdown
## Step 5: Parsing — understanding the HTML before wiring it in

Before connecting any parser to the pipeline, write and test it against
local HTML files. This decouples your parsing logic from the network:
you're not waiting for 260 HTTP requests every time you tweak a CSS
selector.

!!! tip "Test your parser against fixture files before wiring it into the pipeline"
    Download five representative pages and save them as fixtures. Run your
    parser tests against those files. You want to know your selectors work
    *before* you've fetched 260 pages and found the broken ones only at
    transform time.

**Collect fixture files** — pick five pages that cover the structural
variations you've observed and save them under
`tutorial/tests/fixtures/case_studies/`. Choose pages that vary:

- Newer structure with intro + sections + body images
- Newer structure with fewer sections, no body images
- Newer structure with Charity Funds category
- Older flat structure with no intro, no fund link
- Older flat structure with Charity Funds

Now write the parser:

```python
# tutorial/parsers.py
from bs4 import BeautifulSoup, Tag


class CaseStudyParser:
    """Extracts structured data from a Foundation Scotland case study HTML page."""

    def __init__(self, html: str):
        self.soup = BeautifulSoup(html, "html.parser")

    def get_title(self) -> str:
        tag = self.soup.find("h1", class_="heading-primary")
        if tag is None:
            return ""
        return tag.get_text(strip=True)

    def get_category(self) -> str:
        for ul in self.soup.find_all("ul", class_="list-meta"):
            for li in ul.find_all("li"):
                if "Category" in li.get_text():
                    link = li.find("a")
                    if link:
                        return link.get_text(strip=True)
        return ""

    def get_fund_name(self) -> str | None:
        for ul in self.soup.find_all("ul", class_="list-meta"):
            for li in ul.find_all("li"):
                if "Related fund" in li.get_text():
                    link = li.find("a")
                    if link:
                        return link.get_text(strip=True)
        return None

    def get_hero_image_url(self) -> str | None:
        hero_fig = self.soup.find("figure", class_="wide")
        if hero_fig is None:
            return None
        img = hero_fig.find("img")
        if img is None:
            return None
        src = img.get("src")
        return str(src) if src else None

    def get_introduction(self) -> str:
        tag = self.soup.find("p", class_="text-lead")
        if tag is None:
            return ""
        return tag.get_text(strip=True)

    def get_body_sections(self) -> list[str]:
        """
        Returns body sections as a list of HTML strings.

        Newer pages use p.red-brown as section headings (without text-lead class).
        Each section runs from one p.red-brown to the next.
        Older flat pages have no p.red-brown elements and return an empty list.
        """
        all_tags: list[Tag] = []
        for div in self.soup.find_all("div", class_="editor"):
            for child in div.children:
                if isinstance(child, Tag):
                    all_tags.append(child)

        sections: list[str] = []
        current: list[Tag] = []
        in_section = False

        for tag in all_tags:
            classes = tag.get("class") or []
            is_heading = (
                tag.name == "p"
                and "red-brown" in classes
                and "text-lead" not in classes
            )
            if is_heading:
                if in_section and current:
                    sections.append("".join(str(t) for t in current))
                current = [tag]
                in_section = True
            elif in_section:
                current.append(tag)

        if in_section and current:
            sections.append("".join(str(t) for t in current))

        return sections

    def get_body_image_urls(self) -> list[str]:
        """Returns image src values found inside div.editor (body content, not hero)."""
        urls = []
        for div in self.soup.find_all("div", class_="editor"):
            for img in div.find_all("img"):
                src = img.get("src")
                if src:
                    urls.append(str(src))
        return urls
```

A few things worth noting:

- `get_fund_name()` returns `None` (not `""`) when absent — older pages
  have no Related fund link at all, and we want to distinguish "not
  present" from "present but empty"
- `get_introduction()` returns `""` on older pages — the `text-lead` class
  simply doesn't exist on those pages
- `get_body_sections()` checks for `red-brown` *without* `text-lead` to
  exclude the intro paragraph, which on newer pages carries both classes
- `get_body_image_urls()` only looks inside `div.editor`, not the entire
  document, so the hero image isn't double-counted

Write tests against each fixture:

```python
# tutorial/tests/test_parser.py
from pathlib import Path

from tutorial.parsers import CaseStudyParser

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "case_studies"


def load_fixture(filename: str) -> CaseStudyParser:
    html = (FIXTURES_DIR / filename).read_text(encoding="utf-8")
    return CaseStudyParser(html)


class TestCaseStudyParserFixture01:
    """reopening-crosswater: newer structure, 4 sections, body images"""

    def setup_method(self):
        self.parser = load_fixture("case_study_01.html")

    def test_get_title(self):
        assert self.parser.get_title() == "Reopening The Crosswater"

    def test_get_category(self):
        assert self.parser.get_category() == "Community Funds"

    def test_get_fund_name(self):
        assert self.parser.get_fund_name() == "Barrhill Community Interest Company"

    def test_get_body_sections_count(self):
        assert len(self.parser.get_body_sections()) == 4

    def test_get_body_image_urls(self):
        urls = self.parser.get_body_image_urls()
        assert len(urls) == 2

# ... and so on for fixtures 02–05
```

Each fixture class tests something different: a page with no body images,
a page with Charity Funds category, an older page with no intro, an older
page with no fund link.

Checkpoint:

```bash
pytest tutorial/tests/test_parser.py -v
```

All tests should pass. Fix any selector mismatches before moving on —
getting this right now means your pipeline will work without surprises.
```

- [ ] **Step 2: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: rewrite tutorial Step 5 with tip callout and prose notes on parser design"
```

---

### Task 6: Rewrite Step 6 (Miner)

**Files:**
- Modify: `docs/tutorial.md` (Step 6)

- [ ] **Step 1: Replace Step 6**

Find `## Step 6: Mining — discovering images` and replace the entire section with:

```markdown
## Step 6: Mining — discovering what the pages reference

Mining exists because content doesn't live in isolation. Case study pages
reference images — and those images need to be downloaded and stored in
Wagtail before the pages that reference them can be created. The miner's
job is to look at an extracted page and emit new resources for everything
it references.

```python
# tutorial/miners.py
from isekai.miners import BaseMiner
from isekai.types import BlobResource, Key, MinedResource, TextResource

from tutorial.parsers import CaseStudyParser


class CaseStudyMiner(BaseMiner):
    """Mines image resources from a case study page."""

    def mine(
        self, key: Key, resource: TextResource | BlobResource
    ) -> list[MinedResource]:
        if key.type != "url":
            return []
        if not isinstance(resource, TextResource):
            return []

        parser = CaseStudyParser(resource.text)
        mined: list[MinedResource] = []
        seen: set[str] = set()

        hero_url = parser.get_hero_image_url()
        if hero_url and hero_url not in seen:
            seen.add(hero_url)
            mined.append(MinedResource(key=Key(type="url", value=hero_url), metadata={}))

        for image_url in parser.get_body_image_urls():
            if image_url not in seen:
                seen.add(image_url)
                mined.append(
                    MinedResource(key=Key(type="url", value=image_url), metadata={})
                )

        return mined
```

!!! note "Why we track `seen` URLs"
    The same image URL can appear as both the hero and a body image on some
    pages. Without deduplication, we'd create two resource rows for the
    same URL and download the image twice.

!!! warning "Image URLs are often variants, not originals"
    Many CMSes serve images through a resizing or cropping layer. The URL
    you find in the HTML might look like
    `/media/images/photo__width-800.jpg` — a resized variant — rather than
    the original `/media/images/photo.jpg`. If you mine these variant URLs
    directly, you'll download a degraded version of the image and potentially
    end up with many near-duplicate entries in your Wagtail image library
    (one per size variant encountered across pages).

    Before you run the pipeline, inspect the image URLs on a few pages and
    check whether they follow a variant pattern. If they do, normalize them
    to their canonical form in the miner before emitting the resource. The
    exact normalization depends on your source site's URL structure.

When the miner emits a `url:` resource, isekai seeds it for extraction.
On the next extract pass, those image files are downloaded as binary blobs.
Then `ImageTransformer` (already in `Resource.transformers`) picks them up
and creates Wagtail `Image` objects from them.

Wire the miner into your `Resource` model:

```python
from tutorial.miners import CaseStudyMiner

class Resource(AbstractResource):
    # ...
    miners = [CaseStudyMiner()]
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: rewrite tutorial Step 6 with seen-set note and image URL variant warning"
```

---

### Task 7: Rewrite Step 7 (Transformer)

**Files:**
- Modify: `docs/tutorial.md` (Step 7)

- [ ] **Step 1: Replace Step 7**

Find `## Step 7: Transforming — mapping HTML to Wagtail fields` and replace the entire section with:

```markdown
## Step 7: Transforming — mapping content to a model description

A transformer reads an extracted resource and returns a `Spec` — a
description of what model instance to create and what field values to give
it. Critically, the transformer *doesn't touch the database*. It just
describes the object. The loader (Step 8) does the actual creating.

```python
# tutorial/transformers.py
from django.conf import settings

from isekai.transformers import BaseTransformer
from isekai.types import BlobRef, BlobResource, Key, Spec, TextResource

from tutorial.parsers import CaseStudyParser


class CaseStudyTransformer(BaseTransformer):
    """Transforms an extracted case study HTML page into a CaseStudyPage Spec."""

    def transform(self, key: Key, resource: TextResource | BlobResource) -> Spec | None:
        if key.type != "url":
            return None
        if not isinstance(resource, TextResource):
            return None

        parser = CaseStudyParser(resource.text)
        title = parser.get_title()
        if not title:
            return None

        attributes: dict = {
            "title": title,
            "category": parser.get_category(),
            "fund_name": parser.get_fund_name() or "",
            "introduction": parser.get_introduction(),
            "body": [
                {"type": "section", "value": section}
                for section in parser.get_body_sections()
            ],
            "__wagtail_parent_page": settings.CASE_STUDIES_PARENT_PAGE_ID,
        }

        hero_url = parser.get_hero_image_url()
        if hero_url:
            attributes["hero_image"] = BlobRef(Key(type="url", value=hero_url))

        return Spec(
            content_type="tutorial.casestudypage",
            attributes=attributes,
        )
```

Three things worth understanding here:

**`content_type="tutorial.casestudypage"`** tells the loader which Django
model to instantiate. It's the app label plus the model name, lowercased —
the same format Django uses for `ContentType`.

**`__wagtail_parent_page`** is a special attribute that `PageLoader` reads
to know where in the Wagtail page tree to attach the new page. It's removed
before Django sees the attributes, so it won't cause an "unexpected field"
error.

**`BlobRef(Key(type="url", value=hero_url))`** deserves a closer look:

!!! warning "BlobRef is lazy — the image doesn't need to exist yet"
    `BlobRef` is a *reference*, not a value. It says "when you load this
    page, set `hero_image` to whatever Wagtail `Image` was created from this
    URL." The loader resolves it at load time, after the image has been
    extracted and transformed. You don't need the image to exist when you
    return this `Spec` — isekai handles the ordering for you.
```

- [ ] **Step 2: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: rewrite tutorial Step 7 with BlobRef warning and transformer-as-description framing"
```

---

### Task 8: Rewrite Step 8 (Loading + Running)

**Files:**
- Modify: `docs/tutorial.md` (Step 8)

- [ ] **Step 1: Replace Step 8**

Find `## Step 8: Loading — writing to the database` and replace the entire section with:

```markdown
## Step 8: Running the pipeline

With all the components wired in, your `Resource` model is complete:

```python
class Resource(AbstractResource):
    seeders = [CaseStudySeeder()]
    extractors = [HTTPExtractor()]
    miners = [CaseStudyMiner()]
    transformers = [
        ImageTransformer(),
        CaseStudyTransformer(),
    ]
    loaders = [
        PageLoader(),
        ModelLoader(),
    ]
```

The `loaders` list has two entries because there are two kinds of objects
to create. `PageLoader` handles `CaseStudyPage` objects — it reads the
`__wagtail_parent_page` attribute, creates the page under the right parent
in the Wagtail tree, and strips the special attribute before saving.
`ModelLoader` handles everything else, including the Wagtail `Image`
objects that `ImageTransformer` produces from the downloaded image resources.

!!! note "Isekai handles dependency ordering automatically"
    One of the trickier parts of a content migration is figuring out what
    to create first. Pages reference images; images need to exist before
    pages can be saved. Isekai analyses the dependency graph across all
    your `Spec` objects and determines the correct creation order
    automatically — you don't need to think about it.

    For cases where dependencies form a cycle (object A references object B
    which references object A), isekai uses a partial construction strategy
    to break the cycle and resolve all references correctly. See
    [Dependency Resolution](reference/dependency-resolution.md) for a full
    explanation of how this works.

Run the pipeline:

```bash
python manage.py isekai
```

The command displays the pipeline configuration and prompts
`Start pipeline? [y/N]:` before running. Press `y` to proceed.

The pipeline runs in a fixed sequence:

1. **Seed** — 260 case study resources created at `SEEDED`
2. **Extract** — HTML fetched, resources move to `EXTRACTED`
3. **Mine** — images discovered, new `url:` resources created at `SEEDED`
4. **Extract** (again) — image files downloaded, move to `EXTRACTED`
5. **Mine** (again) — no new resources found; loop exits
6. **Transform** — case study resources produce `CaseStudyPage` Specs, image resources produce `Image` Specs
7. **Load** — Wagtail pages and images written to the database

If the pipeline stops partway through — a network error, a timeout, a
keyboard interrupt — run it again. Isekai skips resources that have
already moved past a stage, so nothing gets re-fetched or re-processed.

Open the Wagtail admin and navigate to the parent page. You should find
all 260 case study pages nested beneath it, each with title, category,
fund name, hero image, introduction, and body sections populated.
```

- [ ] **Step 2: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: rewrite tutorial Step 8 with loader explanation, dependency resolution note, and resumability"
```

---

### Task 9: Rewrite the closing

**Files:**
- Modify: `docs/tutorial.md` (closing section)

- [ ] **Step 1: Replace the closing**

Find `## What's next` and replace from there to the end of the file with:

```markdown
## What you built

You started with a deadline and a blank file. Now 260 case studies are
in Wagtail — titles, categories, fund names, hero images, body sections,
all of it. The pipeline handled the ordering, the retries, the inconsistent
HTML structure across older and newer pages. You described what each stage
should do; isekai did the coordination.

!!! success "What we learned"
    - **Understand the shape of your data before writing any code.** Five
      minutes with a sitemap and a few representative pages tells you what
      fields exist and what edge cases to design for.
    - **Separate fetching from parsing from loading.** When something
      breaks, you'll know exactly which stage failed and why — and you
      won't re-fetch two hundred pages to try again.
    - **Normalize image URLs at mine time, not transform time.** CMS image
      URLs are often variants of the original. Mine the canonical URL so
      you download the full-quality image once.
    - **If the pipeline stops, run it again.** Isekai picks up where it
      left off.

## What's next

The same pattern scales to every other content type on the site. News
articles, team bios, funding pages — each one gets a seeder to find them,
a parser to extract the fields, and a transformer to map them to the right
Wagtail page type. The pipeline infrastructure you've built here handles
all of them.

A few things a production migration will add:

- **URL normalization** — the same image URL might appear with and without
  a trailing slash; deduplicate with a normalizer before seeding
- **Image fallbacks** — some hero images may return 404; add a null check
  in the transformer or handle the error in your miner
- **Authenticated pages** — some sites require session cookies; extend
  `HTTPExtractor` or replace it with a custom extractor that manages auth
- **Multiple content types** — see the how-to guides for seeders,
  extractors, miners, transformers, and loaders
```

- [ ] **Step 2: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: rewrite tutorial closing with reflection paragraph and What we learned callout"
```

---

### Task 10: Create the dependency resolution placeholder page

**Files:**
- Create: `docs/reference/dependency-resolution.md`

- [ ] **Step 1: Create the placeholder**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/reference/dependency-resolution.md
git commit -m "docs: add dependency resolution placeholder page"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Opening narrative arc (5 beats) | Task 1 |
| Step 0 tip callout | Task 2 |
| Step 1 framed as existing model | Task 3 |
| Step 2 empty-first Resource, one-subclass note | Task 3 |
| Step 3 warmer prose + wire-in example | Task 4 |
| Step 4 HTTPExtractor explanation | Task 4 |
| Step 5 tip callout + parser design notes | Task 5 |
| Step 6 seen-set note + image URL variant warning | Task 6 |
| Step 7 BlobRef warning + transformer-as-description framing | Task 7 |
| Step 8 loader explanation + dependency resolution note + resumability | Task 8 |
| Closing reflection + What we learned callout | Task 9 |
| dependency-resolution.md placeholder | Task 10 |

All spec requirements covered. ✓

**Placeholder scan:** No TBDs, TODOs, or incomplete steps found. ✓

**Consistency check:** No cross-task type or method name inconsistencies — all code blocks are self-contained rewrites of existing tutorial sections. ✓
