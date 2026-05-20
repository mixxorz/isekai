# Isekai Tutorial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write a full end-to-end tutorial (`docs/tutorial.md`) and runnable example app (`tutorial/`) teaching developers how to migrate case studies from a source website into Wagtail using isekai.

**Architecture:** A `tutorial/` Django app plugs into the existing `dev/` project. It contains a complete isekai pipeline: seeder, extractor, miner, parser, transformer, and loader targeting a `CaseStudyPage` Wagtail model. A narrative `docs/tutorial.md` walks through each stage with the problem, code, and checkpoint. Parser tests use local HTML fixture files in `tutorial/tests/fixtures/case_studies/`.

**Tech Stack:** Python, Django, Wagtail, BeautifulSoup4 (bs4), isekai, pytest

---

## File Map

**Create:**
- `tutorial/__init__.py` — makes tutorial a Python package
- `tutorial/models.py` — `CaseStudyPage` (Wagtail page) + `Resource` model wiring all processors
- `tutorial/seeders.py` — `CaseStudySeeder` (filters sitemap to case study URLs only)
- `tutorial/parsers.py` — `CaseStudyParser` (BeautifulSoup, extracts all fields)
- `tutorial/miners.py` — `CaseStudyMiner` (emits image resource keys)
- `tutorial/transformers.py` — `CaseStudyTransformer` (builds Spec for CaseStudyPage)
- `tutorial/tests/__init__.py`
- `tutorial/tests/fixtures/case_studies/case_study_01.html` — newer structure, 4 sections, body images, fund name (reopening-crosswater)
- `tutorial/tests/fixtures/case_studies/case_study_02.html` — newer structure, 2 sections, no body images (loch-restocking-for-barrhill-angling-club)
- `tutorial/tests/fixtures/case_studies/case_study_03.html` — newer structure, 0 body sections, Charity Funds category (brewing-up-strong-blend-of-skills)
- `tutorial/tests/fixtures/case_studies/case_study_04.html` — older flat structure, no p.text-lead intro, no sections, no fund link (watten-school-parent-council)
- `tutorial/tests/fixtures/case_studies/case_study_05.html` — older flat structure, Charity Funds, no fund link (fischy-music)
- `tutorial/tests/test_parser.py` — parser tests against all five fixtures
- `docs/tutorial.md` — the narrative tutorial document

**Modify:**
- `dev/testproject/settings.py` — add `'tutorial'` to `INSTALLED_APPS`, add `CASE_STUDIES_PARENT_PAGE_ID` setting

---

## Task 1: Create the tutorial app skeleton

**Files:**
- Create: `tutorial/__init__.py`
- Create: `tutorial/tests/__init__.py`
- Modify: `dev/testproject/settings.py`

- [ ] **Step 1: Create the package files**

```bash
mkdir -p tutorial/tests
touch tutorial/__init__.py
touch tutorial/tests/__init__.py
```

- [ ] **Step 2: Add tutorial to INSTALLED_APPS and add the parent page setting**

In `dev/testproject/settings.py`, change:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'isekai',
    'testapp',
]
```

to:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'isekai',
    'testapp',
    'tutorial',
]

# Tutorial: ID of the Wagtail page under which CaseStudyPages will be created.
# Set this to the pk of your case studies index page in the Wagtail admin.
CASE_STUDIES_PARENT_PAGE_ID = 1
```

- [ ] **Step 3: Verify Django recognises the app**

```bash
PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python dev/manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add tutorial/__init__.py tutorial/tests/__init__.py dev/testproject/settings.py
git commit -m "feat(tutorial): scaffold tutorial app and settings"
```

---

## Task 2: Define CaseStudyPage and Resource models

**Files:**
- Create: `tutorial/models.py`

- [ ] **Step 1: Write `tutorial/models.py`**

