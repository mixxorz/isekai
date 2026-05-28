# Tutorial Production Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update isekai's default resource key length and restructure the Wagtail tutorial so it teaches production-ready migration patterns while keeping the Cairngorm case study.

**Architecture:** Make the library change first with a focused regression test, then rewrite the tutorial in small sections that preserve the existing narrative. The tutorial should use normalized image keys consistently, move body images into Wagtail image blocks, explain lazy refs accurately, and keep advanced MAP-derived patterns as optional callouts.

**Tech Stack:** Python, Django models, pytest, Wagtail StreamField/RichText examples, Markdown documentation, tox/ruff/pyright.

---

## File Structure

- Modify: `isekai/models.py` — increase `AbstractResource.key.max_length` to 1024.
- Modify: `tests/test_models.py` — add a regression test for the default concrete resource key field length.
- Modify: `docs/tutorial.md` — restructure the tutorial and update all examples/prose.
- Reference only: `docs/superpowers/specs/2026-05-28-tutorial-production-restructure-design.md` — approved design; do not edit unless implementation reveals a spec error.
- Reference only: `../map-website/map/content_migration/*` — source of real migration patterns; do not edit.

## Important Constraints

- Keep imports at the top of Python examples. Do not introduce inline imports in tutorial code samples.
- Do not recommend `pip install "isekai-django[wagtail]"`; use `pip install isekai-django`.
- Do not tell readers to override `Resource.key` for normal URL migrations after the default changes to 1024.
- Keep the Cairngorm scenario. Do not rewrite the tutorial as a MAP news migration.
- Advanced patterns should be callouts or optional sections, not a second full tutorial track.

---

### Task 1: Increase Default Resource Key Length

**Files:**
- Modify: `tests/test_models.py`
- Modify: `isekai/models.py`

- [ ] **Step 1: Add the failing regression test**

Add this test inside `TestAbstractResource` in `tests/test_models.py`, after `test_model_creation`:

```python
    def test_key_field_defaults_to_url_friendly_length(self):
        """Resource keys should be long enough for real migrated URLs."""
        key_field = ConcreteResource._meta.get_field("key")
        assert key_field.max_length == 1024
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
uv run pytest tests/test_models.py::TestAbstractResource::test_key_field_defaults_to_url_friendly_length -v
```

Expected: FAIL because `key_field.max_length` is currently `255`.

- [ ] **Step 3: Update the model field**

In `isekai/models.py`, change the `AbstractResource.key` field to:

```python
    key = models.CharField(max_length=1024, primary_key=True, db_index=True)
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
uv run pytest tests/test_models.py::TestAbstractResource::test_key_field_defaults_to_url_friendly_length -v
```

Expected: PASS.

- [ ] **Step 5: Run model tests**

Run:

```bash
uv run pytest tests/test_models.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the library change**

Run:

```bash
git add isekai/models.py tests/test_models.py
git commit -m "Increase default resource key length"
```

Expected: commit succeeds and includes only `isekai/models.py` and `tests/test_models.py`.

---

### Task 2: Update Tutorial Setup And Destination Model

**Files:**
- Modify: `docs/tutorial.md`

- [ ] **Step 1: Update prerequisites and opening claims**

In `docs/tutorial.md`, update the prerequisites list to:

```markdown
- A working Django + Wagtail project
- Python 3.10+
- isekai installed: `pip install isekai-django`
```

Remove the separate BeautifulSoup install bullet. BeautifulSoup is already a package dependency.

In the opening, replace any claim that implies every page gets every optional field with wording like:

```markdown
By the end you'll have a pipeline that handles the page content, hero images,
body images where present, categories, and fund names — and if it stops halfway
through, you can run it again and it'll skip everything that already worked.
```

- [ ] **Step 2: Update the destination model example**

Replace the `CaseStudyPage.body` StreamField snippet with one that supports text sections and images:

```python
    body = StreamField(
        [
            ("section", blocks.RichTextBlock()),
            (
                "image",
                blocks.StructBlock(
                    [
                        ("image", ImageChooserBlock()),
                        ("caption", blocks.CharBlock(required=False)),
                    ]
                ),
            ),
        ],
        blank=True,
        use_json_field=True,
    )
