# Tutorial Redesign: Two Scoops Voice

**Date:** 2026-05-20
**Approach:** Hybrid — restructure opening and closing, polish the middle

---

## Goal

Rewrite `docs/tutorial.md` so it reads like a chapter from *Two Scoops of Django*:
warm, opinionated, first-person plural ("we"), with a narrative arc that earns the
pipeline before showing it. Target reader: a Django developer who has never done a
content migration and doesn't yet know why they need a structured approach.

---

## Narrative Arc (Opening)

Replace the current thin introduction with a proper chapter opener in five beats:

1. **The moment** — You're near the end of the project. The new Wagtail site is almost
   ready. But there's one thing you've been putting off: moving the content over from
   the old site. It's time.

2. **The naive plan** — You figure you'll write a quick script. Fetch the pages, parse
   the HTML, save them to the database. How hard could it be?

3. **Reality hits** — The HTML is inconsistent. Some pages have an intro paragraph, some
   don't. Images have unexpected URL structures. The case study pages need their hero
   images to exist *before* you can attach them — but the images come from the same
   pages you're still fetching. You don't know what you don't know until you're in it.

4. **The insight** — What you need isn't a script. You need a *pipeline* — a structure
   that separates fetching from parsing from loading, isolates failures at each stage,
   and lets you resume exactly where you stopped if anything goes wrong.

5. **What you'll build** — The Cairngorm Foundation scenario: 260 case study pages,
   hero images, body images, all loaded into Wagtail. Framed as: "by the end of this
   chapter, you'll have a pipeline that handles all of this — and if it stops halfway
   through, you can resume without re-fetching what already worked."

---

## Step 0: Planning (polish)

Keep the sitemap analysis script and manual page inspection list. Changes:
- Opening sentence: why you do this *before* writing any code
- **Tip callout:** "Five minutes with a sitemap saves hours of surprised parsing code"

---

## Steps 1–2: Destination Model + Resource Model (restructure)

**Step 1 — The destination model:**
Frame it as a model the developer already built earlier in the project. The tutorial
says "you already have a `CaseStudyPage`" and shows it as existing code. Add one
anchoring sentence: "This is the destination. Everything the pipeline does is in
service of populating these fields."

**Step 2 — The Resource model:**
Show the empty `AbstractResource` subclass first, explain what it is conceptually
("the pipeline's ledger — one row per piece of content, tracking exactly where it
is in the journey"), then say "by the end of this tutorial it'll look like this"
and show the full populated version. This avoids forward references to classes that
don't exist yet feeling like dangling threads.

Add a **Note callout** explaining the one-concrete-subclass rule.

---

## Step 3: Seeding (polish prose)

- Open with one sentence on why this stage exists
- Code stays as-is
- Brief prose note on what the filter is doing and why

---

## Step 4: Extracting (polish prose)

- Currently very thin ("it's built in, move on")
- Add a sentence on what `HTTPExtractor` actually does (retries, redirects, MIME
  type detection, stores as text or blob depending on content type)
- Keep it short — it genuinely is simple

---

## Step 5: Parsing (polish + callout)

- Keep the "write and test parsing logic against local HTML files before connecting
  it to the pipeline" approach — this is good Two Scoops-style advice
- **Tip callout:** "Test your parser against fixture files before wiring it into the
  pipeline. You want to know your selectors work before you've fetched 260 pages."
- Prose notes on the parser design decisions stay (None vs "", red-brown without
  text-lead, editor-scoped image URLs)

---

## Step 6: Mining (polish + callouts)

- Open with one sentence on why mining exists as a separate stage
- **Note callout on the `seen` set:** "We deduplicate here because the same image URL
  can appear as both the hero and a body image on some pages."
- **Warning callout on image URL variants:** CMS image URLs are often variants —
  cropped, resized, thumbnailed. If you mine these directly, you'll download a small
  thumbnail instead of the full image, and end up with many near-duplicate images in
  your Wagtail library. Normalize image URLs to their canonical form before emitting
  them as resources. If real variant URL patterns exist in the fixtures, show a
  concrete before/after example; otherwise, flag the pattern and advise the reader to
  inspect their own site's URL structure.

---

## Step 7: Transforming (polish + callout)

- Open with one sentence on what a Spec is and why it exists (decouple parsing from
  saving — the transformer doesn't touch the database)
- Keep the three explanatory points (content_type, BlobRef, __wagtail_parent_page)
- **Warning callout on BlobRef:** "BlobRef is lazy — it's resolved at load time, not
  now. The image doesn't need to exist yet when you return this Spec."

---

## Step 8: Running the Pipeline (expand)

- Explain *why* there are two loaders (PageLoader for Wagtail tree placement,
  ModelLoader for everything else)
- **Note callout on dependency resolution:** Isekai automatically determines the
  correct creation order so you don't have to think about "I need to create the image
  before the page that references it." For circular dependencies, isekai handles those
  too via partial construction. Link to `reference/dependency-resolution.md` (page to
  be written).
- Keep the numbered pipeline run sequence — it's good
- Add a sentence after: "If the pipeline stops partway through, run it again. Isekai
  skips resources that have already moved past a stage — no redundant fetches."
- Close with what you should see in the Wagtail admin

---

## Closing (rewrite)

Replace the bullet list with:

1. **Reflection paragraph** — You started with a deadline and a blank file. Now 260
   case studies are in Wagtail, images and all. The pipeline handled the ordering,
   the retries, the inconsistent HTML — you just described what each stage should do.

2. **"What we learned" callout** (Three Scoops style) — 3–4 bullet points of key
   lessons, written as wisdom:
   - Understand the shape of your data before writing any code
   - Separate fetching from parsing from loading — failures are easier to diagnose
   - Normalize image URLs at mine time, not transform time
   - If the pipeline stops, run it again — it picks up where it left off

3. **"What's next" section** — same content as current, but framed as "the same
   pattern scales to other content types" rather than a list of edge cases to handle.

---

## Callout Box Summary

| Location | Type | Subject |
|---|---|---|
| Step 0 | Tip | Five minutes with a sitemap |
| Step 2 | Note | One concrete subclass rule |
| Step 5 | Tip | Test parser against fixtures first |
| Step 6 | Note | Deduplication with `seen` set |
| Step 6 | Warning | Image URL variants / normalization |
| Step 7 | Warning | BlobRef is lazy |
| Step 8 | Note | Automatic dependency resolution |
| Closing | Callout | What we learned |

---

## Out of Scope

- No changes to `docs/concepts.md` or how-to guides
- `reference/dependency-resolution.md` is referenced but not written in this pass
  (link will be a placeholder)
- No changes to code in `isekai/` — this is docs only