```python
from django.conf import settings
from django.db import models
from wagtail.fields import RichTextField, StreamField
from wagtail import blocks
from wagtail.images.models import AbstractImage
from wagtail.models import Page

from isekai.contrib.wagtail.loaders import PageLoader
from isekai.contrib.wagtail.transformers import ImageTransformer
from isekai.extractors import HTTPExtractor
from isekai.models import AbstractResource
from isekai.loaders import ModelLoader

from tutorial.miners import CaseStudyMiner
from tutorial.seeders import CaseStudySeeder
from tutorial.transformers import CaseStudyTransformer


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

Note: `CaseStudyMiner`, `CaseStudySeeder`, and `CaseStudyTransformer` are imported here but defined in later tasks. The models file will not be importable until those tasks are complete.

- [ ] **Step 2: Commit the models file**

```bash
git add tutorial/models.py
git commit -m "feat(tutorial): add CaseStudyPage and Resource models"
```

---

## Task 3: Write `CaseStudySeeder`

**Files:**
- Create: `tutorial/seeders.py`

- [ ] **Step 1: Write `tutorial/seeders.py`**

```python
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

- [ ] **Step 2: Verify it imports cleanly**

```bash
PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python -c "from tutorial.seeders import CaseStudySeeder; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add tutorial/seeders.py
git commit -m "feat(tutorial): add CaseStudySeeder"
```

---

## Task 4: Download HTML fixture files

**Files:**
- Create: `tutorial/tests/fixtures/case_studies/case_study_01.html` — downloaded from foundationscotland.org.uk
- Create: `tutorial/tests/fixtures/case_studies/case_study_02.html`
- Create: `tutorial/tests/fixtures/case_studies/case_study_03.html`
- Create: `tutorial/tests/fixtures/case_studies/case_study_04.html`
- Create: `tutorial/tests/fixtures/case_studies/case_study_05.html`

These are real pages downloaded from foundationscotland.org.uk. The tutorial fictions the site name as "Cairngorm Foundation" in prose, but uses the real HTML as fixtures so the parser is tested against actual markup.

The real site's HTML structure (discovered by inspection):
- Title: `<h1 class="heading-primary">`
- Category: `<ul class="list-meta"> li` containing `<strong>Category:</strong>` + `<a class="link">`
- Fund name: `<ul class="list-meta"> li` containing `<strong>Related fund:</strong>` + `<a>`
- Hero image: `<figure class="... wide ..."> img` (relative `/sites/default/files/...` src)
- Intro (newer pages only): `<p class="text-lead">`
- Section headings (newer pages only): `<p class="red-brown">` (not combined with `text-lead`)
- Body images: `<img>` inside `<div class="editor section">`

- [ ] **Step 1: Create fixture directory and download pages**

```bash
mkdir -p tutorial/tests/fixtures/case_studies

curl -s -A "Mozilla/5.0" \
  "https://www.foundationscotland.org.uk/our-impact/case-studies/reopening-crosswater" \
  -o "tutorial/tests/fixtures/case_studies/case_study_01.html"

curl -s -A "Mozilla/5.0" \
  "https://www.foundationscotland.org.uk/our-impact/case-studies/loch-restocking-for-barrhill-angling-club" \
  -o "tutorial/tests/fixtures/case_studies/case_study_02.html"

curl -s -A "Mozilla/5.0" \
  "https://www.foundationscotland.org.uk/our-impact/case-studies/brewing-up-strong-blend-of-skills" \
  -o "tutorial/tests/fixtures/case_studies/case_study_03.html"

curl -s -A "Mozilla/5.0" \
  "https://www.foundationscotland.org.uk/our-impact/case-studies/watten-school-parent-council" \
  -o "tutorial/tests/fixtures/case_studies/case_study_04.html"

curl -s -A "Mozilla/5.0" \
  "https://www.foundationscotland.org.uk/our-impact/case-studies/fischy-music" \
  -o "tutorial/tests/fixtures/case_studies/case_study_05.html"
```

Expected: 5 files, each ~49–55 KB.

- [ ] **Step 2: Commit the fixtures**

```bash
git add tutorial/tests/fixtures/
git commit -m "feat(tutorial): add downloaded HTML fixture files for parser testing"
```

---

## Task 5: Write `CaseStudyParser`

