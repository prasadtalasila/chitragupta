# A figure-similarity review tier, and the benchmark that gates it (#659)

Status: **benchmark built and run; `bench/RESULTS.md` recommends a
narrowly-scoped ship** -- SigLIP, not CLIP, and described for exactly
what it measured: catching a redraw that keeps the source's own text
labels, not a redraw that also relabels its boxes. This file is the plan
for that tier, written before the outcome was known; its Tasks section
below is live, with two measurement gaps `bench/RESULTS.md` names as
open before implementation starts (Task 0). Written 2026-09-04, for
issue [#659](https://github.com/prasadtalasila/chitragupta/issues/659).

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to run the Tasks section task-by-task.
> Start at Task 0 -- it closes the two gaps `bench/RESULTS.md` left open
> before Task 1's file structure is worth building.

**Written for** whoever next touches `chitragupta/review/` figure
handling, or reopens this issue: someone who has read
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) and
[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md), but has not
necessarily read [docs/TIKZ-STYLE.md](../docs/TIKZ-STYLE.md)'s "Check
the drawn figure against this list" section or
[docs/PLAGIARISM-DESIGN.md](../docs/PLAGIARISM-DESIGN.md)'s methodology
for a prior "does a threshold separate signal from noise" measurement --
both are summarised below rather than assumed read.

## 🕳 The gap this closes, and why it has no mechanical support today

Three separately correct decisions compose into a hole: (1) no citekey
may appear inside a figure file, so a citekey in a node label would
evade `python -m chitragupta.draft gate`; (2) the renderer reaches a
figure only through `\input{figures/<n>.tex}`, which the gate does not
follow; (3) `chitragupta/review/figure_layout/` measures geometry, not
provenance. The result: "the TikZ must be as original as the ASCII" is
the one originality rule in this project with no mechanical check at
all, in the place -- reproducing a diagram everyone in the field already
knows -- where the pull to violate it is strongest. Full statement in
the issue; not restated here.

## 🧪 What was measured, and why in this order

`bench/bench_figure_similarity.py` (see its own docstring for the full
methodology) measures, against the real corpus's `content/docling/`
crops:

1. **Identity control** -- a real crop, decoded fresh, must be its own
   top match. Separates "the encoder is weak on this domain" from "the
   pipeline is broken", which the planted case alone cannot do.
2. **The cross-paper false-positive floor** -- every crop's cosine to
   its nearest neighbour from a *different paper*. "Different paper" is
   the ledger's `title`, not the citekey: 55 of 642 ledger items
   (2026-09-04) share a title with another citekey -- the same PDF
   attached twice -- and masking by citekey alone would count those
   pairs' identical figures as "genuine cross-paper similarity",
   pinning the floor's tail at cosine 1.0 for a reason with nothing to
   do with the field's drawing conventions. This was found empirically,
   from a first dev run at `--sample 200` producing exactly that
   symptom -- see `bench/bench_figure_similarity.py`'s
   `citekey_paper_groups()`.
