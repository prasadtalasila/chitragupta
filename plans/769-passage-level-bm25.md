# 🧩 Passage-level BM25, with a cap on passages per paper (#769)

Status: **built.** Written 2026-09-15, implementing issue #769. PR number
to be recorded here when it lands.

**What changed on the way**, four things, each because the code or the
measurement disagreed with this document:

1. **No over-fetch multiplier.** This plan specified one, on the strength
   of the embedding path's. Wrong here: that path caps a list Chroma has
   already truncated, and `_bm25_scores` truncates nothing, so the cap
   walks the fully ranked list and an over-fetch knob would have had one
   answer at every setting. The config key was written and then removed.
2. **Two splits, not one.** `retrieval_passages.py` crossed the C2 limit
   at 270 lines the moment it was first written, and `retrieval_cli.py`
   crossed it at 280 when the `--unit passage` printer went in. Hence
   `retrieval_passages_cache.py` and `retrieval_passages_cli.py`. Both
   splits were forced rather than chosen.
3. **`without_sidecar` counted the wrong thing**, and the real-corpus
   smoke run is what caught it: it reported 2 on a corpus where all 497
   documents have a sidecar, because a document whose passages all fell
   under the token floor was counted as sidecar-less. The cache entry now
   records the sidecar's presence explicitly.
4. **The measurement did not say what this plan assumed.** Recall falls
   rather than holds -- 0.8086 → 0.6914 and 0.8646 → 0.7812 -- and source
   diversity is *spent* by the smaller unit rather than gained, since the
   document unit is 5-of-5 by construction. The feature earns its place
   on evidence quality (99.8% → 16.4% of returned text cut mid-sentence,
   and a page on every hit), which is a narrower claim than this document
   started with. `docs/RETRIEVAL.md` and `bench/RESULTS.md` carry it.

**Written for** the person about to build a second BM25 index whose unit
is a paragraph rather than a document, alongside the one
`chitragupta/retrieval.py` already ships.
**Assumed:** you have read `docs/RETRIEVAL.md`'s BM25 section,
`chitragupta/passages.py`'s module docstring, and
`chitragupta/_reference_cut.py`. You have a synced ledger with
`content/parsed/<citekey>.passages.json` sidecars.
**Not covered here:** field weighting (issue 762), which lands first and
changes the baseline this is measured against; the embedding path, which
already ranks chunks and already has the cap this borrows.

## 🎯 What is actually being fixed

Today's BM25 path scores with one function and displays with a different
one, and the second never feeds back into the first.

| | ranks | displays |
| --- | --- | --- |
| Function | `retrieval._bm25_scores` | `retrieval._snippet` → `_windows` |
| Unit | one whole document per citekey | a 500-character character window |
| Criterion | IDF × saturated TF, length-normalized against corpus `avgdl` | count of *distinct* query terms inside the window |
| When | over the whole ledger | after the top-k is already decided |

So the text a drafting agent is shown as evidence was chosen by a
criterion that had no part in deciding the document was worth showing.
`chitragupta/passages.py`'s own docstring already names this as the
defect its seam was extracted for, and says it is unbuilt: "a snippet
shown to a drafting agent as evidence is under exactly the same
constraint as a passage shown to a reviewer, and the two should not
answer 'what does this source say here?' from different text -- but
today they do."

The structural payoff is not in the issue's checklist, and it is the
reason to build this: **the two stages collapse into one.** What ranks
becomes what is shown. The reading position comes along for free,
because a sidecar record already carries its page.

## 🏗 Design

### The unit, and where it comes from

One index entry per `(citekey, passage_index)`, where `passage_index` is
the record's position in `passages.corpus_passages(citekey)` -- the
sidecar's own reading order, so the number is stable and a caller can
say "the 14th passage" and mean it.

**`corpus_passages`, not `structural_passages`.** Rung 2 alone, for
exactly the reason `_reference_cut` already chose it:
`chitragupta/retrieval.py` promises that running `chitragupta.enrich`
does not change what BM25 ranks, and rung 1 is the enrichment layer's
own parse. Preferring rung 1 here because it is "better" would break
that promise silently -- the scores would move on a host that had run
`--stages docling` and nowhere else.