**Files:**
- Create: `tutorial/parsers.py`

- [ ] **Step 1: Write `tutorial/parsers.py`**

The real site HTML structure (verified against downloaded fixtures):
- Title: `<h1 class="heading-primary">`
- Category: first `<a>` inside the `<li>` containing `<strong>Category:</strong>` in `<ul class="list-meta">`
- Fund: first `<a>` inside the `<li>` containing `<strong>Related fund:</strong>` in `<ul class="list-meta">`
- Hero: `<figure class="... wide ..."> img` — the `wide` class identifies the hero figure
- Intro (newer pages): `<p class="text-lead">` — absent on older pages, returns `""` gracefully
- Section headings (newer pages): `<p class="red-brown">` without `text-lead` — absent on older pages
- Body images: `<img>` inside any `<div>` with both `section` and `editor` classes

```python
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
        # The hero figure has the "wide" class among its figure classes
        hero_fig = self.soup.find("figure", class_="wide")
        if hero_fig is None:
            return None
        img = hero_fig.find("img")
        if img is None:
            return None
        src = img.get("src")
        return str(src) if src else None

    def get_introduction(self) -> str:
        # Newer pages have p.text-lead; older pages have no dedicated intro element
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

- [ ] **Step 2: Verify it imports cleanly**

```bash
PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python -c "from tutorial.parsers import CaseStudyParser; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add tutorial/parsers.py
git commit -m "feat(tutorial): add CaseStudyParser"
```

---

## Task 6: Write parser tests

**Files:**
- Create: `tutorial/tests/test_parser.py`

- [ ] **Step 1: Write `tutorial/tests/test_parser.py`**

Expected values verified against actual downloaded fixtures.

```python
from pathlib import Path

from tutorial.parsers import CaseStudyParser

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "case_studies"


def load_fixture(filename: str) -> CaseStudyParser:
    html = (FIXTURES_DIR / filename).read_text(encoding="utf-8")
    return CaseStudyParser(html)


class TestCaseStudyParserFixture01:
    """case_study_01.html: reopening-crosswater — newer structure, 4 sections, body images"""

    def setup_method(self):
        self.parser = load_fixture("case_study_01.html")

    def test_get_title(self):
        assert self.parser.get_title() == "Reopening The Crosswater"

    def test_get_category(self):
        assert self.parser.get_category() == "Community Funds"

    def test_get_fund_name(self):
        assert self.parser.get_fund_name() == "Barrhill Community Interest Company"

    def test_get_hero_image_url(self):
        url = self.parser.get_hero_image_url()
        assert url is not None
        assert "sites/default/files" in url

    def test_get_introduction(self):
        intro = self.parser.get_introduction()
        assert "Barrhill" in intro
        assert intro != ""

    def test_get_body_sections_count(self):
        sections = self.parser.get_body_sections()
        assert len(sections) == 4

    def test_get_body_sections_contain_headings(self):
        sections = self.parser.get_body_sections()
        full_text = " ".join(sections)
        assert "The Background" in full_text
        assert "Community Ownership" in full_text
        assert "The Impact" in full_text

    def test_get_body_image_urls(self):
        urls = self.parser.get_body_image_urls()
        assert len(urls) == 2
        assert all("sites/default/files" in u for u in urls)


class TestCaseStudyParserFixture02:
    """case_study_02.html: loch-restocking — newer structure, 2 sections, no body images"""

    def setup_method(self):
        self.parser = load_fixture("case_study_02.html")

    def test_get_title(self):
        assert self.parser.get_title() == "Loch Restocking for Barrhill Angling Club"

    def test_get_hero_image_url_present(self):
        # This page has a hero image
        assert self.parser.get_hero_image_url() is not None

    def test_get_fund_name(self):
        assert self.parser.get_fund_name() == "Barrhill Community Interest Company"

    def test_get_body_sections_count(self):
        sections = self.parser.get_body_sections()
        assert len(sections) == 2

    def test_get_body_image_urls_empty(self):
        assert self.parser.get_body_image_urls() == []

    def test_get_introduction(self):
        intro = self.parser.get_introduction()
        assert "Barrhill Angling Club" in intro