3. **Recall on a graded planted case**, the same shape
   `bench_overlap_embed.py` already uses for text: four citekey-free
   TikZ fixtures under `bench/fixtures/figure_similarity/`, redrawing
   `karabey_aksakalli_deployment_2021`'s Fig. 1 -- `faithful_trace.tex`
   (same boxes/labels/edges, in the source's own rounded pale-yellow
   UML style), `traced_redraw.tex` (the same structural copy in a
   generic plain-rectangle style), `relabelled_redraw.tex` (same
   topology, generic labels), and `original_diagram.tex` (a legitimately
   original diagram in the same box-and-arrow genre -- the negative
   control). SigLIP ranks the two label-preserving fixtures **1st** and
   **5th** of 6,541 corpus crops; CLIP ranks the same two 133rd and
   182nd. Both encoders lose almost all of that signal once the labels
   are genericized (rank ~450, next to the negative control's ~500-1,100)
   -- the signal is substantially about preserved label text, not pure
   geometry. A first run of this fixture set was retracted by a
   TikZ-rendering bug that silently clipped wide figures at the page
   edge; see `bench/RESULTS.md` for the retraction and the corrected
   numbers above.
4. **Encoder choice and cost** -- a CLIP-class (`clip-ViT-B-32` via
   `sentence-transformers`) and a SigLIP-class encoder
   (`google/siglip-base-patch16-224`, vision tower only --
   `SiglipVisionModel`/`AutoImageProcessor`, since the fused
   `AutoProcessor` path needs `sentencepiece`, an undeclared dependency,
   purely to build a text tokenizer this measurement never uses), both
   confirmed to load under the `transformers>=4.57.6,<4.58.0` window
   `adapters` pins (pyproject.toml), timed end-to-end per crop.
5. **A perceptual-hash prescreen** -- plain 8x8 average-hash via PIL,
   not the `ImageHash` package (would start a lock fight inside a
   measurement PR for ~5 lines of arithmetic) -- scored the same way as
   the embedding floor, since #659 proposes it as a cheap first pass.

**Numbers, decision and raw records:** `bench/RESULTS.md`.
This plan does not restate them -- they are the input to the decision,
not a second copy that can drift from the measured one.

## 🧩 File structure

A new review-layer tier, deterministic and LLM-free -- same input, same
findings shape, safe unattended -- following #428's claim-support class
as precedent for "ranked, never banded, exit 0 whatever it finds".

| File | Responsibility |
| --- | --- |
| `chitragupta/review/figure_similarity/__init__.py` | Public entry point the review CLI calls; assembles the other modules' output into one findings payload |
| `chitragupta/review/figure_similarity/_rasterize.py` | Compile a draft's `figures/<n>.tex` and rasterise to PNG (the same TikZ-to-PDF compile `_probe.py` already does for geometry, extended to render rather than just measure -- **do not duplicate the compile**; factor the shared subprocess call out of `_probe.py` if it is not already isolated). **Must use a fixed oversized page** (`bench_figure_similarity.py`'s `_TEX_WRAP`, not bare `\documentclass{article}`) -- the bench script's own first run silently clipped wide figures at the page's MediaBox edge, which is a rasterisation bug this module would inherit verbatim if it copies the wrong version |
| `chitragupta/review/figure_similarity/_hash_screen.py` | The 8x8 average-hash prescreen, promoted from the bench script once its floor/recall numbers are in `bench/RESULTS.md`. Measured to saturate at 64/64 by the 90th percentile on this corpus -- keep it if a future corpus check finds it discriminates there, but do not rely on it as a hard screen without re-measuring |
| `chitragupta/review/figure_similarity/_embed_index.py` | Corpus-crop embedding index using **SigLIP** (`google/siglip-base-patch16-224`, vision tower only), not CLIP -- `bench/RESULTS.md` measured CLIP markedly weaker on the same fixtures (rank 133rd/182nd vs. SigLIP's 1st/5th). Built once and cached the way `content/chroma/` already is for tier 3 of the overlap scan -- reuse that cache's on-disk shape rather than inventing a second one |
| `chitragupta/review/figure_similarity/_report.py` | Findings assembly: per draft figure, top-N corpus crops with citekey, the paper's own figure number (from `cite`, per `chitragupta/draft_figures.py`'s existing resolution -- never a docling picture ordinal), and score |

**Reused, not reinvented:** `chitragupta.draft_figures.figures()`'s
`image_path` resolution; `chitragupta/review/figure_layout/_probe.py`'s
TikZ-compile-in-a-tempdir pattern; whatever on-disk cache shape
`chitragupta/overlap_embed.py`/tier 3 already uses for a Chroma
collection, so this is the second consumer of that shape rather than a
third bespoke one.

## Global Constraints

- No citekey is ever generated, guessed or rewritten (SOUL.md's one
  invariant) -- this tier only *reads* citekeys the ledger already
  carries, for crops already indexed by the enrichment layer.