### Which labels are indexed, and the short-passage trap

`PASSAGE_LABELS` is `text`, `list_item`, `section_header`, `title`,
`formula`, plus `table` records written by the table loop. Not all of
them should rank.

BM25's length normalization (`b = 0.75`) *rewards* a short dense match.
At document scale that is harmless; at passage scale a three-word
`section_header` whose text is the query is the highest-scoring object
in the corpus, and it is not evidence of anything. The same arithmetic
is why the issue's Additional Context is wrong about reference lists: it
expects them to become "low-value passages", when a bibliography entry
is a short passage stuffed with title words and will rank *higher* as a
passage than it ever did pooled into a document.

The design therefore:

- indexes `text`, `list_item`, `table` and `formula`;
- excludes `section_header` and `title` -- the document's title is
  already a field on the document-level path, and issue 762 is where
  title matching gets its answer;
- applies a minimum token floor below which a passage is not indexed at
  all, default proposed as 20 tokens *after* `_tokenize`, to be confirmed
  by the measurement below;
- cuts the reference tail **by passage position**, not by re-deriving the
  boundary from flattened text.

That last point needs a small addition to `chitragupta/_reference_cut.py`:
today `strip_references(text, parsed_path)` returns truncated *text*,
and `_last_header` is private and returns the header's *string*. Expose
the index of the last reference `section_header` within a passage list
(`reference_cut_index(found) -> int | None`), and have `strip_references`
keep using it so there remains exactly one rule in one place. Passages
at or after that index are not indexed.

### Scoring

Reuse `retrieval._bm25_scores` unchanged -- it is already generic over
its dict key, despite the local variable being named `citekey`; rename
that local to `key` and nothing else moves. Pass it a dict keyed by the
`(citekey, passage_index)` tuple.

**`chitragupta/retrieval.py` takes no net new lines in this work.** It is
a registered C2 offender with about two docstring lines of headroom, and
growing it reddens the ratchet independently of the lint. The rename
above adds none; nothing else in step 3 may land there.

`N` is the passage count, document frequency is passage frequency, and
`avgdl` is the mean passage length. This is a **different IDF and a
different normalizer** from the document index, so scores from the two
units are not comparable and nothing may sort them into one list. Say so
in the docstring and in `docs/RETRIEVAL.md`; that is the failure mode a
later "hybrid" idea will walk into.

The `collection` filter works the same way and for the same reason:
applied to the ranking, never to the index, so IDF does not depend on
the filter and one cache serves both.

### The cap, and why a cap alone is a bug

The issue's checklist says only "no citekey contributes more than the
configured number of passages to one result set". Implemented literally,
that reproduces the exact defect `config.toml.example` already documents
for the embedding path: "At 1 the cap can only shorten -- which is the
failure issue 305 existed to fix."

So the cap needs an over-fetch alongside it. Rank `k × multiplier`
passages, drop each citekey's excess from that longer list, then
truncate to `k` -- which *promotes* another paper's passage into the
window rather than merely making the list shorter.

Two new settings under a new `[retrieval]` section, named to mirror the
enrichment pair so the two paths read as one idea:

| setting | default | mirrors |
| --- | --- | --- |
| `max_passages_per_source` | 3 | `[enrich].embed_max_passages_per_source` |
| `overfetch_multiplier` | 4 | `[enrich].embed_overfetch_multiplier` |

Read through `config._get_positive_int`, as that pair already is.

Neither `[retrieval]` exists yet in `config.toml.example` or
`docs/CONFIG.md`. Issue 762 needs the same section. Whichever lands
first creates it; do not block on the other.

### Determinism

`retrieval._windows`' docstring is a monument to what per-process string
hashing does to a result that reads a `set`'s order. Two places here can
repeat that mistake:

- the final sort, which must break ties on `(citekey, passage_index)`;
- the cap, whose "which 3 of this paper's 8 survive" must be
  "the 3 highest-scoring, ties broken on passage index", never
  "whichever 3 iteration reached first".

Both belong in the tests, phrased as properties rather than as fixtures.