class TestCaseStudyParserFixture03:
    """case_study_03.html: brewing-up-strong-blend-of-skills — Charity Funds, 0 sections"""

    def setup_method(self):
        self.parser = load_fixture("case_study_03.html")

    def test_get_category(self):
        assert self.parser.get_category() == "Charity Funds"

    def test_get_title(self):
        assert self.parser.get_title() == "Brewing up a strong blend of skills"

    def test_get_fund_name(self):
        assert self.parser.get_fund_name() == "Bairdwatson Charitable Trust"

    def test_get_body_sections_empty(self):
        # This page has intro text but no red-brown section headings
        assert self.parser.get_body_sections() == []

    def test_get_introduction(self):
        intro = self.parser.get_introduction()
        assert "Bairdwatson" in intro


class TestCaseStudyParserFixture04:
    """case_study_04.html: watten-school-parent-council — older flat structure, no intro, no fund"""

    def setup_method(self):
        self.parser = load_fixture("case_study_04.html")

    def test_get_title(self):
        assert "Watten" in self.parser.get_title()

    def test_get_body_sections_empty(self):
        # Older flat pages have no p.red-brown section headings
        assert self.parser.get_body_sections() == []

    def test_get_hero_image_url_present(self):
        assert self.parser.get_hero_image_url() is not None

    def test_get_introduction_empty(self):
        # Older pages have no p.text-lead
        assert self.parser.get_introduction() == ""

    def test_get_fund_name_none(self):
        # This page has no Related fund link
        assert self.parser.get_fund_name() is None

    def test_get_category(self):
        assert self.parser.get_category() == "Community Funds"


class TestCaseStudyParserFixture05:
    """case_study_05.html: fischy-music — older flat structure, Charity Funds, no fund"""

    def setup_method(self):
        self.parser = load_fixture("case_study_05.html")

    def test_get_title(self):
        assert "mental health" in self.parser.get_title().lower()

    def test_get_category(self):
        assert self.parser.get_category() == "Charity Funds"

    def test_get_fund_name_none(self):
        assert self.parser.get_fund_name() is None

    def test_get_introduction_empty(self):
        assert self.parser.get_introduction() == ""

    def test_get_body_sections_empty(self):
        assert self.parser.get_body_sections() == []

    def test_get_body_image_urls_empty(self):
        assert self.parser.get_body_image_urls() == []
```

- [ ] **Step 2: Run the tests and verify they fail (parser not yet tested)**

```bash
PYTHONPATH=/Users/mixxorz/Projects/isekai uv run pytest tutorial/tests/test_parser.py -v
```

Expected: All tests PASS (fixtures and parser are already written by this point). If any fail, fix `tutorial/parsers.py` selectors to match the fixture HTML.

- [ ] **Step 3: Commit**

```bash
git add tutorial/tests/test_parser.py
git commit -m "feat(tutorial): add parser tests against HTML fixtures"
```

---

## Task 7: Write `CaseStudyMiner`

**Files:**
- Create: `tutorial/miners.py`

- [ ] **Step 1: Write `tutorial/miners.py`**

```python
from bs4 import BeautifulSoup

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

- [ ] **Step 2: Verify it imports cleanly**

```bash
PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python -c "from tutorial.miners import CaseStudyMiner; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add tutorial/miners.py
git commit -m "feat(tutorial): add CaseStudyMiner"
```

---

## Task 8: Write `CaseStudyTransformer`

**Files:**
- Create: `tutorial/transformers.py`

- [ ] **Step 1: Write `tutorial/transformers.py`**

```python
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

- [ ] **Step 2: Verify it imports cleanly**

```bash
PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python -c "from tutorial.transformers import CaseStudyTransformer; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add tutorial/transformers.py
git commit -m "feat(tutorial): add CaseStudyTransformer"
```

---

## Task 9: Create migrations and verify Django check

**Files:**
- Create: `tutorial/migrations/` (generated)

- [ ] **Step 1: Run makemigrations for the tutorial app**

```bash
PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python dev/manage.py makemigrations tutorial
```

Expected: `Migrations for 'tutorial': tutorial/migrations/0001_initial.py`

- [ ] **Step 2: Run Django system check**

```bash
PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python dev/manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Run migrations**

