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

## Step 1: The Wagtail destination model

Create a `CaseStudyPage` that represents where the migrated content will land:

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

The `body` StreamField uses `RichTextBlock` for each section, which preserves the HTML from the source page. The `hero_image` FK points at Wagtail's built-in `Image` model — isekai will create those Image objects automatically when it processes the mined image resources.

Find the parent page ID in the Wagtail admin by navigating to the page you want case studies nested under and noting the ID in the URL (e.g. `/cms/pages/3/`). Add it to your settings:

```python
# settings.py
CASE_STUDIES_PARENT_PAGE_ID = 3
```

## Step 2: Setting up isekai — the Resource model

Every isekai pipeline needs a concrete `Resource` model that wires all processors together. Create it alongside `CaseStudyPage`:

```python
# tutorial/models.py (continued)
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

Each list slot is a processor class. Isekai calls them in order at the appropriate pipeline stage. We'll fill these in as we build each component — for now, understand the overall shape:

- **seeders** — generate the initial list of resource keys (URLs to migrate)
- **extractors** — fetch data for each resource (HTTP requests)
- **miners** — discover related resources from extracted content (images)
- **transformers** — convert extracted content into a `Spec` describing what Django model to create
- **loaders** — write the `Spec` to the database

## Step 3: Seeding — getting the URL list

`SitemapSeeder` is built into isekai. It fetches a sitemap XML and creates a Resource for every URL. But we only want case study URLs, not the whole site:

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

The filter keeps only URLs that contain `/our-impact/case-studies/` and aren't the index page itself.

Individual pipeline stages can't be run in isolation — the full pipeline runs together in Step 8. Continue to the next step.

## Step 4: Extracting — fetching the HTML

`HTTPExtractor` is built in and handles retries, redirects, and MIME type detection. No custom code is needed. It's already in `Resource.extractors`:

```python
extractors = [HTTPExtractor()]
```

Individual pipeline stages can't be run in isolation — the full pipeline runs together in Step 8. Continue to the next step.

## Step 5: Parsing — understanding the HTML before wiring it in

Write and test parsing logic against local HTML files before connecting it to the pipeline. This decouples your parsing logic from the network and makes iteration fast.

**Collect fixture files** — pick five representative pages that cover the structural variations you've observed, download their HTML, and save them under `tutorial/tests/fixtures/case_studies/`. Choose pages that vary:

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

- `get_fund_name()` returns `None` (not `""`) when absent — older pages have no Related fund link at all
- `get_introduction()` returns `""` on older pages — the `text-lead` class simply doesn't exist
- `get_body_sections()` checks for `red-brown` WITHOUT `text-lead` to exclude the intro paragraph, which on newer pages carries both classes
- `get_body_image_urls()` only looks inside `div.editor`, not the entire document, so hero images aren't double-counted

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

Each fixture class tests something different: a page with no body images, a page with Charity Funds category, an older page with no intro, an older page with no fund link.

Checkpoint:

```bash
pytest tutorial/tests/test_parser.py -v
```

All tests should pass. Fix any selector mismatches before moving on — getting this right now means your pipeline will work without surprises.

## Step 6: Mining — discovering images

Mining discovers related resources from extracted content. Case study pages have a hero image and sometimes body images. Those images need to be downloaded before they can be attached to the Wagtail pages.

`CaseStudyMiner` uses the parser to find image URLs and emits them as new resources:

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

When the miner emits a `url:` resource, isekai seeds it for extraction. On the next extract pass, those image files are downloaded. Then `ImageTransformer` (already in `Resource.transformers`) picks them up and creates Wagtail `Image` objects.

## Step 7: Transforming — mapping HTML to Wagtail fields

A transformer takes an extracted resource and returns a `Spec` — a description of what model to create and what field values to give it.

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

Three things to explain here:

**`content_type="tutorial.casestudypage"`** tells the loader which Django model to instantiate. It's the app label plus the model name, lowercased.

**`BlobRef(Key(type="url", value=hero_url))`** is a lazy reference. Rather than embedding the image directly, it says "when you load this page, set `hero_image` to whatever Wagtail Image was created from this resource key." The loader resolves it at load time, after the image has been extracted and loaded.

**`__wagtail_parent_page`** is a special attribute that `PageLoader` reads to know where in the Wagtail page tree to attach the new page. Set it to the integer PK of your parent page.

## Step 8: Loading — writing to the database

The `loaders` list has two entries:

```python
loaders = [
    PageLoader(),
    ModelLoader(),
]
```

`PageLoader` handles `CaseStudyPage` objects. It reads the `__wagtail_parent_page` attribute, creates the page under the right parent in the Wagtail tree, and removes the special attribute before saving so Django doesn't see it as an unknown field.

`ModelLoader` handles everything else — including the Wagtail `Image` objects that `ImageTransformer` produces from the mined image resources.

Final checkpoint:

```bash
python manage.py isekai
```

The command displays the pipeline configuration and prompts `Start pipeline? [y/N]:` before running. Press `y` to proceed.

Watch the pipeline run. The sequence is:

1. **Seed** — 260 case study resources created at `SEEDED`
2. **Extract** — HTML fetched, resources move to `EXTRACTED`
3. **Mine** — images discovered, new `url:` resources created at `SEEDED`
4. **Extract** (again) — image files downloaded, move to `EXTRACTED`
5. **Mine** (again) — no new resources found; loop exits
6. **Transform** — case study resources produce `CaseStudyPage` Specs, image resources produce `Image` Specs
7. **Load** — Wagtail pages and images written to the database

Open the Wagtail admin and navigate to the parent page. You should find all 260 case study pages nested beneath it, each with title, category, fund name, hero image, introduction, and body sections populated.

## What's next

This tutorial covered the happy path. A production migration will hit a few more things:

- **URL normalization** — the same image URL might appear with and without a trailing slash; deduplicate with a normalizer before seeding
- **Image fallbacks** — some hero images may return 404; handle errors in your miner or add a null check in the transformer
- **Authenticated pages** — some sites require session cookies; extend `HTTPExtractor` or replace it with a custom extractor that manages auth
- **Other content types** — news articles, team bios, and funding pages all follow the same pattern: a seeder to find them, a parser to extract the fields, a transformer to map them to Wagtail models
