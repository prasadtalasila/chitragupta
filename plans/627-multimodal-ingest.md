# Multimodal ingest: tables and formulae as retrievable units (#627)

Status: **in progress.** Written 2026-09-03.

**Written for** the implementer of issue #627 (roadmap key H11): an
author grounding a quantitative claim in a table should be able to
retrieve the table itself, with its page anchor -- not only its caption.

**Assumed**: the Docling sidecar machinery as it stands after #600/#602
-- `chitragupta/passages.py:passage_records()` is the one shared
definition of a passage, written by both parsers (the corpus layer's
`pdf_text/_backends._extract_docling` and the enrichment layer's
`docling_parse.parse_doc`), and read back through
`passages.source_passages()` by every review aid that anchors a claim.

**Not covered here**: vision-model captioning of figures (measured and
rejected -- it would put generated text in the corpus layer, which may
not call an LLM); any change to how figures are handled (#600/#602 own
that); OCR of scanned tables.

## What is actually missing, measured on the real corpus

Three routes were read before writing this, because the issue's phrase
"indexed by the lexical route (cell text)" turns out to be already true:

- **Lexical**: `chitragupta/retrieval.py` indexes `content/parsed/*.txt`
  (pdftotext), where table cell text is present in visual layout.
- **Dense**: `embed_index` chunks `get_text()`, which prefers the
  Docling `.md` -- and Docling's markdown export serialises tables as
  pipe tables, cell text included.
- **Units**: `passage_records()` keeps only
  `{text, list_item, section_header, title}` items, so **a table is not
  a passage** -- no page anchor, nothing for `review provenance` /
  `claim_support` / `quotation` to point at. And formulae are worse:
  Docling writes `<!-- formula-not-decoded -->` into the `.md` unless
  its formula-enrichment model runs, so a formula's content is dropped
  from every route.

So the deliverable is the unit layer, plus the opt-in that gives
formulae any content to carry.

## The change

1. **Tables become passage records.** `passage_records()` gains a second
   loop over `getattr(dl_doc, "tables", [])` (duck-typed, like
   everything else in that module -- it must import under bare
   `python`): text is the item's own `export_to_markdown(dl_doc)` with
   the caption (via `caption_text(dl_doc)`, when the document carries
   one) prepended, label `"table"`, page and bbox from `prov[0]` exactly
   as for text items. A table whose export is empty contributes nothing.
   Structure survives as markdown rather than a flattened word bag, so
   the record is both matchable (its `distinctive()` words are the cell
   text) and readable when a review aid shows it.
2. **Formulae pass through when they have content.** `"formula"` joins
   `PASSAGE_LABELS`: a decoded formula is exactly the kind of content a
   claim rests on (Li et al.'s finding, per the issue). An undecoded one
   has no text and is already skipped by the existing empty-text guard
   -- no new special case.
3. **`[enrich] docling_formulas`** (bool, default `false`, env
   `DOCLING_FORMULAS`): sets Docling's `do_formula_enrichment` in the
   enrichment layer's `_build_converter()`, mirroring `docling_images`'
   declaration shape. Off by default because it downloads and runs an
   additional model per page; it joins the Docling cache key like the
   other runtime toggles, since flipping it changes what every `.md`
   and sidecar should contain.
4. **Cache version bump.** `_docling_cache._CACHE_VERSION` 2 -> 3:
   a sidecar written before this change carries no table records even
   though its PDF is unchanged, which is precisely what that constant
   exists to catch. The corpus layer's own sidecar (rung 2) has no such
   version; it backfills on the next `sync --reparse`, and the docs say
   so rather than pretending otherwise.

## What deliberately does not change

- `source_passages()` and every consumer: `_from_sidecar()` already
  passes any label through, `Passage.quotable` already answers from
  `text`, and the review aids score words without caring what kind of
  item produced them. That inheritance is the point of the shared seam.
- `chitragupta/retrieval.py` and `embed_index`: both routes already see
  cell text (above); no new index, no new artefact.
- The corpus layer still calls no LLM: Docling's table and formula
  models are local layout/recognition models, the same class of thing
  as its OCR.

## Risks named up front

- `export_to_markdown` is a real library call that can fail on a
  malformed table; both parsers already classify a per-document raise
  honestly (per-doc `error` in the enrichment stage, a failed parse in
  the corpus layer), so it is allowed to propagate rather than being
  swallowed.
- The verbatim/overlap aids will now see table text on both sides; a
  draft that reproduces a table row verbatim becomes visible to them,
  which is a feature, not a regression.