```bash
PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python dev/manage.py migrate
```

Expected: Migration output with no errors.

- [ ] **Step 4: Run the full test suite to confirm nothing is broken**

```bash
PYTHONPATH=/Users/mixxorz/Projects/isekai uv run pytest tutorial/tests/test_parser.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tutorial/migrations/
git commit -m "feat(tutorial): add initial migrations"
```

---

## Task 10: Write `docs/tutorial.md`

**Files:**
- Create: `docs/tutorial.md`

This is the narrative document. Write it in full — no placeholders. The tone is practical and first-person.

- [ ] **Step 1: Write `docs/tutorial.md`**

The document should contain these sections in order. Write each section fully:

```markdown
# Tutorial: Migrating Content into Wagtail with Isekai

## Introduction

A brief framing: you've been handed a Wagtail site rebuild project and need to migrate the old site's content. Isekai is a Django library that automates this through an ETL (Extract, Transform, Load) pipeline. This tutorial walks through a real migration: moving case studies from the old Cairngorm Foundation website into a new Wagtail site.

By the end, you'll have a working isekai pipeline that seeds URLs, fetches pages, mines images, parses content, and loads it into Wagtail as CaseStudyPage objects.

## Prerequisites

- A working Django + Wagtail project
- Python 3.11+
- isekai installed: `pip install isekai`
- BeautifulSoup4 installed: `pip install beautifulsoup4`

## Step 0: Planning — What to migrate

Explain the strategy: analyse the sitemap to find sections with the most direct children, since those are usually serialized content (blogs, news, case studies) that will have a consistent page structure and therefore be easy to migrate in bulk.

Show this Python script:

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

Show the output:
     260  /our-impact/case-studies/
      53  /about-us/our-news/
      42  /apply-for-funding/funding-available/
     ...

Explain: 260 case study pages, each with a consistent structure. That's the target.

Then: inspect a single case study page. List what we can extract:
- Title — from `<h1 class="case-study__title">`
- Category — from the metadata list
- Fund name — from the metadata list
- Hero image — from `<div class="case-study__hero"> img`
- Introduction — from `<p class="case-study__intro">`
- Body — from `<h2>` sections inside `<div class="case-study__body">`

## Step 1: The Wagtail destination model

Show the CaseStudyPage model (copy from tutorial/models.py, explain each field and why it maps to that source field).

Show where to look in the Wagtail admin to find the parent page ID, and explain the CASE_STUDIES_PARENT_PAGE_ID setting.

## Step 2: Setting up isekai — the Resource model

Explain the Resource model: it's the central object that connects all processors. Show the skeleton Resource model with empty lists first, then explain we'll fill these in as we build each component.

Show the final Resource model from tutorial/models.py and explain what each processor does at a high level.

## Step 3: Seeding — getting the URL list

Explain that SitemapSeeder fetches a sitemap and creates a Resource for each URL. But we only want case study URLs, not the whole site.

Show CaseStudySeeder (copy from tutorial/seeders.py) and explain the filter.

Show the checkpoint:
    python manage.py isekai

Expected output: table showing CaseStudySeeder, resource count after seeding.

## Step 4: Extracting — fetching the HTML

Explain that HTTPExtractor is built in and handles retries and MIME detection. No custom code needed.

Show adding HTTPExtractor() to the Resource.extractors list.

Checkpoint: after running isekai again, resources move to EXTRACTED status and text_data holds the raw HTML.

## Step 5: Parsing — understanding the HTML before wiring it in

Explain the parser-first approach: write and test parsing logic against local HTML files before connecting it to the pipeline. This makes iteration fast and isolates bugs.

Explain how to collect fixture files: pick 5 representative pages, save their HTML locally. Choose pages that vary in structure.

Show CaseStudyParser (copy from tutorial/parsers.py) with explanation of each method and its CSS selector.

Show the test file (copy from tutorial/tests/test_parser.py) and explain why each fixture tests something different.

Checkpoint:
    pytest tutorial/tests/test_parser.py -v

Expected: all tests pass.

## Step 6: Mining — discovering images

Explain that mining discovers related resources from extracted content. Images on the case study pages need to be downloaded before they can be assigned as hero images.

Show CaseStudyMiner (copy from tutorial/miners.py) and how it uses the parser.

Explain: when the pipeline mines a new `url:` resource, it schedules it for extraction. The built-in ImageTransformer (added to Resource.transformers) handles turning those image blobs into Wagtail Image objects.

## Step 7: Transforming — mapping HTML to Wagtail fields

Explain that a transformer takes an extracted resource and returns a Spec — a description of what Django model to create and what field values to give it.

Show CaseStudyTransformer (copy from tutorial/transformers.py). Explain:
- `content_type="tutorial.casestudypage"` tells the loader what model to create
- `BlobRef(Key(...))` is a lazy reference — it tells the loader "set hero_image to the Wagtail Image created from this resource key"
- `__wagtail_parent_page` tells PageLoader where to attach the page in the Wagtail tree

## Step 8: Loading — writing to the database

Explain PageLoader vs ModelLoader. PageLoader handles the Wagtail-specific tree positioning using `__wagtail_parent_page`. ModelLoader handles everything else (including the Wagtail Image objects created from mined images).

Show the fully assembled Resource model.

Final checkpoint:
    python manage.py isekai

Walk through what you should see: resources seeded → extracted → mined (images discovered) → extracted again (images fetched) → mined again → transformed → loaded. Then open the Wagtail admin and find the case study pages under the parent page.

## What's next

Brief mention of what wasn't covered: URL normalization for deduplication, image fallback strategies for 404s, custom extractors for authenticated pages, and transformers for other content types.
```