- Ranked and scored, never banded; no threshold introduced anywhere
  (per PLAGIARISM-DESIGN.md's finding that none separated signal from
  noise for text, and this benchmark's finding for images).
- Exits 0 whatever it finds; unavailability (no crops, no TikZ figures
  in the draft) appears in `tiers_not_run`, distinct from "measured and
  clean" (#408's lesson).
- `adapters` pins `transformers>=4.57.6,<4.58.0`; the shipped encoder
  must load under that window without adding `sentencepiece` or any
  other new pinned dependency unless the benchmark specifically
  measured needing one.
- Line and branch coverage stays at 100% for anything under
  `chitragupta/` -- unlike `bench/`, this is inside CI's coverage
  target and the clean-code ratchet.

---

## Tasks

### Task 0: Close the two measurement gaps `bench/RESULTS.md` left open

`bench/RESULTS.md`'s ship recommendation is explicit that these two are
outstanding, not merely "nice to have":

1. **The cross-paper floor's true tail is not established.** The
   measured floor's p95-p99 (cosine ~1.0, both encoders) turned out on
   inspection to be dominated by the *same book counted twice* -- an
   edited collection and its own individual chapters, catalogued as
   separate ledger items with different titles, so
   `bench_figure_similarity.py`'s title-based `paper_group` mask cannot
   catch it. Before this tier's floor can be trusted for anything beyond
   "an upper bound on the noise", extend the bench script (or a
   successor) with a same-book/chapter detection -- e.g. a high
   *within-document* text-overlap check between two citekeys' parsed
   text, or a hand-maintained collection map -- and re-measure.
2. **Only box-and-arrow figures were tested.** This corpus is mostly
   photographic and plot-heavy figures. Run the same identity-control /
   floor / planted-case method against a planted photographic or
   plot-style redraw before claiming this tier's SigLIP result
   generalises past the one genre it was measured on.

**Files:** `bench/bench_figure_similarity.py`, `bench/RESULTS.md`
(record the re-measurement the same way as the 2026-09-04 entry, dated
and cross-referenced, not overwriting it -- see
`bench/RESULTS.md`'s own "Which sections are current" convention).

- [ ] **Step 1:** Design and implement the same-book/chapter detector;
      re-run the floor with it and record whether the tail narrows.
- [ ] **Step 2:** Add a photographic or plot-style planted fixture (a
      real corpus figure of that kind, redrawn or re-plotted) and record
      SigLIP's rank on it.
- [ ] **Step 3:** If either re-measurement changes the ship/close
      call, update `bench/RESULTS.md`'s "Which sections are current"
      table to mark the 2026-09-04 entry superseded and say why, and
      revisit Tasks 1-5 below before writing any of their code.
- [ ] **Step 4:** Commit.

### Task 1: Promote the encoder and the hash screen out of `bench/`

**Files:**

- Create: `chitragupta/review/figure_similarity/__init__.py`,
  `chitragupta/review/figure_similarity/_hash_screen.py`,
  `chitragupta/review/figure_similarity/_embed_index.py`
- Test: `tests/test_figure_similarity_hash_screen.py`,
  `tests/test_figure_similarity_embed_index.py`
- Reference: `bench/bench_figure_similarity.py`'s `average_hash()`,
  `hamming_matrix_chunked()`, `load_clip()`/`load_siglip()` -- copy the
  winning encoder's loader only, not both

**Interfaces:**

- Produces: `_hash_screen.average_hash(image: PIL.Image) -> np.ndarray`
  (flat bool array), `_hash_screen.hamming(a, b) -> int`
- Produces: `_embed_index.embed_images(images: list[PIL.Image]) -> np.ndarray`,
  `_embed_index.load_or_build_cache(cache_path: Path, crops: list[dict]) -> np.ndarray`

- [ ] **Step 1: Write the failing test** for `average_hash`/`hamming` --
      an identical pair must hash to Hamming distance 0, a black image
      and a white image must hash to a large distance.
- [ ] **Step 2: Run it, confirm it fails** (`ModuleNotFoundError`).
- [ ] **Step 3: Copy the two functions from `bench/bench_figure_similarity.py`
      into `_hash_screen.py`** unchanged.
- [ ] **Step 4: Run the test, confirm it passes.**
- [ ] **Step 5: Write the failing test for `_embed_index`** -- a cache
      miss builds and writes embeddings; a cache hit with an unchanged
      crop list returns the cached array without re-embedding (mock the
      encoder loader and assert it is called 0 times on the hit path).
- [ ] **Step 6: Implement `_embed_index.py`** using the bench script's
      winning `load_clip`/`load_siglip` function, plus a cache keyed by
      crop path + mtime, following whatever shape
      `chitragupta/overlap_embed.py` already uses for its Chroma cache.
- [ ] **Step 7: Run the tests, confirm they pass.**
- [ ] **Step 8: Commit.**

### Task 2: Rasterize a draft figure

**Files:**

- Create: `chitragupta/review/figure_similarity/_rasterize.py`
- Modify: `chitragupta/review/figure_layout/_probe.py` only if the
  compile-in-a-tempdir subprocess call needs factoring out to avoid
  duplication -- read it first; do not duplicate it speculatively
- Test: `tests/test_figure_similarity_rasterize.py`

**Interfaces:**

- Consumes: nothing from Task 1
- Produces: `_rasterize.rasterize(tex_path: Path) -> PIL.Image`, raising
  `figure_layout._probe.FigureCompileError` on a figure that does not
  compile (same exception type, so a caller already catching it for the
  layout aid catches this too)

- [ ] **Step 1: Write the failing test** -- a fixture `.tex` with a
      single labelled node rasterises to a non-empty image; a fixture
      with a deliberate TeX error raises `FigureCompileError`.
- [ ] **Step 2: Run it, confirm it fails.**
- [ ] **Step 3: Implement `_rasterize.py`**, adapting
      `bench_figure_similarity.py`'s `rasterize_tikz()` (compile via
      `pdflatex` in a `TemporaryDirectory`, render page 1 with
      `pypdfium2`, autocrop to non-white content, close the `PdfDocument`
      and `PdfPage` explicitly).
- [ ] **Step 4: Run the test, confirm it passes.**
- [ ] **Step 5: Commit.**

### Task 3: Findings assembly and the `tiers_not_run` contract

**Files:**

- Create: `chitragupta/review/figure_similarity/_report.py`,
  `chitragupta/review/figure_similarity/__init__.py`
- Modify: wherever the review CLI assembles `tiers_not_run` today (find
  via `grep -rn tiers_not_run chitragupta/`) to add this tier's key
- Test: `tests/test_figure_similarity_report.py`

**Interfaces:**

- Consumes: `_rasterize.rasterize`, `_embed_index.embed_images`/
  `load_or_build_cache`, `_hash_screen.average_hash`
- Produces: `__init__.check(draft_dir: Path) -> dict` with keys
  `{"findings": [...], "measured": bool, "reason": str | None}`; each
  finding is `{"draft_figure": str, "top": [<candidate>, ...]}`, where
  a `<candidate>` is `{"citekey": str, "figure": str, "score": float}`
  and `"figure"` is the `cite`-derived paper-own figure reference, not
  a docling ordinal

- [ ] **Step 1: Write the failing test** for the three `tiers_not_run`
      cases: no corpus crops at all, a draft with no TikZ figures, and a
      draft figure that fails to compile (must appear as a distinct
      per-figure note, not fold into "measured nothing").
- [ ] **Step 2: Run it, confirm it fails.**
- [ ] **Step 3: Write the failing test for the happy path** -- a draft
      figure closely matching a fixture corpus crop produces a finding
      whose top entry names that crop's citekey and figure reference.
- [ ] **Step 4: Implement `_report.py`** wiring Tasks 1-2 together.
- [ ] **Step 5: Run both tests, confirm they pass.**
- [ ] **Step 6: Wire into the review CLI's `tiers_not_run` list.**
- [ ] **Step 7: Commit.**

### Task 4: Documentation

**Files:**

- Modify: `docs/PLAGIARISM.md` (user-facing: what this tier reports and
  how to read it -- ranked, not banded, per its own convention for the
  other tiers)
- Modify: `docs/TIKZ-STYLE.md`'s "Literal copying" bullet -- state what
  is now mechanically supported (traced/relabelled redraws of an
  indexed corpus figure) and what is not (photographic/plot-heavy
  figures were not part of this benchmark's planted case; chaotic
  routing and colour-only distinctions remain human judgement, unchanged)

- [ ] **Step 1: Edit `docs/PLAGIARISM.md`**, following the existing
      tiers' section shape.
- [ ] **Step 2: Edit `docs/TIKZ-STYLE.md`**'s "Literal copying" bullet.
- [ ] **Step 3: Run `mkdocs build --strict`** to confirm no broken
      cross-references.
- [ ] **Step 4: Commit.**

### Task 5: Coverage and bench count bookkeeping

**Files:**

- Modify: whatever pyproject.toml coverage-source list and
  `bench/README.md`'s self-check count sentence this repo's tests pin
  (`tests/test_technical_debt_scan.py::test_the_bench_self_check_count_matches_the_tree`)
- Test: run the full suite with coverage; fix any uncovered line before
  declaring the task done, since C1/C2 and 100% coverage bind
  `chitragupta/` even though `bench/` sits outside both

- [ ] **Step 1: Run the full suite with `--cov`** from the correct venv
      (`.venv-full`, not `.venv-313` -- see this project's own note on
      the difference) and confirm 100%.
- [ ] **Step 2: Fix any gap.**
- [ ] **Step 3: Bump the version** (every PR must, docs-only included).
- [ ] **Step 4: Commit and open the PR.**