```

Also update the imports in the tutorial code sample to include:

```python
from wagtail.images.blocks import ImageChooserBlock
```

- [ ] **Step 3: Update destination model prose**

Replace the prose that says the body only preserves source HTML with:

```markdown
The `body` StreamField has one block for rich text sections and one for images.
That matters: body images should become Wagtail image references, not old
`<img src="...">` tags pointing back at the source site.
```

- [ ] **Step 4: Self-check this section**

Run:

```bash
git diff -- docs/tutorial.md
```

Expected: the diff updates only the prerequisites, opening claim, destination model sample, and nearby prose.

- [ ] **Step 5: Commit setup/tutorial model changes**

Run:

```bash
git add docs/tutorial.md
git commit -m "docs: update tutorial setup and destination model"
```

Expected: commit succeeds.

---

### Task 3: Update Resource Model, Admin Registration, And Processor Ordering

**Files:**
- Modify: `docs/tutorial.md`

- [ ] **Step 1: Update final Resource model sample**

Ensure the full `Resource` sample in Step 2 shows processors in this order:

```python
class Resource(AbstractResource):
    seeders = [CaseStudySeeder()]
    extractors = [
        CaseStudyImageExtractor(),
        HTTPExtractor(),
    ]
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

Add imports for `CaseStudyImageExtractor` only if the optional extractor is shown as part of the final sample. If the tutorial keeps fallback extraction optional, keep the final sample as:

```python
    extractors = [HTTPExtractor()]
```

and explain that `CaseStudyImageExtractor()` goes before `HTTPExtractor()` when used.

- [ ] **Step 2: Add admin registration example**

After the Resource model setup, add this short example:

```python
# tutorial/admin.py
from django.contrib import admin

from isekai.admin import AbstractResourceAdmin

from tutorial.models import Resource


@admin.register(Resource)
class ResourceAdmin(AbstractResourceAdmin):
    pass
```

Add prose:

```markdown
This is not required for the pipeline, but it is useful during a migration.
The admin shows each resource's status and `last_error`, which makes failed
runs much easier to inspect.
```

- [ ] **Step 3: Correct processor ordering prose**

Replace the existing broad processor-ordering text with:

```markdown
Processor ordering depends on the stage:

- Seeders all run.
- Miners all run.
- Extractors are tried in order until one returns a resource.
- Transformers are tried in order until one returns a `Spec`.
- Loaders are tried in order until one returns created objects for the current load node.

That is why specific extractors go before generic extractors. If you add a
custom image extractor, put it before `HTTPExtractor()` so it gets first chance
at image URLs.
```

- [ ] **Step 4: Remove any custom key override guidance**

Search within `docs/tutorial.md` for `max_length=1024`, `key = models.CharField`, or guidance about overriding `Resource.key`. The tutorial should not recommend overriding it for normal URL-heavy migrations after Task 1.

Run:

```bash
rg "max_length=1024|key = models.CharField|override.*key|Resource.key" docs/tutorial.md
```

Expected: no recommendation to override `Resource.key` for normal URL migrations. It is acceptable if the tutorial mentions that isekai's default resource keys are long enough for URL migrations.

- [ ] **Step 5: Commit Resource/admin/order changes**

Run:

```bash
git add docs/tutorial.md
git commit -m "docs: clarify tutorial resource setup"
```

Expected: commit succeeds.

---

### Task 4: Add URL Normalization To Parser And Mining Examples

**Files:**
- Modify: `docs/tutorial.md`

- [ ] **Step 1: Update parser imports**

In the `tutorial/parsers.py` code sample, add top-level imports:

```python
import re
from urllib.parse import urljoin
```

Keep all imports at the top of the sample.

- [ ] **Step 2: Add parser URL helpers**

Inside `CaseStudyParser`, add helpers like this:

```python
    def normalize_image_url(self, src: str, base_url: str) -> tuple[str, str]:
        """Return (canonical_url, original_url) for an image src."""
        original_url = urljoin(base_url, src)
        canonical_url = original_url
        canonical_url = canonical_url.replace("_cropped", "")
        canonical_url = re.sub(r"__width-\d+(\.[^.]+)$", r"\1", canonical_url)
        canonical_url = re.sub(r"_\d+_\d+(\.[^.]+)$", r"\1", canonical_url)
        canonical_url = re.sub(r"-\d+x\d+(\.[^.]+)$", r"\1", canonical_url)
        return canonical_url, original_url
```