### The result type

A new dataclass, not an overloaded `SearchResult`: checklist item 3
requires the document-level `search()` to be unchanged, and
`snippet_chars` has no meaning for a passage hit whose length is the
paragraph's own.

```python
@dataclass
class PassageResult:
    citekey: str
    title: str          # the document's, from the ledger row
    score: float
    text: str           # the passage verbatim -- quotable by construction
    page: int | None
    passage_index: int
    label: str | None
```

`text` is verbatim rather than window-cut, which is the whole point:
this is rung-2 reading-ordered text, so it may be quoted, and
`passages.Passage.quotable` is `True` for every record that reaches
here.

### Caching

A second cache file, `content/retrieval_passage_index.json`, with its
own `_INDEX_SCHEMA_VERSION` starting at 1.

**Its fingerprint must include the sidecar's own stat**, which the
document index's deliberately does not. `retrieval_cache`'s comment
explains why it is safe to omit there: `passages.clear_sidecar` runs
before every re-parse and the same parse rewrites the `.txt`, so the
sidecar cannot move without the `.txt`'s mtime moving. That argument
covers the case where the `.txt` is the source of truth and the sidecar
supplies one boundary. Here the sidecar *is* the source of truth, and a
hand-written or externally-restored sidecar beside an untouched `.txt`
would be invisible. Fingerprint on `(title, parsed_path, status, sidecar
exists/size/mtime_ns)`.

Cache shape stays JSON-able by nesting rather than by stringifying the
tuple key:

```json
{"version": 1,
 "items": {"<citekey>": {"fingerprint": [...],
                         "passages": [{"i": 3, "length": 84,
                                       "term_freqs": {"twin": 2}}]}}}
```

The flat `(citekey, i)`-keyed scoring index is assembled in memory.

Do **not** reach into `retrieval_cache._load_cache` / `_fingerprint` /
`_tokenize_item` to generalise them: `chitragupta/dossier/_drift.py`
composes all three directly and that module's docstring says so. A
parallel, small cache module is cheaper than a shared abstraction with
two callers pulling in opposite directions.

### Module placement

New module `chitragupta/retrieval_passages.py`, importing `_tokenize`,
`_bm25_scores` and `_query_terms` from `chitragupta/retrieval.py` in
that direction only -- the same arrangement `retrieval_cli.py` already
has. It must not go into `retrieval.py`: that file's own comment records
it has about two docstring lines of headroom under
`docs/CODE-STANDARDS.md`'s C2 limit, so this could not even be
documented there. Put the cache in `retrieval_passages_cache.py` if the
combined module crosses 250 code lines; measure before splitting, per
the C2 ratchet.

### CLI surface

A `--unit {document,passage}` flag on the existing
`python -m chitragupta.draft retrieve search`, defaulting to `document`.

Deliberately not a new subcommand: `docs/PACKAGING.md` carries a
test-enforced leaf-command count and a command table, and a new leaf
moves a number that contains no command name. A flag also states the
relationship correctly -- same question, two units -- which a sibling
subcommand would not.

`--unit passage` prints citekey, score, page and the passage verbatim.
It should also print a one-line note naming how many ledger items have
no sidecar and are therefore unreachable on this path (see below).

## ⚠️ What this does not touch, and say so

- **`search()` is unchanged.** Same signature, same scores, same
  snippets. The choice of unit is the caller's, per checklist item 3.
- **`evidence` is unchanged.** It answers "what in *this* paper bears on
  my query" for a document already chosen, and it deliberately ranks the
  same text BM25 ranked. Changing it is a separate question.
- **`retrieval_iterative.search_iterative` stays document-only.** It
  merges two rounds on citekey and caps back to `k`; a passage unit
  changes that merge key and its dedup semantics. Out of scope, and
  named in the docstring as out of scope so the next reader does not
  read the omission as an oversight.
- **No genre skill changes.** Nothing in `.claude/skills/` switches unit
  in this PR. Measure first; a skill change is its own decision with its
  own review.

## 🕳 The coverage question the issue does not answer

