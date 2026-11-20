# 📄 PDF parser tradeoffs for chitragupta

Status: **reasoning document.**

**Written for** someone choosing `[parser].backend`, or revisiting that
choice. **Assumed:** [CONFIG.md](CONFIG.md) for how to set it. **Not
covered here:** the measured cost of each backend, which is
[PERFORMANCE.md](PERFORMANCE.md).

## 🔭 Short summary

Two backends ship: `pdftotext` (the default) and `docling`. Two more were
evaluated on this corpus and removed: `markitdown`, which fuses adjacent
words ([why](#-why-markitdown-was-removed)), and `grobid`, whose header
metadata the bib file already supplies
([why](#-why-grobid-was-removed)). A proposal to bring GROBID back beside
docling, for a citation graph, is in
[GROBID-CITATION-GRAPH.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/GROBID-CITATION-GRAPH.md).
Four newer parsers were surveyed and none adopted
([analysis](#-four-newer-backends-evaluated-and-not-adopted)).

## ⚖ Comparison table

| Tool | Best at | Strengths | Weaknesses | Relative speed vs `pdftotext` | Status |
| --- | --- | --- | --- | --- | --- |
| `pdftotext` | Plain text extraction | Very fast, simple, byte-identical output across runs, no `enrich` group needed | Weak on layout, tables, headings and reading order; writes no passage sidecar | 1x | **Default** |
| `docling` | Layout-aware PDF parsing | Reading order, sections, tables and structured Markdown; the only backend that writes the passage sidecar a claim can be quoted from | Heavy, slower, model/runtime complexity; not reproducible under concurrency | ~42x slower with OCR on (5 real bib PDFs; see below) | Opt-in |
| `markitdown` | General file-to-Markdown conversion | Flexible normalization, multi-format support | Fuses adjacent words on this corpus (4.17% of tokens), which silently breaks BM25 ranking | ~17x slower (5 real bib PDFs) | Removed |
| `grobid` | Scholarly structure and references | Title, abstract, sections and references | Not a general-purpose plain-text extractor; needs a JDK 21 build and a long-running service | Separate from the main speed scale | Removed |

## 🧭 Which backend to choose

`[parser].backend` is a tier, not a ladder: you pick one, and if it is
unavailable `sync` warns and skips parsing rather than substituting the
other ([ARCHITECTURE.md](ARCHITECTURE.md#-ladders-and-tiers)). The
enrichment layer's `docling` stage always uses docling, whatever
`[parser].backend` says, and writes `content/docling/`, which BM25 never
reads.

| If you need | Set | Because |
| --- | --- | --- |
| The fastest parse and the smallest install | `backend = "pdftotext"` (the default) | It needs only poppler-utils, and its output is byte-identical across runs |
| A quotable paragraph with its page from a search (`retrieve search --unit passage`), `weight_abstract`, or the reference-list cut in BM25 | `backend = "docling"` | All three read the corpus layer's passage sidecar, which only docling writes ([RETRIEVAL.md](RETRIEVAL.md#-the-passage-unit)) |
| Better chunks for embeddings and topics, without changing what BM25 ranks | `pdftotext`, plus `python -m chitragupta.enrich --stages docling` | The embedding stage prefers `content/docling/<doc>.md` when it exists |
| Title, authors, year and DOI | either | `papers/bibliography.bib` is the source of truth for metadata ([CONFIG.md](CONFIG.md)); no parser re-derives it |

### 🧱 What `docling` costs

**The ~42x figure is the OCR-on ceiling**, Docling's default but not this
project's (`[parser].ocr = false`). Over the whole corpus, OCR off is
**2.08x** faster serially and up to **4.79x** at 24 workers; a full
501-PDF serial parse takes 55m 30s with OCR off against 1h 56m with it
on. OCR off drops text the PDF stores as a bitmap, mostly publisher
furniture and figure sub-captions on this sample but two whole tables in
one document. See
[PERFORMANCE.md](PERFORMANCE.md#-parserocr----the-largest-single-lever-and-a-trade).

**Its output is not reproducible under concurrency.** With a worker
pool, dense reference blocks are grouped into elements slightly
differently between runs, so a quoted span can change across a re-parse.
Ranking is unaffected, because `chitragupta/retrieval.py` tokenises on
runs of `[a-z0-9]`. Docling exposes no determinism setting; `pdftotext`
does not have the problem. The measured rates are in
[ARCHITECTURE.md](ARCHITECTURE.md#-what-is-reproducible-and-what-is-not).

It also needs system libraries nothing else here needs, and a missing
one produces a misleading error; see
["docling fails every document with an OpenCV recursion error"](#-docling-fails-every-document-with-an-opencv-recursion-error).

## 🧪 Four newer backends, evaluated and not adopted

Surveyed 2026-08-05 from each project's own documentation, without a
trial run: **marker**, **surya**, **xberg** and **unstructured**, against
docling as the incumbent. Nothing was adopted.

### 🏷 What "fit" means here

A replacement has to supply every docling behaviour this repository
depends on:

| What the repo uses | Where |
| --- | --- |
| Per-item `label`, `text`, `prov[0].page_no`, `prov[0].bbox` | passage provenance, `chitragupta/passages.py` |
| `pic.caption_text(dl_doc)`: figure caption matched to "Figure N" in prose | `_figure_records`, see `DEVELOPER.md`'s "Figures and copyright" (git checkout only) |
| `export_to_markdown()` | `content/docling/<citekey>.md`, the artefact downstream stages read |
| `AcceleratorOptions(device="cuda:N", num_threads=...)` set **per worker process** | `init_worker`, one GPU claimed round-robin |
| A togglable OCR flag, default off | `[parser].ocr` |
| A togglable formula-recognition flag, default off; without one, an equation reaches `content/parsed/` as a `formula-not-decoded` marker instead of as LaTeX | `[parser].formulas` |

### ⚖ Comparison

| | **docling** (incumbent) | **marker** | **surya** | **xberg** | **unstructured** |
| --- | --- | --- | --- | --- | --- |
| Category | End-to-end layout-aware PDF→doc | End-to-end PDF→Markdown/JSON, built on surya | Layout/OCR/table **primitives** (marker's foundation) | Polyglot doc-intelligence engine, Rust core | ETL "elements" extractor, multi-strategy |
| Native Markdown export | Yes | Yes | **No**: assembly required | Yes (+ Djot/HTML/JSON) | **No**: typed `Element` list only |
| Provenance (page + bbox + label) | Yes, per item | Yes, JSON block tree | Yes, but page/doc assembly is on you | Yes, "Structured" JSON | Yes, per element |
| Figure↔caption auto-linking | **Yes** | Undocumented | Not provided | Unverified | Undocumented |
| Table extraction | Structured, built in | Structured (HTML), CPU heuristic + VLM fallback | Structured (HTML/cells) | Structured (TATR/SLANet) | Structured (TATR) |
| GPU model | Optional, **in-process** | External inference server (vLLM/Docker), **OCR paths only** | Same server requirement | Optional, CPU-first (ONNX) | CPU-historically; GPU auto-detect unverified |
| OCR off-switch | Yes | Yes (`--disable_ocr`) | **No**: inherent to the VLM | Yes, swappable backends | Yes, via `strategy` |
| Fits the per-process CUDA-device pool | Yes (built for it) | OCR off: yes. OCR on: **no** | **No** | Mostly: no persistent CUDA context | Roughly, in-process ONNX |
| Code license | MIT | Apache-2.0 | Apache-2.0 | MIT | Apache-2.0 |
| Model-weight license | Open weights | **Modified OpenRAIL-M**: free under $5M revenue, else paid | Same OpenRAIL-M variant | N/A | N/A |
| System deps beyond pip | None with OCR off | vLLM + Docker + NVIDIA toolkit, or llama.cpp, **only if OCR is used** | Same as marker | None (bundles ONNX) | libmagic, poppler, tesseract, libreoffice, pandoc |
| Maturity | Established, IBM-backed | Established; v2.0 rewrite Jul 2026 | Established; v2 rewrite May 2026 | v1.0 days old at survey time | Established |

### ⚠ The finding that would break a naive swap

**marker and surya moved OCR and layout to a locally-spawned inference
server** (vLLM on GPU, llama.cpp on CPU) in their 2026 rewrites. Workers
become HTTP clients of one shared server, so this repository's
`ProcessPoolExecutor` + `init_worker` GPU round-robin does not carry over
([PARALLELISM.md](PARALLELISM.md#-components)). That cost applies only
with OCR on. Under `--disable_ocr`, this project's default configuration,
marker starts no server: layout comes from an in-process `rf-detr`
detector, text from `pdftext`, tables from CPU heuristics, which is close
in shape to docling.

### 📊 Where each one lands

1. **surya: do not target directly.** It is marker's primitive layer;
   using it means rebuilding everything marker already does.
2. **marker: the strongest candidate, and only with OCR off.** It still
   needs a JSON→passage/figures mapping layer and custom figure↔caption
   linking, and the OpenRAIL-M weight licence applies even with the VLM
   disabled.
3. **xberg: best licence and CPU story, too new to trust.** It would
   need a measured pilot first.
4. **unstructured: most work, least gain.** No native Markdown export
   and the heaviest system dependencies.

### 🏁 Conclusion of the alternatives review

**Stay on docling.** Its weaknesses are measured and written down, which
is worth more than an unmeasured alternative's. marker, xberg and
unstructured share one blocker: **figure↔caption auto-linking is
undocumented in all three**, and `_figure_records` depends on it. If
this is revisited, pilot marker with OCR off against the real 501-PDF
corpus, the measurement that removed markitdown and GROBID.

## 🗑 Why GROBID was removed

GROBID only ever called `/api/processHeaderDocument`, for
title/authors/abstract: metadata `papers/bibliography.bib` already
supplies, via `chitragupta/bib_reader.py`, for every PDF the project
parses.

What only GROBID offered was parsing a paper's reference list into
structured records (`/api/processFulltextDocument`, never called here).
That serves corpus discovery, not grounding. Extracted references are not
in the bib file, so per AGENTS.md's citekey invariant no draft may cite
them, and `chitragupta/enrich/corpus.py` sources the enrichment corpus
from the ledger only, so there is nowhere to index them either. A
discovered paper enters the way every other one does: catalogue it,
re-export, and re-run `python -m chitragupta.corpus sync`.

The cost was an exactly pinned JDK 21, a multi-GB Gradle build, and a
long-running service on port 8070. If snowballing ever becomes a real
workflow, the case to revisit is for `/api/processFulltextDocument`, not
the header endpoint.

## 🗑 Why markitdown was removed

**The symptom.** Over the same 10 CPS papers, `markitdown` produced
**3,647 alphabetic tokens longer than 20 characters (4.17% of all
tokens)** against `pdftotext`'s **9 (0.01%)**, and 23% fewer words,
because words were being fused together:

```text
isaninputtooranoutputfromafunction
AnnualReviewsinControl51(2021)357-373
theapplicationofthevery same principles
```

`chitragupta/retrieval.py` is BM25 over tokens split on runs of
`[a-z0-9]`, so a query for "cyber physical" cannot match
`cyberphysicalsystems`: a silent ranking failure.

**The cause.** `markitdown` calls pdfplumber's `page.extract_text()`,
whose default `x_tolerance` of 3 points merges glyphs closer than that.
These papers set inter-word spacing below 3pt. On four of them,
`x_tolerance=1` eliminated every over-long token (179 -> 0, 83 -> 0,
164 -> 0, 141 -> 0). `markitdown` hardcodes the tolerance and its
`convert()` never forwards `**kwargs`, so it cannot be fixed through its
public API. Its own source says the heuristic is "not for multi-column
text layouts in scientific documents".

**What replaced it.** Nothing: it was worse than `pdftotext` on text and
worse than `docling` on structure. Using `pdfplumber` directly with a
tuned tolerance was deferred: no current use case needs a third backend.
Instead, a parse-quality guard (`chitragupta/pdf_text.quality_warning`,
wired into `sync`) warns when more than 1% of a document's words exceed
20 characters. The two backends sit three orders of magnitude apart on
that measure, so the threshold needs no precise tuning.

## 🐛 docling fails every document with an OpenCV recursion error

The `os-deps` stage prevents this. A host provisioned some other way will
hit it, and the error points at nothing useful.

**The symptom.** With `[parser].backend = "docling"`, `sync` prints a
bare `sys.path` listing and then fails every document it had to parse:

```text
['/workspace', '/usr/lib/python313.zip', ..., '/workspace/.venv-full/lib/python3.13/site-packages']
[497/497] noauthor_logical_nodate
FAILED  shao_use_2021: ERROR: recursion is detected during loading of "cv2" binary extensions. Check OpenCV installation.
```

There is no recursion, and OpenCV is installed correctly.

**The mask.** `cv2/__init__.py` sets `sys.OpenCV_LOADER = True` during
its bootstrap. If the first `import cv2` dies partway, the flag leaks,
and every later import in that process or its forks reports the
recursion error (and prints `sys.path`). To reproduce the mask:

```console
$ python -c "import sys; sys.OpenCV_LOADER = True; import cv2"
ImportError: ERROR: recursion is detected during loading of "cv2" binary extensions.
```

`prestart_pool()` (`chitragupta/pdf_text/_startup.py`) preloads
`docling` in a forkserver, whose `main()` discards the `ImportError`, so
every forked worker inherits the poisoned flag.

**The real cause.** The enrich group's `docling` pulls
`docling-slim[standard]`, which pulls `rapidocr`, which requires the
GUI-linked `opencv-python` distribution by name. Its `cv2.abi3.so` needs
`libGL.so.1`, `libglib-2.0.so.0` and the X libraries from the system,
and a base image installed with `--no-install-recommends` has none of
them. The exact first error is inferred, not captured; the mask
mechanism and the remedy are confirmed.

**The fix.** `libgl1` and GLib are in the `os-deps` package list, so
`chitragupta install os-deps` covers it. By hand:

```console
sudo apt-get install -y libgl1 libglib2.0-0t64   # libglib2.0-0 before Ubuntu 24.04 / Debian 13
```

**To see the real error instead of the mask,** run the parse serially,
so the import happens in-process with no preload to swallow it:

```console
PARSER_WORKERS=1 python -m chitragupta.corpus sync
```

**Why `opencv-python-headless` is not the fix.** `rapidocr` requires
`opencv-python` by name, so a constraint would install both
distributions into the same `cv2/` directory. Swapping after install was
not worth it against two apt packages.

## 🐛 docling silently empties every formula on a GPU host

The `os-deps` stage prevents this too. It happens only with
`[parser].formulas` (or `[enrich].docling_formulas`) turned on, which is
not the default, and it fails neither the run nor the document.

**What it looks like.** A `sync` that keeps going, with one line per
affected document buried among docling's table-recovery warnings:

```text
[vaillant_towards_2022] Error processing code/formula batch: Command '['/usr/bin/gcc',
  '.../triton/backends/nvidia/driver.c', ...]' returned non-zero exit status 1.
[5/497] vaillant_towards_2022
```

and, further up, the compile that failed:

```text
.../triton/backends/nvidia/driver.c:9:10: fatal error: Python.h: No such file or directory
```

**The cause.** torch's default Linux wheel bundles triton. With a GPU
visible, triton compiles a small C shim (`backends/nvidia/driver.c`) at
the first CUDA kernel launch, a runtime `gcc` call that `#include`s
`Python.h`. A host with no CPython development headers fails it. A
CPU-only host never sees this.

**Why it does not look like a failure.** docling catches the exception
per batch and assigns `""` to every formula in it; the document converts
and the ledger records it as parsed. The Markdown serializer then writes
`<!-- formula-not-decoded -->` for each, exactly the `formulas = false`
output, after paying for the model download and the extra pass per page.

**How to tell, if you no longer have the log.** A successful recognition
writes LaTeX between `$$` delimiters and leaves no marker:

```console
grep -l 'formula-not-decoded' content/parsed/*.txt | wc -l   # 0 when healthy
grep -l '\$\$' content/parsed/*.txt | wc -l                  # 0 is the tell
```

On this project's 497-document corpus:

| `[parser].formulas` | Docs with a marker | Docs with `$$` LaTeX |
| --- | --- | --- |
| `false` | 148 | 0 |
| `true`, model ran | 0 | 151 |
| `true`, this failure | as `false` | 0 |

So one marker while the key is on is enough for the diagnosis. The
`false` row is the measurement
[CONFIG.md](CONFIG.md#-formulas-and-why-it-is-not-the-enrich-key)
records.

**Re-running does not repair it.** Both caches key on the input PDF,
which has not changed, and the two settings recover differently:

```console
sudo apt-get install -y python3-dev gcc     # or re-run the os-deps stage

# [parser].formulas -- the corpus parse; --reparse overrides the
# (size, mtime) skip.
python -m chitragupta.corpus sync --reparse

# [enrich].docling_formulas -- the enrichment parse. --reparse does not
# reach it, and its cache entries still match, so delete the cache file:
rm content/docling_cache.json
python -m chitragupta.enrich --stages docling
```

**The fix.** `python3-dev` and `gcc` are in the `os-deps` package list,
so `bash scripts/install_full_pipeline.sh os-deps` (or `chitragupta
install os-deps`) covers it. A host provisioned another way, or a
long-running container that has not re-run `os-deps`, needs the apt line
above by hand. If you do not want formula recognition, leave
`[parser].formulas = false`: docling then never loads the model that
needs triton.