Use patterns that match the tutorial prose. If Cairngorm uses different variant URLs in the examples, adjust the regexes in both code and prose so they match.

- [ ] **Step 3: Update image parser methods**

Change `get_hero_image_url()` to accept `base_url` and return a dict:

```python
    def get_hero_image(self, base_url: str) -> dict[str, str] | None:
        hero_fig = self.soup.find("figure", class_="wide")
        if hero_fig is None:
            return None
        img = hero_fig.find("img")
        if img is None:
            return None
        src = img.get("src")
        if not src:
            return None
        url, original_url = self.normalize_image_url(str(src), base_url)
        return {
            "url": url,
            "original_src": original_url,
            "alt_text": str(img.get("alt", "")),
            "caption": "",
        }
```

Change `get_body_image_urls()` to `get_body_images(base_url)`:

```python
    def get_body_images(self, base_url: str) -> list[dict[str, str]]:
        images = []
        for div in self.soup.find_all("div", class_="editor"):
            for img in div.find_all("img"):
                src = img.get("src")
                if src:
                    url, original_url = self.normalize_image_url(str(src), base_url)
                    images.append(
                        {
                            "url": url,
                            "original_src": original_url,
                            "alt_text": str(img.get("alt", "")),
                            "caption": "",
                        }
                    )
        return images
```

- [ ] **Step 4: Update parser notes and tests in prose**

Update the prose and fixture test examples so they refer to `get_hero_image(base_url)` and `get_body_images(base_url)`.

Example assertion:

```python
    def test_get_body_images(self):
        images = self.parser.get_body_images("https://cairngormfoundation.org.uk/")
        assert len(images) == 2
        assert images[0]["url"].startswith("https://cairngormfoundation.org.uk/")
```

- [ ] **Step 5: Update miner example**

Change the miner to use the page URL as the base URL and emit metadata:

```python
        parser = CaseStudyParser(resource.text)
        mined: list[MinedResource] = []
        base_url = key.value

        hero_image = parser.get_hero_image(base_url)
        if hero_image:
            mined.append(
                MinedResource(
                    key=Key(type="url", value=hero_image["url"]),
                    metadata={
                        "alt_text": hero_image["alt_text"],
                        "caption": hero_image["caption"],
                        "original_src": hero_image["original_src"],
                    },
                )
            )

        for image in parser.get_body_images(base_url):
            mined.append(
                MinedResource(
                    key=Key(type="url", value=image["url"]),
                    metadata={
                        "alt_text": image["alt_text"],
                        "caption": image["caption"],
                        "original_src": image["original_src"],
                    },
                )
            )

        return mined
```

- [ ] **Step 6: Add deduplication and normalization prose**

Add prose explaining:

```markdown
Isekai deduplicates exact resource keys for you. Normalization is different:
it is how you make several source URL strings point at the same canonical key
before they reach the database.
```

- [ ] **Step 7: Commit parser/miner tutorial changes**

Run:

```bash
git add docs/tutorial.md
git commit -m "docs: add tutorial URL normalization"
```

Expected: commit succeeds.

---

### Task 5: Add Optional Image Fallback Extractor Pattern

**Files:**
- Modify: `docs/tutorial.md`

- [ ] **Step 1: Add fallback extractor section after HTTPExtractor explanation**

Add an optional section titled like:

```markdown
### Optional: Falling back when image originals 404
```

Use this code sample:

```python
# tutorial/extractors.py
import re

import requests

from isekai.extractors import HTTPExtractor
from isekai.types import Key


class CaseStudyImageExtractor(HTTPExtractor):
    def extract(self, key: Key, metadata: dict | None = None):
        if key.type != "url" or not self._is_image_url(key.value):
            return None

        try:
            return super().extract(key, metadata)
        except requests.exceptions.HTTPError as error:
            if error.response is None or error.response.status_code != 404:
                raise
            original_error = error

        for fallback_url in self._fallback_urls(key.value, metadata or {}):
            try:
                return super().extract(Key(type="url", value=fallback_url), metadata)
            except requests.exceptions.HTTPError:
                continue

        raise original_error

    def _is_image_url(self, url: str) -> bool:
        return url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))

    def _fallback_urls(self, url: str, metadata: dict) -> list[str]:
        urls = []
        original_src = metadata.get("original_src")
        if original_src and original_src != url:
            urls.append(original_src)
        urls.append(self._with_suffix(url, "_cropped"))
        urls.append(self._with_suffix(url, "_778_518"))
        return urls

    def _with_suffix(self, url: str, suffix: str) -> str:
        return re.sub(r"(\.[^.]+)$", rf"{suffix}\1", url)
```

- [ ] **Step 2: Add warning about source-specific fallback rules**

Add this prose below the code:

```markdown
Do not copy these suffixes blindly. They are examples of the kind of fallback
you might need after inspecting your source site. The important pattern is to
mine one canonical key, keep the original URL in metadata, and let a specific
image extractor try known fallbacks before the generic `HTTPExtractor` runs.
```

- [ ] **Step 3: Show processor ordering for optional extractor**

Add this snippet:

```python
extractors = [
    CaseStudyImageExtractor(max_retries=8, max_delay=300),
    HTTPExtractor(max_retries=8, max_delay=300),
]
```

Explain that the custom extractor must come first because extractors are tried in order.

- [ ] **Step 4: Commit fallback extractor docs**

Run:

```bash
git add docs/tutorial.md
git commit -m "docs: add image fallback extractor pattern"
```

Expected: commit succeeds.

---

### Task 6: Update Transformer Example For Rich Text And Body Image Refs

**Files:**
- Modify: `docs/tutorial.md`

- [ ] **Step 1: Update transformer imports**

In the `tutorial/transformers.py` sample, include top-level imports:

```python
from django.conf import settings
from wagtail.admin.rich_text.converters.editor_html import EditorHTMLConverter

from isekai.transformers import BaseTransformer
from isekai.types import BlobRef, BlobResource, Key, ResourceRef, Spec, TextResource

from tutorial.parsers import CaseStudyParser
```

- [ ] **Step 2: Add helper for body blocks**

Inside `CaseStudyTransformer`, add:

```python
    def build_body_blocks(
        self, parser: CaseStudyParser, base_url: str, converter: EditorHTMLConverter
    ) -> list[tuple[str, str | dict[str, object]]]:
        blocks: list[tuple[str, str | dict[str, object]]] = []

        for section in parser.get_body_sections():
            blocks.append(("section", converter.to_database_format(section)))

        for image in parser.get_body_images(base_url):
            image_key = Key(type="url", value=image["url"])
            blocks.append(
                (
                    "image",
                    {
                        "image": ResourceRef(image_key),
                        "caption": image["caption"],
                    },
                )
            )

        return blocks
```

- [ ] **Step 3: Update transform method**

Use the converter and normalized keys:

```python
    def transform(self, key: Key, resource: TextResource | BlobResource) -> Spec | None:
        if key.type != "url":
            return None
        if not isinstance(resource, TextResource):
            return None

        parser = CaseStudyParser(resource.text)
        title = parser.get_title()
        if not title:
            return None

        converter = EditorHTMLConverter()
        base_url = key.value

        attributes: dict = {
            "title": title,
            "category": parser.get_category(),
            "fund_name": parser.get_fund_name() or "",
            "introduction": converter.to_database_format(parser.get_introduction()),
            "body": self.build_body_blocks(parser, base_url, converter),
            "__wagtail_parent_page": settings.CASE_STUDIES_PARENT_PAGE_ID,
        }

        hero_image = parser.get_hero_image(base_url)
        if hero_image:
            hero_key = Key(type="url", value=hero_image["url"])
            attributes["hero_image"] = ResourceRef(hero_key)

        return Spec(
            content_type="tutorial.casestudypage",
            attributes=attributes,
        )
```

If the actual `PageLoader`/`ModelLoader` path in current isekai requires `hero_image_id = ResourceRef(hero_key).pk` rather than assigning the model instance to `hero_image`, use this in the tutorial instead:

