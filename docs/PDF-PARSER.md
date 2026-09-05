# 📄 PDF parser tradeoffs for chitragupta

Status: **reasoning document.** Written 2026-08-02. Updated 2026-08-24.

**Written for** someone choosing `[parser].backend`, or revisiting that
choice. **Assumed:** [CONFIG.md](CONFIG.md) for how to set it. **Not
covered here:** the measured cost of each backend, which is
[PERFORMANCE.md](PERFORMANCE.md).

## 🔭 Short summary

This repository needs PDF processing that balances speed, text quality,
structure preservation, and portability.

The main candidates are:

- `pdftotext`
- `markitdown` -- **removed 2026-08-01**, see ["Why markitdown was removed"](#-why-markitdown-was-removed)
- `docling`

`grobid` was evaluated as a fourth candidate and **removed from the repo on
2026-08-01**. It is kept in the comparison below as a record of that decision,
not as an available backend -- see ["Why GROBID was
removed"](#-why-grobid-was-removed). A separate proposal to bring it back in a
*different* role -- alongside docling rather than instead of it, for a citation
graph -- is in [GROBID-CITATION-GRAPH.md](GROBID-CITATION-GRAPH.md).

Four newer parsers (**marker**, **surya**, **xberg**, **unstructured**) were
surveyed in 2026-08 and none adopted; the analysis is in ["Four newer backends,
evaluated and not adopted"](#-four-newer-backends-evaluated-and-not-adopted).

## ⚖ Comparison table

| Tool | Best at | Strengths | Weaknesses | Relative speed vs `pdftotext` | Fit for this repo |
| --- | --- | --- | --- | --- | --- |
| `pdftotext` | Plain text extraction | Very fast, simple, stable, low dependency footprint | Weak on layout, tables, headings, and reading order | 1x | Best lightweight baseline |
| `markitdown` | General file-to-Markdown conversion | Flexible normalization, multi-format support | Fuses adjacent words on this corpus (4.17% of tokens), which silently breaks BM25 ranking | ~17x slower (measured, 5 real bib PDFs) | **Removed 2026-08-01** -- see below |
| `docling` | Layout-aware PDF parsing | Better reading order, sections, tables, and structured Markdown -- and the only backend whose reading order is *kept*, as the passage sidecar a claim can be quoted from | Heavy, slower, model/runtime complexity | ~42x slower (measured, 5 real bib PDFs, OCR on -- see note below) | Best quality parser for either layer; required if you want quotable passages |
| `grobid` | Scholarly structure and references | Excellent for title, abstract, sections, and references | Not a general-purpose plain-text extractor; needs a JDK 21 build and a long-running service | Separate from the main speed scale | **Removed 2026-08-01** -- see below |

## 🔬 Likely behavior in practice

### ⌨ `pdftotext`

This is the fastest option and the easiest to operate. It is well suited to the
repo's lightweight corpus layer when the goal is to get searchable text into the
ledger and retrieval index.

### 📝 `markitdown`

A general conversion tool rather than a scholarly parser, and meaningfully
slower than `pdftotext` (~17x measured). Measurement on this repo's own corpus
later showed it loses word boundaries here, which is why it is no longer a
backend -- see below.

### 🧱 `docling`

This is the best fit when the PDF's structure matters: headings, tables, reading
order, and section boundaries. It is much slower and heavier (~42x measured),
but the output is more useful for later chunking, retrieval, and topic modeling.

**The ~42x figure predates the OCR default.** It was measured with
Docling's OCR stage on, which is Docling's default but has not been this
project's (`config.toml`'s `[parser].ocr = false`). Measured
over the whole corpus rather than a sample, turning OCR off is **2.08x**
faster serially and up to **4.79x** at 24 workers, so the current default
sits well below 42x. Treat 42x as the OCR-on ceiling from a 5-PDF sample,
and [PERFORMANCE.md](PERFORMANCE.md) as the figure to plan against: a
full 501-PDF serial parse takes 55m 30s with OCR off against 1h 56m with
it on. (An older **2.46x**, from a 16-PDF serial sample, is still quoted
in some places; it estimated the serial case only.)

**Its output is not reproducible under concurrency.** With a worker pool,
dense reference blocks are grouped into elements slightly differently
between runs: ~1.4% of documents come back with different text and ~1.0%
with a different *quotable passage*, and two runs of the same
configuration are not exempt. Ranking is unaffected -- `chitragupta/retrieval.py`
tokenises on runs of `[a-z0-9]`, so where an element boundary falls
between two words changes nothing about the terms extracted -- but the
exact span quoted from a source can change, which is the part that
matters for a citation-grounded pipeline. This is
Docling's own behaviour under load, not something this repo's parallelism
introduced, and it cannot be switched off: Docling exposes no determinism
setting. `pdftotext` does not have this property; its output is
byte-identical across runs.

The artifact-by-artifact contract is in
[ARCHITECTURE.md](ARCHITECTURE.md#-what-is-reproducible-and-what-is-not),
with the measurement in `bench/RESULTS.md` (developer-only, in the
repository).

Turning OCR off is a trade-off, not a free win: it drops text that the
PDF stores as a bitmap rather than as characters, which on this sample
was mostly publisher furniture and figure sub-captions but on one
document included two whole tables. See
[PERFORMANCE.md](PERFORMANCE.md#-parserocr----the-largest-single-lever-and-a-trade).

It also carries a system dependency nothing else in this repository has,
and one that announces itself in a thoroughly misleading way -- see
["docling fails every document with an OpenCV recursion error"](#-docling-fails-every-document-with-an-opencv-recursion-error).

### 📖 `grobid`

GROBID is most valuable for reference extraction and scholarly structure. It was
never a drop-in replacement for the other tools, and is no longer part of this
repo -- see below.

## 📌 Recommended use in this repository

A practical tiered strategy:

1. **`pdftotext`** for the fast baseline path
2. **`docling`** for high-quality structured parsing

That tiering matches the repository's design philosophy:

- probe first
- degrade gracefully
- keep the corpus layer usable even when the enrich group is absent

## ⚖ Quality tradeoff for this repo

### ⚡ If speed is the priority

Use `pdftotext`.

### 🏗 If PDF structure is the priority

Use `docling`.

### 📖 If references and scholarly metadata are the priority

`papers/bibliography.bib` already supplies these -- it is the source of truth
for title, authors, year, and DOI (see [CONFIG.md](CONFIG.md)). No parser needs
to re-derive them.

## 🖥 Notes on cross-platform support

- `pdftotext` depends on an external system package, so it is not the most
  portable option.
- `docling` is the heaviest option and may be the hardest to support
  consistently across operating systems.

If cross-platform support is important, the best approach is to treat these as
**optional backends** and keep a fallback ladder rather than relying on a single
tool.

## 🏗 Suggested architecture

A robust design for this repo would be:

- corpus layer: `pdftotext`
- enrichment (structured) path: `docling`

That gives a good balance of:

- speed
- fidelity
- portability
- downstream retrieval quality

## 🏁 Conclusion

For this repository:

- `pdftotext` is the fastest and simplest
- `docling` is the best structured PDF parser

The best overall outcome is not choosing one tool, but combining them in a
layered backend strategy.

## 🧪 Four newer backends, evaluated and not adopted

Surveyed 2026-08-05 (originally in
[issue #22](https://github.com/prasadtalasila/chitragupta/issues/22)) from
each project's own documentation rather than from a trial run: **marker**,
**surya**, **xberg** and **unstructured**, all against docling as the
incumbent. Nothing was adopted. This is recorded so the next person asking
"should we switch parsers?" starts from the analysis rather than repeating
it -- and so the one finding that would break a naive swap is written down.

### 🏷 What "fit" means here

The bar is not "does it parse a PDF". This repository depends on specific
docling behaviours, and a replacement has to supply all of them:

| What the repo uses | Where |
| --- | --- |
| Per-item `label`, `text`, `prov[0].page_no`, `prov[0].bbox` | passage provenance, `chitragupta/passages.py` |
| `pic.caption_text(dl_doc)` -- figure caption matched to "Figure N" in prose | `_figure_records`, see `DEVELOPER.md`'s "Figures and copyright" (git checkout only) |
| `export_to_markdown()` | `content/docling/<citekey>.md`, the artefact downstream stages read |
| `AcceleratorOptions(device="cuda:N", num_threads=...)` set **per worker process** | `init_worker`, one GPU claimed round-robin |
| A togglable OCR flag, default off | `[parser].ocr` |
| A togglable formula-recognition flag, default off -- without one, an equation reaches `content/parsed/` as a `formula-not-decoded` marker rather than as LaTeX | `[parser].formulas` |

### ⚖ Comparison

| | **docling** (incumbent) | **marker** | **surya** | **xberg** | **unstructured** |
| --- | --- | --- | --- | --- | --- |
| Category | End-to-end layout-aware PDF→doc | End-to-end PDF→Markdown/JSON, built on surya | Layout/OCR/table **primitives** (marker's foundation) | Polyglot doc-intelligence engine, Rust core | ETL "elements" extractor, multi-strategy |
| Native Markdown export | Yes | Yes | **No** -- assembly required | Yes (+ Djot/HTML/JSON) | **No** -- typed `Element` list only |
| Provenance (page + bbox + label) | Yes, per item | Yes, JSON block tree | Yes, but page/doc assembly is on you | Yes, "Structured" JSON | Yes, per element |
| Figure↔caption auto-linking | **Yes** | Undocumented | Not provided | Unverified | Undocumented |
| Table extraction | Structured, built in | Structured (HTML), CPU heuristic + VLM fallback | Structured (HTML/cells) | Structured (TATR/SLANet) | Structured (TATR) |
| GPU model | Optional, **in-process** | External inference server (vLLM/Docker) -- **OCR paths only** | Same server requirement | Optional, CPU-first (ONNX) | CPU-historically; GPU auto-detect unverified |
| OCR off-switch | Yes | Yes (`--disable_ocr`) | **No** -- inherent to the VLM | Yes, swappable backends | Yes, via `strategy` |
| Fits the per-process CUDA-device pool | Yes (built for it) | OCR off: yes. OCR on: **no** | **No** | Yes-ish -- no persistent CUDA context | Roughly, in-process ONNX |
| Code license | MIT | Apache-2.0 | Apache-2.0 | MIT | Apache-2.0 |
| Model-weight license | Open weights | **Modified OpenRAIL-M** -- free under $5M revenue, else paid | Same OpenRAIL-M variant | N/A | N/A |
| System deps beyond pip | None with OCR off | vLLM + Docker + NVIDIA toolkit, or llama.cpp -- **only if OCR is used** | Same as marker | None (bundles ONNX) | libmagic, poppler, tesseract, libreoffice, pandoc |
| Maturity | Established, IBM-backed | Established; v2.0 rewrite Jul 2026 | Established; v2 rewrite May 2026 | v1.0 days old at survey time | Established |

### ⚠ The finding that would break a naive swap

**marker and surya moved OCR and layout to a locally-spawned inference
server** (vLLM on GPU, llama.cpp on CPU) in their 2026 rewrites. Workers
become HTTP clients of one shared server rather than each holding its own
CUDA context -- so this repository's `ProcessPoolExecutor` +
`init_worker` GPU round-robin does not carry over. That is an
architecture change, not a backend substitution. See
[PARALLELISM.md](PARALLELISM.md#-components).

**But it is an OCR-only cost.** Under `--disable_ocr` marker starts no
server at all: layout comes from an in-process `rf-detr` detector, text
from `pdftext`, tables from CPU heuristics. Since this project already
runs with OCR off by default, that is the configuration that matters --
and in it, marker collapses to something close in shape to docling's own
architecture.

### 📊 Where each one lands

1. **surya -- do not target directly.** It is the primitive marker is
   built on. Using it means rebuilding page assembly, Markdown emission,
   image cropping and caption pairing -- work marker has already done.
2. **marker -- the strongest candidate, and only with OCR off.** Still
   needs a JSON→passage/figures mapping layer (mechanical, bounded), and
   **custom figure↔caption linking**, which is undocumented. Note the
   OpenRAIL-M weight licence applies even with the VLM disabled.
3. **xberg -- best licence and CPU story, too new to trust.** Plain MIT
   with no weight carve-out, CPU-first, and it sidesteps the
   fork-versus-CUDA-context problem entirely by having no persistent CUDA
   context. But the v1.0 line was days old, and figure/caption pairing
   could not be confirmed. This repository has a documented habit
   (markitdown, GROBID) of adopting on the strength of documentation and
   removing after measurement; xberg would need a measured pilot first.
4. **unstructured -- most work, least gain.** No native Markdown export
   (this repo would own a permanent `Element`→Markdown renderer),
   undocumented caption linking, the heaviest system-dependency
   footprint, and the least certain GPU story.

### 🏁 Conclusion of the alternatives review

**Stay on docling.** Its weaknesses -- speed, and non-determinism under
concurrency -- are known, measured and written down
([ARCHITECTURE.md](ARCHITECTURE.md#-what-is-reproducible-and-what-is-not)),
which is worth more than an unmeasured alternative's undocumented ones.
The shared blocker across marker, xberg and unstructured is the same:
**figure↔caption auto-linking is undocumented in all three**, and
`_figure_records` depends on it.

If this is revisited, marker with OCR off is the one to pilot, and the
pilot must measure against the real 501-PDF corpus -- the same discipline
that removed markitdown and GROBID.

## 🗑 Why GROBID was removed

GROBID's role here was bibliographic-quality header and reference
extraction, and it only ever called one endpoint
(`/api/processHeaderDocument`) for title/authors/abstract. That is
metadata `papers/bibliography.bib` already provides for every document
the project cares about: the goal is to parse the PDFs the bib file
names, and those arrive with real metadata already attached via
`chitragupta/bib_reader.py`.

What GROBID uniquely offered -- parsing a paper's own reference list into
structured author/title/year/DOI records, via the
`/api/processFulltextDocument` endpoint this repo never called -- serves
*corpus discovery* ("which papers do my papers cite that I don't have
yet"), not grounding. Extracted references are not in the bib file, so
per AGENTS.md's citekey invariant no draft may cite them -- and since
`chitragupta/enrich/corpus.py` sources the enrichment corpus from the ledger and
nothing else, there is nowhere to index them either. A discovered paper
enters this project the way every other one does: catalogue it in your
reference manager, re-export, and re-run `python -m chitragupta.corpus sync`.

Against that, the operational cost was a JDK 21 pinned exactly (its
bundled Kotlin compiler cannot parse a JDK 25 version string), a
multi-GB multi-minute Gradle build, and a long-running service on port
8070. Not worth it for a capability the project doesn't use.

If corpus-growth-by-snowballing later becomes a real workflow, the case
to revisit is for `/api/processFulltextDocument` specifically -- not the
header endpoint that was here.

## 🗑 Why markitdown was removed

Removed 2026-08-01, after measurement on this repository's own corpus
rather than on its stated feature set.

**The symptom.** Over the same 10 CPS papers, `markitdown` produced
**3,647 alphabetic tokens longer than 20 characters (4.17% of all
tokens)** against `pdftotext`'s **9 (0.01%)** -- a factor of 400 -- and
23% fewer total words, because words were being *fused* rather than
dropped. It is visible directly in retrieval snippets:

```text
isaninputtooranoutputfromafunction
AnnualReviewsinControl51(2021)357-373
theapplicationofthevery same principles
```

**Why that matters.** `chitragupta/retrieval.py` is BM25 over tokens split on
runs of `[a-z0-9]`, so a fused run is one token: a query for "cyber
physical" cannot match text fused into `cyberphysicalsystems`. A silent
ranking failure, not a cosmetic one.

**The cause.** `markitdown` extracts PDFs via `pdfplumber`, calling
`page.extract_text()` with no arguments. pdfplumber's default
`x_tolerance` is 3 points: glyphs closer than that are treated as one
word. These papers set inter-word spacing below 3pt. Measured on four
of them, dropping to `x_tolerance=1` eliminated every over-long token
(179 -> 0, 83 -> 0, 164 -> 0, 141 -> 0) and roughly doubled the word
count. `pdftotext` reads the same files correctly, so the spacing
information is present in the PDFs -- this is the extractor's threshold,
not damaged input.

**Why it wasn't fixable here.** `markitdown`'s PDF converter hardcodes
both `page.extract_text()` and `extract_words(x_tolerance=3,
y_tolerance=3)`. Its `convert()` accepts `**kwargs` but never forwards
them, so the tolerance is unreachable through its public API. Its own
source comments that the heuristic is "not for multi-column text layouts
in scientific documents" -- which is this entire corpus.

**What replaced it.** Nothing: `markitdown` sat in the middle of a
three-way ladder while being worse than `pdftotext` on text and worse
than `docling` on structure, so the ladder is now two rungs. Using
`pdfplumber` directly with a tuned tolerance was considered and
deferred -- it would no longer be "markitdown", and no current use case
needs a tier between the two remaining backends.

**What was added instead.** A parse-quality guard
(`chitragupta/pdf_text.quality_warning`, wired into `sync`) that warns when more
than 1% of a document's words exceed 20 characters. The two backends sit
three orders of magnitude apart on that measure, so the threshold does
not need precise tuning. Had it existed earlier, this would have been
reported by `sync` on the first run instead of being noticed by eye in a
retrieval snippet.

## 🐛 docling fails every document with an OpenCV recursion error

Diagnosed 2026-08-09. Fixed in the `os-deps` stage; recorded here because
the error message points at nothing useful, and because a host provisioned
some other way will hit it again.

**The symptom.** With `[parser].backend = "docling"`, `python -m
chitragupta.corpus sync`
prints a bare `sys.path` listing before the bibliography progress and then
fails every document it had to parse:

```text
['/workspace', '/usr/lib/python313.zip', ..., '/workspace/.venv-full/lib/python3.13/site-packages']
[497/497] noauthor_logical_nodate
FAILED  shao_use_2021: ERROR: recursion is detected during loading of "cv2" binary extensions. Check OpenCV installation.
```

There is no recursion, and OpenCV is installed correctly. Both halves of
that message are wrong.

**The mask.** `cv2/__init__.py` sets `sys.OpenCV_LOADER = True` at the top
of its bootstrap and deletes it at the bottom. If the *first* `import cv2`
in a process dies partway, the flag leaks -- and every later `import cv2`
in that process, or in any process forked from it, reports the recursion
error instead of the real reason. The stray `sys.path` line is cv2's own
`print(sys.path)` on that path. Reproduce the mask directly:

```console
$ python -c "import sys; sys.OpenCV_LOADER = True; import cv2"
ImportError: ERROR: recursion is detected during loading of "cv2" binary extensions.
```

**Why sync turns that into a whole-run failure.** `chitragupta/pdf_text/_startup.py`'s
`prestart_pool()` starts a forkserver whose preload imports `docling` while
the parent reads the bibliography -- which is why the print lands *before*
the progress lines. `forkserver.main()` catches `ImportError` and discards
it, so the genuine failure is swallowed and the poisoned flag survives in
the server process. Every worker forked from it then re-imports cv2 and
reports the mask. `chitragupta/pdf_text.preload_modules`' docstring already named
this as a known gap; this is that gap costing a run's diagnosability.

**The real cause.** OpenCV is a transitive dependency nothing here asks
for: the enrich group's `docling` pulls `docling-slim[standard]`, which
pulls `rapidocr`, which requires the `opencv-python` distribution *by
name*. That is the GUI-linked wheel. Its `cv2.abi3.so` vendors Qt but not
`libGL.so.1`, `libglib-2.0.so.0`, or the X libraries -- `ldd` resolves
those to the system, and a base image installed with
`--no-install-recommends` has none of them. So the first import raises,
and installing exactly those libraries is what fixes it.

The precise first-error string is inferred rather than captured: the mask
is what reaches the log, and by the time this was diagnosed the host had
been repaired. On a missing `libGL.so.1` the loader's message is
`ImportError: libGL.so.1: cannot open shared object file`. What is
confirmed is the mask mechanism (reproduced below) and the remedy.

**The fix.** `libgl1` and GLib are in the `os-deps` package list, so
`bash scripts/install_full_pipeline.sh os-deps` covers it. By hand:

```console
sudo apt-get install -y libgl1 libglib2.0-0t64   # libglib2.0-0 before Ubuntu 24.04 / Debian 13
```

**To see the real error rather than the mask,** run the parse serially --
the import then happens in-process, with no preload to swallow it and no
second attempt to trigger the flag:

```console
PARSER_WORKERS=1 python -m chitragupta.corpus sync
```

**Why `opencv-python-headless` is not the fix.** It is the right wheel for
a container, but `rapidocr` requires `opencv-python` by distribution name
and arrives through `docling-slim[standard]`, which is not droppable. A
constraint would install both distributions; they own the same `cv2/`
directory and clobber each other. Swapping to headless would have to be
post-install surgery -- uninstall one, install the other, after the enrich
group -- in the style of `ensure_gpu_torch`, and was not worth it against
two apt packages.

## 🐛 docling silently empties every formula on a GPU host

Diagnosed 2026-09-05. Fixed in the `os-deps` stage, like the OpenCV entry
above -- but recorded at more length, because this one does not fail the
run, does not fail the document, and produces output that is
byte-for-byte what you would get from the setting you did not choose. It
only happens with `[parser].formulas` (or `[enrich].docling_formulas`)
turned on, which is not the default.

**What it looks like.** A `sync` that keeps going, with one line per
affected document buried in a log that is already full of docling's own
table-recovery warnings:

```text
[vaillant_towards_2022] Error processing code/formula batch: Command '['/usr/bin/gcc',
  '.../triton/backends/nvidia/driver.c', ...]' returned non-zero exit status 1.
[5/497] vaillant_towards_2022
```

and, further up, the compile that actually failed:

```text
.../triton/backends/nvidia/driver.c:9:10: fatal error: Python.h: No such file or directory
```

**The cause.** torch's default Linux wheel bundles triton. With a GPU
visible, triton compiles a small C shim (`backends/nvidia/driver.c`) the
first time a CUDA kernel is launched -- a real `gcc` invocation, at
runtime, that `#include`s `Python.h`. A host with no CPython development
headers fails it. Nothing in this project asks for triton, and nothing
asks gcc to run; both arrive with torch and fire only under `--gpus`,
which is why a CPU-only host never sees this.

**Why it does not look like a failure.** docling catches the exception per
batch (`docling/models/stages/code_formula/code_formula_vlm_model.py`),
logs the line above, and assigns `""` to every element in the batch. The
document then converts successfully and the ledger records it as parsed.

What reaches the corpus text is the `formulas = false` behaviour, exactly.
`docling_core`'s Markdown serializer -- which both parses go through,
`pdf_text/_backends.py`'s `export_to_markdown()` and
`enrich/docling_parse.py`'s alike -- writes
`<!-- formula-not-decoded -->` for a `FormulaItem` whose `text` is empty
but whose `orig` is not, and the failure clears only `text`. So the
marker stays. You are not left wondering whether a formula was there;
you are left with a run that reported success, paid for the model
download and the extra pass per page, and produced the output you would
have got for free with the key switched off.

**How to tell, if you no longer have the log.** The two states are cleanly
separable, because a successful recognition writes LaTeX between `$$`
delimiters and leaves no marker at all:

```console
grep -l 'formula-not-decoded' content/parsed/*.txt | wc -l   # 0 when healthy
grep -l '\$\$' content/parsed/*.txt | wc -l                  # 0 is the tell
```

Measured on this project's own 497-document corpus, both states:

| `[parser].formulas` | Docs with a marker | Docs with `$$` LaTeX |
| --- | --- | --- |
| `false` | 148 | 0 |
| `true`, model ran | 0 | 151 |
| `true`, this failure | as `false` | 0 |

So one marker *while the key is on* is the whole diagnosis: the two
never coexist, and a healthy `true` run produces none. The `false` row is
the measurement
[CONFIG.md](CONFIG.md#-formulas-and-why-it-is-not-the-enrich-key) records;
the `true` row was measured on the same corpus after this key was turned
on.

**Re-running does not repair it, and the two settings recover
differently.** Both caches key on the *input* PDF, which has not changed,
so fixing the host and re-running leaves every already-parsed document
exactly as it was. Which lever clears it depends on which parse produced
the damage:

```console
sudo apt-get install -y python3-dev gcc     # or re-run the os-deps stage

# [parser].formulas -- the corpus parse. Skips on
# ledger.upsert_reference's (size, mtime) of the PDF; --reparse overrides it.
python -m chitragupta.corpus sync --reparse

# [enrich].docling_formulas -- the enrichment parse. `--reparse` is a
# `corpus sync` flag and does not reach this stage. Its cache does record
# the formulas setting (chitragupta/enrich/_docling_cache.py), but that
# setting has not changed either, so the entries still match. Delete the
# cache file, which invalidates every entry at once:
rm content/docling_cache.json
python -m chitragupta.enrich --stages docling
```

**The fix.** `python3-dev` and `gcc` are in the `os-deps` package list, so
`bash scripts/install_full_pipeline.sh os-deps` (equivalently `chitragupta
install os-deps`) covers it. Hosts provisioned before 2026-09-05, including
any long-running container built from `docker/Dockerfile.claude`, need the
apt line above by hand.

**If you do not want formula recognition,** the cheaper answer is to leave
`[parser].formulas = false`. docling then writes
`<!-- formula-not-decoded -->` and never loads the model that needs
triton at all.