The index is built "over the corpus layer's sidecars alone", so a
citekey parsed by `pdftotext` has no sidecar and is **absent from this
index entirely** -- not ranked low, not there. That is a source a
passage search can never return.

On the corpus this is being built against the cost is currently zero:
497 of 497 items in `/workspace/content/parsed/` have a
`.passages.json` sidecar. It is not zero for a user on
`[parser].backend = "pdftotext"`, for whom this index would be empty.

**Decision: absent, and reported.** Falling back to a document-level hit
for those items would put two incomparable scores in one ranking (see
"Scoring" above), which is worse than a stated gap. The passage path
therefore counts sidecar-less items and says so -- in the CLI note, and
by returning that count from the search function so a programmatic
caller can act on it. An all-empty index gets a specific message naming
`[parser].backend`, not "No results."

## 📏 Measurement

Both existing arms rank *papers*, so a passage arm has to collapse to
citekeys before recall@k means anything.
`bench/bench_retrieval_compare.py` already has `collapse_to_citekeys`
for exactly this, written for the dense-chunk rows; reuse it rather than
writing a second one.

New `bench/bench_retrieval_passage.py` scoring, against both
`bench_retrieval_keyword_selfretrieval.py`'s 256 queries and
`bench_retrieval_live_logs.py`'s 96:

1. recall@5 and nDCG@5, passage hits collapsed to citekeys, against the
   document-level BM25 row and the dense row -- checklist item 4.
2. **Distinct sources in the top five**, before and after the cap, with
   the cap at 1/2/3 and the multiplier at 1/4. The multiplier at 1 is
   the control that shows a cap alone only shortens.
3. **Evidence quality, which recall cannot see**, in the register
   `docs/RETRIEVAL.md` already uses for the reference cut: what
   fraction of returned text is a whole reading-ordered paragraph rather
   than a character window cut mid-sentence. That is the figure this
   feature exists for, and the document arm scores 0 on it by
   construction.
4. The short-passage floor swept at 0/10/20/40 tokens, to turn the
   proposed default of 20 into a measured one.

Pin every `PARSER_*` setting in the harness -- the host `config.toml`
has OCR and formulas on, so an unpinned arm measures a different parse
from the record it is compared against. Follow `bench/`'s self-check
convention: fabricate a difference and assert the script sees it. Adding
any `bench/*.py` also reddens the test that counts them.

Run from `.venv-full`, with `CONTENT_DIR` pointed at the real corpus.

## 📋 Order of work

1. `reference_cut_index` in `_reference_cut.py`, with `strip_references`
   rewired through it. No behaviour change; tests should not move.
2. `[retrieval]` section: `config.py`, `config.toml.example`,
   `docs/CONFIG.md`. Skip if 762 has already created it.
3. `retrieval_passages.py`: index build, cache, `search_passages`, the
   cap and over-fetch, `PassageResult`.
4. `--unit passage` on the CLI, plus the sidecar-coverage note.
5. `bench/bench_retrieval_passage.py` and the run.
6. `docs/RETRIEVAL.md`: the "Unit of a hit" row now needs two BM25
   columns or a footnote, a new section carrying the figures, and the
   `_snippet`-vs-`_bm25_scores` split named explicitly -- it is the
   thing the feature closes.
7. `docs/RAG.md` and `docs/CORPUS-SEARCH.md` sweep: grep for "whole
   document" and "one per citekey" rather than diffing the files this
   PR touched.

Steps 1 and 2 are independently mergeable and worth landing first if the
PR gets large; step 3 is the one that needs the review attention.

## ✅ Definition of done

Beyond the issue's own checklist:

- `pytest` green with 100% line *and* branch coverage -- CI fails at
  99.94%.
- The four lint commands plus `markdownlint-cli2` on the branch tip.
- Version bumped in `pyproject.toml`, re-checked against `main` after
  any other PR merges.
- `python -m chitragupta.draft gate` unaffected: no new check is
  promoted into a gate, per the issue's last checklist line.
- No citekey is generated, guessed or rewritten. This feature reads
  citekeys from the ledger and sidecar filenames only, exactly as
  `_reference_cut.strip_references` already does, and writes none.