```python
            attributes["hero_image_id"] = ResourceRef(hero_key).pk
```

Verify against `isekai/loaders.py` behavior before choosing. The loader supports FK field names and `_id` accessors.

- [ ] **Step 4: Update reference type prose**

Add this explanation near the transformer example:

```markdown
`ResourceRef` and `ModelRef` both support lazy dot notation. `ResourceRef(hero_key)`
resolves to the object created from that resource. `ResourceRef(hero_key).pk`
resolves to the eventual primary key. `ModelRef("images.CustomImage", pk=1).file.url`
looks up an existing model and resolves the requested attribute path at load time.
```

- [ ] **Step 5: Explain automatic ref validation**

Add prose:

```markdown
Isekai checks refs during transform. If this transformer returns a `ResourceRef`
for a key that was never seeded or mined, transform fails with an invalid-ref
error. That is why the miner and transformer must use the same normalized URL.
```

- [ ] **Step 6: Commit transformer tutorial changes**

Run:

```bash
git add docs/tutorial.md
git commit -m "docs: update tutorial transformer refs"
```

Expected: commit succeeds.

---

### Task 7: Add Optional Metadata-Only Resource Pattern

**Files:**
- Modify: `docs/tutorial.md`

- [ ] **Step 1: Add metadata-only callout after mining section**

Add a callout titled like:

```markdown
!!! note "Not every mined resource needs HTTP"
```

Use this prose:

```markdown
Sometimes a page reveals objects that do not need to be fetched: tags,
categories, embedded forms, or other snippets. You can still mine them as
resources with keys like `tag:community-funds` or `form:donate-now`. Because
the pipeline expects every resource to pass through extraction, pair those keys
with a no-op extractor that turns metadata into a `TextResource`.
```

- [ ] **Step 2: Add no-op extractor sample**

Add this code sample:

```python
# tutorial/extractors.py
from isekai.extractors import BaseExtractor
from isekai.types import Key, TextResource


class NoopExtractor(BaseExtractor):
    def extract(self, key: Key, metadata: dict | None = None) -> TextResource | None:
        if key.type not in {"tag", "form", "category"}:
            return None

        return TextResource(
            mime_type="text/plain",
            text=str(key),
            metadata=metadata or {},
        )
```

- [ ] **Step 3: Add ordering note**

Add:

```markdown
Put `NoopExtractor()` before `HTTPExtractor()`. Otherwise `HTTPExtractor` will
see a non-URL key, return `None`, and the no-op extractor still works, but
specific-first ordering keeps the configuration easier to read.
```

- [ ] **Step 4: Commit metadata-only docs**

Run:

```bash
git add docs/tutorial.md
git commit -m "docs: add metadata-only resource pattern"
```

Expected: commit succeeds.

---

### Task 8: Add Parser Report And Troubleshooting Sections

**Files:**
- Modify: `docs/tutorial.md`

- [ ] **Step 1: Add optional parser report command**

After parser tests, add an optional command example:

```python
# tutorial/management/commands/report_case_study_fixtures.py
from pathlib import Path

from django.core.management.base import BaseCommand

from tutorial.parsers import CaseStudyParser


class Command(BaseCommand):
    help = "Print parsed case study fixture summaries"

    def handle(self, *args, **options):
        fixtures_dir = Path("tutorial/tests/fixtures/case_studies")

        for fixture_path in sorted(fixtures_dir.glob("*.html")):
            parser = CaseStudyParser(fixture_path.read_text(encoding="utf-8"))
            base_url = "https://cairngormfoundation.org.uk/"

            self.stdout.write(f"\n{fixture_path.name}")
            self.stdout.write(f"  title: {parser.get_title() or '(missing)'}")
            self.stdout.write(f"  category: {parser.get_category() or '(missing)'}")
            self.stdout.write(f"  fund: {parser.get_fund_name() or '(missing)'}")
            self.stdout.write(f"  sections: {len(parser.get_body_sections())}")
            self.stdout.write(f"  body images: {len(parser.get_body_images(base_url))}")
```

- [ ] **Step 2: Add parser report prose**

Add:

```markdown
Tests tell you whether expected selectors still work. A report tells you
whether the parsed output looks sane across real fixture pages. Use both before
running the full pipeline.
```