- [ ] **Step 2: Commit**

```bash
git add docs/tutorial.md
git commit -m "docs: add isekai tutorial"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|---|---|
| Step 0: sitemap analysis script | Task 10 (tutorial.md Step 0) |
| Step 1: CaseStudyPage model | Task 2 |
| Step 2: CaseStudySeeder with URL filter | Task 3 |
| Step 2: CASE_STUDIES_PARENT_PAGE_ID setting | Task 1 |
| Step 3: HTTPExtractor (no custom code) | Task 10 (tutorial.md Step 4) |
| Step 4: HTML fixtures (5+ varied) | Task 4 |
| Step 4: CaseStudyParser with all methods | Task 5 |
| Step 4: test_parser.py | Task 6 |
| Step 5: CaseStudyMiner using parser | Task 7 |
| Step 6: CaseStudyTransformer with BlobRef + parent page | Task 8 |
| Step 7: PageLoader + ModelLoader | Task 2 + Task 10 |
| Tutorial narrative doc | Task 10 |
| Example app in tutorial/ | Tasks 1–9 |

All spec requirements covered.

### Type consistency check

- `CaseStudyParser.__init__(html: str)` — used consistently in miners.py and transformers.py
- `CaseStudyParser.get_hero_image_url() -> str | None` — handled with `if hero_url:` in both miner and transformer
- `CaseStudyParser.get_body_image_urls() -> list[str]` — used in miner Task 7
- `CaseStudyParser.get_body_sections() -> list[str]` — used in transformer Task 8 with correct StreamField value format
- `BlobRef(Key(type="url", value=hero_url))` — matches `BlobRef(key: Key)` constructor in types.py
- `Spec(content_type=..., attributes=...)` — matches Spec dataclass definition
- `__wagtail_parent_page` attribute key — matches `PageLoader._parent_page_prefix` exactly

### Placeholder scan

No TBDs, TODOs, or vague steps. Task 10 uses an inline content description rather than full prose for tutorial.md — the implementor should write the full prose following the outlined structure. All code blocks are complete and runnable.