- [ ] **Step 3: Add troubleshooting section near end**

Add a section titled:

```markdown
## Troubleshooting a real run
```

Include concise subsections for:

```markdown
### Find failed resources

```python
Resource.objects.exclude(last_error="").values("key", "status", "last_error")
```

### Invalid refs during transform

This means a transformer referenced a resource key that was never seeded or mined.
Check that the miner and transformer use the same normalized URL.

### Images that 404

If the image is optional, leave the reference out. If the source site has known
fallback patterns, add a specific image extractor before `HTTPExtractor()`.

### Missing parent page

If `PageLoader` cannot find `CASE_STUDIES_PARENT_PAGE_ID`, check the ID in the
Wagtail admin and make sure the setting is available to Django.

### Unknown content type

Use the lowercased `app_label.modelname` form, such as `tutorial.casestudypage`.
```

- [ ] **Step 4: Commit parser report/troubleshooting docs**

Run:

```bash
git add docs/tutorial.md
git commit -m "docs: add tutorial troubleshooting guidance"
```

Expected: commit succeeds.

---

### Task 9: Final Tutorial Accuracy Pass

**Files:**
- Modify: `docs/tutorial.md`

- [ ] **Step 1: Check for stale install guidance**

Run:

```bash
rg "isekai-django\[wagtail\]|beautifulsoup4" docs/tutorial.md
```

Expected: no matches unless `beautifulsoup4` appears only in explanatory prose that says it is already installed as a dependency.

- [ ] **Step 2: Check for stale source names**

Run:

```bash
rg "Foundation Scotland|MAP|map-website" docs/tutorial.md
```

Expected: no `Foundation Scotland`; no MAP implementation details in the main tutorial. It is acceptable if there is a generic phrase like "real migration" without naming MAP.

- [ ] **Step 3: Check normalized key consistency manually**

Review the miner and transformer samples in `docs/tutorial.md` and confirm both use:

```python
Key(type="url", value=image["url"])
```

Expected: no sample uses raw `src` or `original_src` as the resource key after normalization.

- [ ] **Step 4: Check processor-ordering claims**

Run:

```bash
rg "first one|first processor|tries them|all run|Loaders are tried" docs/tutorial.md
```

Expected: any ordering prose matches actual pipeline behavior: all seeders/miners run; extractors/transformers/loaders are first-result stages.

- [ ] **Step 5: Check code sample import style**

Scan changed Python code samples. Expected: no `from ... import ...` inside functions or methods.

- [ ] **Step 6: Commit final docs polish if needed**

If Step 1-5 found fixes, commit them:

```bash
git add docs/tutorial.md
git commit -m "docs: polish tutorial production rewrite"
```

If no fixes were needed, do not create an empty commit.

---

### Task 10: Run Full Verification

**Files:**
- No edits expected.

- [ ] **Step 1: Run the full test suite**

Run:

```bash
uv run pytest
```

Expected: PASS.

- [ ] **Step 2: Run lint and type checks**

Run:

```bash
uv run tox -e lint,type
```

Expected: PASS.

- [ ] **Step 3: Inspect final diff since the spec commits**

Run:

```bash
git status --short
git log --oneline -10
```

Expected: clean working tree. Recent commits should include the implementation commits from this plan.

- [ ] **Step 4: Record verification outcome**

In the final implementation summary, include:

```markdown
Verification:
- `uv run pytest` passed
- `uv run tox -e lint,type` passed
```

If a command fails, fix the failure before reporting completion.

## Self-Review

- Spec coverage: Tasks cover key length change, install guidance, processor ordering, admin inspection, URL normalization, image metadata, fallback extractor pattern, metadata-only resources, Wagtail rich text conversion, lazy ref dot notation, automatic ref validation, troubleshooting, and verification.
- Placeholder scan: No task contains TBD/TODO/fill-in instructions. Optional choices are explicit and bounded.
- Type consistency: Parser image methods return dictionaries with `url`, `original_src`, `alt_text`, and `caption`; miner and transformer examples both consume those keys. Ref examples use existing `BlobRef`, `ResourceRef`, `ModelRef`, and `Key` types.
