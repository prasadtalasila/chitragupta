# E1: strip interrogatives on the query side

Status: **plan.** Written 2026-08-29, for
[issue 453](https://github.com/prasadtalasila/chitragupta/issues/453) --
[E1](../docs/FEATURE-ROADMAP.md#-e1-strip-interrogatives-on-the-query-side)
in docs/FEATURE-ROADMAP.md.

**Written for** whoever builds E1. **Assumed:** the recall table in
[docs/CORPUS-SEARCH.md](../docs/CORPUS-SEARCH.md#-before-stage-1-the-shape-of-the-query)
and the same measurement restated in
[docs/RAG.md](../docs/RAG.md#-one-measured-hazard) -- this plan does not
re-derive it, only implements what it already proved. **Not covered
here:** E2 (an outline the human writes), which depends on this landing
first but is its own plan; the `co-simulation` -> `simulation` defect
CORPUS-SEARCH.md records next to this one (`len(w) > 2` dropping `co`)
-- named there because the term is central to the same illustration, not
because it is this fix.

## 🧭 Table of contents

- [What was measured, and what it does not license](#-what-was-measured-and-what-it-does-not-license)
- [Where a query is tokenized -- three call sites, not one](#-where-a-query-is-tokenized----three-call-sites-not-one)
- [Candidates considered for a stopword package](#-candidates-considered-for-a-stopword-package)
- [The change, drawn](#-the-change-drawn)
- [The citation-marker hygiene sub-item](#-the-citation-marker-hygiene-sub-item)
- [The C2 line budget](#-the-c2-line-budget)
- [Build order](#-build-order)
- [Docs and roadmap sweep](#-docs-and-roadmap-sweep)
- [Verification](#-verification)

## 🧺 Consolidating the stopword core with `passages.py`

Bundled into this PR at the human's request, not part of issue #453's
own text. `passages.py::_STOPWORDS` (37 words) is `retrieval.py`'s 19
words verbatim, plus 18 more -- a copy-paste, not a coincidence, found
while checking whether a stopword package existed worth using for E1
(it didn't; see the candidates table above). advisor reviewed this
design twice: once to confirm consolidation was warranted only for this
pair (not `overlap_skipgram.py` or `enrich/topic_labels.py`, whose
lists are deliberately different sizes for stated, opposite reasons),
and once against the actual import graph, which reversed the direction
originally proposed.

**Direction: `retrieval.py` imports from `passages.py`, not the other
way around.** `passages.py` is consumed by the corpus layer
(`pdf_text/`, `ledger_upsert.py`), the enrichment layer, and the review
layer; `retrieval.py` is drafting-layer only. Having `passages.py`
depend on `retrieval.py` would mean `chitragupta corpus sync`
transitively depends on drafting-layer code -- backwards. The corrected
direction is the same shape as `retrieval.py` already importing
corpus-layer `ledger`. Verified acyclic: `passages.py` imports only
`chitragupta.config`, which imports neither module.

```python
# chitragupta/passages.py
_CORE_STOPWORDS = {
    "a", "an", "the", "of", "on", "in", "for", "and", "to", "with",
    "is", "are", "be", "this", "that", "as", "by", "from", "at",
}

# Shared with chitragupta/retrieval.py, which imports _CORE_STOPWORDS
# from here (this module has no drafting-layer dependents, so this is
# the direction that keeps the corpus/enrichment/review layers
# independent of drafting). Editing this constant moves retrieval.py's
# BM25 index too and needs _INDEX_SCHEMA_VERSION bumped there --
# passages.py's own extras just below are free to change on their own.
_STOPWORDS = _CORE_STOPWORDS | {
    "it", "its", "can", "has", "have", "was", "were", "which", "such",
    "these", "those", "their", "than", "then", "but", "not", "also",
}
```

```python
# chitragupta/retrieval.py -- replaces the local _STOPWORDS literal
from chitragupta.passages import _CORE_STOPWORDS as _STOPWORDS
```

**A real, verified bonus, not a side claim:** `chitragupta/passages.py`
is currently a registered C2 offender at 260 code lines
(`code-standards-register.toml`). The 37-word flat literal this removes
is ~31 code lines; the compact core-plus-extras form above is ~8. That
drops the module to roughly 229 lines -- under the 250 limit, so its
register entry is deleted rather than shrunk, which
`test_every_registered_offender_records_its_current_count` requires
either way. `chitragupta/retrieval.py` loses its own 21-line literal and
gains a 1-line import, which only widens the C2 margin the section
below already counts on.

**Cascade this triggers, checked in advance so it isn't found by a red
CI run:**

- `docs/CODE-STANDARDS.md:298-299` states "**3 functions** and **7
  modules**", pinned by
  `test_the_registers_are_the_size_this_document_says`. Becomes **6
  modules**.
- `docs/TECHNICAL-DEBT.md:101-102` states the same pair independently
  ("`code-standards-register.toml` freezes **3 functions** over C1 ...
  and **7 modules** over C2"), pinned by
  `test_the_stated_register_sizes_match_the_registers`. Becomes **6
  modules** too.
- `docs/TECHNICAL-DEBT.md:454-461` also names `chitragupta/passages.py`
  in a historical paragraph about a past reformat PR ("Six modules
  crossed the C2 250-code-line limit from the reformat alone..."). This
  one does **not** need editing: `test_technical_debt_scan.py`
  deliberately only checks a Tier-1 subsection heading or a
  `[Tier 1]`-tagged "What to take first" item (its own docstring: "Not
  free-standing factual claims" / "Not every `chitragupta/*.py` token in
  the document") -- this mention is neither, and it correctly describes
  a past event regardless of the module's current line count.

Size: XS, folded into this PR rather than its own issue -- a pure
internal dedup with no behavior change, verified by the existing
`tests/test_passages.py` assertions (`distinctive("The cat is on a mat")
== {"cat", "mat"}`) passing unchanged.

## 📊 What was measured, and what it does not license

`_STOPWORDS` (`chitragupta/retrieval.py`) holds twenty function words and
no interrogatives, and `len(w) > 2` passes `how`, `why`, `who`, `can`,
`what`, `does`, `did`, `which`, `when`, `where`, `whom`, `whose`,
`could`, `would`, `should`, `will`, `shall`. Because those are rare in
academic PDFs they carry high IDF and compete for the ranking against
the terms a query is actually about.

`bench_retrieval_keyword_selfretrieval.py`'s ground truth -- a paper's
own author-assigned `keywords`, wrapped in interrogative glue -- measured
this over 208 parsed entries:

| Query form | recall@5 | recall@10 |
| --- | --- | --- |
| author keywords (baseline) | **0.808** | **0.865** |
| wrapped as a question | 0.731 (-0.077) | 0.812 (-0.053) |
| question, interrogatives stripped | 0.788 (-0.019) | 0.846 (-0.019) |
| keywords, interrogatives stripped | 0.808 (**+0.000**) | 0.865 (**+0.000**) |

Two things follow, and the second is a scope guard as much as a
finding:

- **Stripping is free on keyword queries** -- the last row is +0.000 at
  both cut-offs, so nothing that already searches in keywords is ever
  harmed.
- **It is a partial fix.** 75% of the loss recovers at k=5, 64% at
  k=10. A wordier question template (adding ordinary words like "role"
  or "evaluate", which are not stopwords) recovers only about a third,
  because *"a question is not merely a keyword query with interrogatives
  attached; it carries generic content words that compete for the
  ranking on their own"* (CORPUS-SEARCH.md). So this does not make
  question-form querying safe, and "phrase it as keywords" stays the
  standing advice in CORPUS-SEARCH.md and in every genre skill's
  Retrieve step. **This plan does not change that advice.** It only
  makes a human-written query (E2) no worse than the sub-theme a skill
  already hand-tunes.

**What this plan still owes and does not fill in:** the wrapping
templates above are synthetic, so the residual loss depends on how
wordy a real question is, and no claim-form regression (a query phrased
as an assertion rather than a question) has been run. Both are reported
as open, not filled, in the bench task below -- filling them is a
separate measurement, not part of this fix.

## 🔍 Where a query is tokenized -- three call sites, not one

The roadmap frames this as "query-side only," but `_tokenize` has three
callers that take a **human- or skill-authored query string**, not just
`search()`:

| Call site | File:line | What it does with the query |
| --- | --- | --- |
| `search()` | `chitragupta/retrieval.py:244` | ranks documents by BM25 |
| `evidence()` | `chitragupta/retrieval_cli.py:73` | finds the best-covering passage in one already-chosen document |
| `DriftIndex.matches()` | `chitragupta/dossier/_drift.py:138` | replays a **recorded** query (one `search()` already ran, logged in `retrieval.md`) to decide whether a new corpus paper would now surface |

The third one is easy to miss and matters most for correctness: if
`search()` strips interrogatives but `_drift.py` replays the same
recorded query through raw `_tokenize()`, drift reporting silently
diverges from what `search()` actually returns for that query today --
exactly the kind of ledger/dossier disagreement E3 (notice the draft
moved) exists to catch, and E1 must not introduce it.

`_tokenize_item()` (`chitragupta/retrieval.py:186`, document indexing)
and `chitragupta.enrich.embed_index.search()` (dense retrieval) are
**not** in this list. The first is the symmetric change the roadmap
explicitly declines -- it would move every document's term frequencies,
every IDF, and would need `_INDEX_SCHEMA_VERSION` bumped for zero
measured gain. The second is out of scope on the roadmap's own evidence:
"This is a BM25 property, not a dense one" (CORPUS-SEARCH.md) -- an
embedding encodes the whole query string, so an interrogative shifts the
vector slightly rather than winning a term-competition dense retrieval
doesn't run.

**Contract:** one new function, `_query_terms(query: str) -> list[str]`
in `chitragupta/retrieval.py`, is `_tokenize(query)` plus interrogatives
dropped. All three call sites above switch to it. `_tokenize` itself,
`_STOPWORDS`, `_tokenize_item`, and `_INDEX_SCHEMA_VERSION` are
untouched -- so this plan cannot move a single document's score for a
query it doesn't itself receive differently.

## 🧮 Candidates considered for a stopword package

Issue #453 asked to use an existing Python package for this if one
offers a real benefit, rather than hand-rolling. Four were checked:

| Candidate | What it ships | Why it doesn't fit here |
| --- | --- | --- |
| [`stop-words`](https://pypi.org/project/stop-words/) (PyPI) | pure-Python, MIT, zero dependencies, one generic ~150-word English list per language | Lightest option by far, but its list is *generic stopwords*, not an interrogatives-only set -- using it whole is a broader, unmeasured intervention than the one the recall table proves inert; using only its wh-word/auxiliary subset means hand-picking the same ~17 words this plan writes directly, for the cost of a new dependency and an indirection |
| `nltk.corpus.stopwords` | requires `nltk.download("stopwords")` at run/build time, plus nltk's own dependency chain (click, joblib, regex, tqdm) | Runtime data download is incompatible with `python -m chitragupta.draft gate` running "with the bare system interpreter, no venv at all" (pyproject.toml); four new transitive dependencies for a ~150-word list |
| `spacy.lang.en.stop_words.STOP_WORDS` | a frozenset, but reachable only by installing spaCy | spaCy pulls thinc, numpy, murmurhash, cymem, preshed -- constraint 3 ("anything with a torch/transformers-shaped dependency goes behind an extra") reads directly on this, and `retrieval.py` is core, not `enrich` |
| `sklearn.feature_extraction.text.ENGLISH_STOP_WORDS` | a frozenset, but reachable only by installing scikit-learn | same shape of problem: numpy/scipy for one frozenset |

**None offers a real benefit over writing the set directly.** Every
candidate's list is *general* stopwords (articles, prepositions,
pronouns, quantifiers) with the interrogatives mixed in, not an
interrogatives-only list -- so getting just the interrogative subset out
of any of them still means hand-selecting the same words this plan
writes as `_INTERROGATIVES` below. The only thing a dependency would buy
is an indirection, at the cost of breaking `pyproject.toml`'s stated
invariant that `bibtexparser` is the one dependency the core pipeline
needs (`retrieval.py` currently has zero third-party imports and sits on
that always-active path, never behind `enrich`). And per the table
above, the interrogative set is closed-class English function words --
`what`/`why`/`how`/`who`/`whom`/`whose`/`which`/`when`/`where`/`can`/
`could`/`would`/`should`/`will`/`shall`/`does`/`did` -- that do not
drift the way a corpus-derived list would, so there is nothing here a
package would keep more current than a hand-maintained set already is.
**Decision: no new dependency.** `_INTERROGATIVES` is a literal set in
`chitragupta/retrieval.py`, the same pattern `_STOPWORDS` already uses
four lines above it.

**Provenance of the set, stated plainly rather than implied: not a
published standard.** It comes from three inputs -- the five words
CORPUS-SEARCH.md's own recall-table examples name (`what`, `why`,
`does`, `who`, `can`), closure over the wh-word class, and a judgment
call to add modals and do-support (`could`, `would`, `should`, `will`,
`shall`, `did`) because they also open an academic question. Penn
Treebank's `WDT`/`WP`/`WP$`/`WRB` tags name exactly the wh-word class
and `MD` names the modals, if a reviewer wants a reference point, but
the set was hand-assembled from the measurement's own examples, not
derived from a tagger or a published list. One member is a judgment
call rather than a class consequence: `which` is `WDT` but is also an
ordinary relative pronoun in academic prose ("the model, which we
calibrate"). Including it is defensible -- this only ever touches a
query string, never document text -- but it is a choice, not a
mechanical one.

**Not a new idea in this codebase, either.** `chitragupta/overlap_skipgram.py`'s
own `STOPWORDS` (~100 words, a different list for a different,
deliberately broader-tolerance purpose -- see the consolidation section
below for why it isn't shared) already includes `what`, `which`, `who`
and `whom`. Interrogative-stripping has precedent in a sibling module;
E1 is the first time it reaches the BM25 retrieval path specifically.

**Why this plan does not also build corpus-derived generic-vocabulary
detection.** `_bm25_scores` already computes document frequency over
every parsed paper, so a near-universal term (`study`, `approach`,
`results`) gets a low IDF and is self-neutralized in ranking by
construction -- no stopword entry needed, which is the actual reason the
19-word `_STOPWORDS` list has stayed that small. A stopword list only
earns its keep for the opposite case: a term that is *rare* in the
corpus (high IDF, competes hard) but carries no topical meaning --
interrogatives are exactly that, and it is why E1 targets them
specifically rather than "strip more generic words." A systematic sweep
for other such rare-but-non-topical terms (dumping the real corpus's
document-frequency distribution and inspecting the high-IDF tail) is a
real, separate measurement in `bench_retrieval_keyword_selfretrieval.py`'s
own style, with its own recall table -- not something to fold into E1,
whose whole safety guarantee is the "+0.000, provably inert" row
measured against this exact 17-word set. A broader, corpus-derived list
would be a different, unmeasured intervention.

If this project later wants non-English interrogative stripping --
issue #108, "a non-English corpus silently breaks retrieval," is the
relevant open item, not this one -- that is the point at which a
multi-language package's *cost* would be worth re-weighing against a
hand-maintained set per language, out of scope here since `_tokenize`'s
own `[a-z0-9]+` regex is English/ASCII-only today regardless of what
strips interrogatives.

## 🛠 The change, drawn

```text
chitragupta/retrieval.py
├── _INTERROGATIVES              new: the closed set above
├── _query_terms(query)          new: _tokenize(query) minus _INTERROGATIVES
├── _CITATION_MARKER             new: compiled regex, numeric bracket markers only
├── _clean_window(text)          new: whitespace-join + marker-strip, replaces two inline call sites
├── _windows()                   modified: last line calls _clean_window instead of inlining it
├── _snippet()                   modified: fallback line calls _clean_window instead of inlining it
└── search()                     modified: `terms = _tokenize(query)` -> `terms = _query_terms(query)`

chitragupta/retrieval_cli.py
├── import                       `_tokenize` import replaced by `_query_terms`
└── evidence()                   modified: `terms = set(_tokenize(query))` -> `terms = set(_query_terms(query))`

chitragupta/dossier/_drift.py
└── DriftIndex.matches()         modified: `retrieval._tokenize(query)` -> `retrieval._query_terms(query)`

chitragupta/passages.py
├── _CORE_STOPWORDS              new: the 19-word core, moved out of retrieval.py
└── _STOPWORDS                   modified: now `_CORE_STOPWORDS | {18 extras}`
```

(The `passages.py`/`retrieval.py` consolidation is
[its own section](#-consolidating-the-stopword-core-with-passagespy)
above -- bundled into this PR, not part of issue #453.)

## 🧹 The citation-marker hygiene sub-item

Carried in the same issue on separate, measured grounds: 22.8% of
retrieved snippets (39 of 180 sampled) contain their own source's
citation markers (mostly `[12]`-style), and checked before claiming
more, zero have ever leaked into a real draft -- so this is context
hygiene, not a fabrication vector, and does not touch the gate. The idea
is OpenScholar's `remove_citations`; not its regex, which also does a
global `]` delete and would eat `[Figure 2]` and `[sic]` along with a
real marker.

`_windows()` and `_snippet()`'s no-anchor fallback are the two places
raw source text is cut into what a caller sees (`_snippet` calls
`_windows` for its own case; `evidence()` calls `_windows` directly for
its passages) -- one shared helper, `_clean_window`, covers both:

```python
_CITATION_MARKER = re.compile(r"\[\d+(?:\s*[,-]\s*\d+)*\]")


def _clean_window(text: str) -> str:
    """Whitespace-normalized `text` with the source's own numeric
    citation markers (`[12]`, `[3, 7]`) stripped -- only a bracketed run
    of digits/commas/hyphens qualifies, so `[Figure 2]` and `[sic]`
    survive."""
    return " ".join(_CITATION_MARKER.sub("", text).split())
```

`_windows()`'s return line becomes
`return [_clean_window(text[begin:end]) for begin, end in sorted(chosen)]`,
and `_snippet()`'s fallback becomes `return _clean_window(text[:window])`.

One measurable side effect to note in the PR, not fix: `retrieval_cli.py`'s
`_print_results` sums `len(result.snippet)` as the reported "characters
returned," which `dossier.log_retrieval` records into `retrieval.md` and
`retrieval_cost` reads back out. Stripping a marker shortens the snippet
by a few characters on the affected 22.8%, so a `retrieval_cost` reading
taken after this ships is not bit-for-bit comparable to one taken
before. That is the correct, smaller number, not a bug -- just worth one
sentence in the PR description so nobody chases a `bench/RESULTS.md`
delta that is this, not drift.

## 📏 The C2 line budget

`chitragupta/retrieval.py` is 225 code lines today (`scripts/code_standards.py`'s
count: non-blank, non-`#`-comment lines; docstrings count, `#` comments
don't) against the 250-line C2 limit, and is not currently a registered
offender. The additions above (`_INTERROGATIVES`, `_query_terms`,
`_CITATION_MARKER`, `_clean_window`, minus what the two inlined
`" ".join(...)` expressions they replace remove) come to +16 code
lines, landing at 241 -- under the limit, with a 9-line margin. Put any
rationale in `#` comments (free) rather than in docstrings (counted) to
keep that margin; if a later edit does tip it over 250, split the module
rather than adding it to `LEGACY_LONG_FILES` in
`tests/test_code_standards_scan.py` -- this module has been split once
already (#441) and DEVELOPER-AGENTS.md's "Module boundaries" is the
standing preference. `chitragupta/dossier/_drift.py` (230 code lines) and
`chitragupta/retrieval_cli.py` (184) each change by one line and are not
at risk.

Run `.venv-full/bin/python -m pytest tests/test_code_standards_scan.py -v`
after Task 1 below, before writing anything else, to confirm the budget
held.

## 🏗 Build order

Each task ends green and independently committable, per
DEVELOPER-AGENTS.md's small-increment, test-first convention.

### Task 1: `_query_terms()` and `_INTERROGATIVES`, in isolation

**Files:** modify `chitragupta/retrieval.py`; modify `tests/test_retrieval.py`.

- [ ] Write the failing tests, a new class in `tests/test_retrieval.py`
  right after `TestTokenize`:

  ```python
  class TestQueryTerms:
      def test_strips_wh_words_and_a_modal(self):
          assert retrieval._query_terms(
              "what are the failure modes of co-simulation"
          ) == ["failure", "modes", "simulation"]

      def test_strips_why_and_does(self):
          assert retrieval._query_terms("why does model calibration matter") == [
              "model",
              "calibration",
              "matter",
          ]

      def test_leaves_a_keyword_query_untouched(self):
          assert retrieval._query_terms(
              "digital twin structural health monitoring"
          ) == ["digital", "twin", "structural", "health", "monitoring"]

      def test_tokenize_itself_is_not_touched(self):
          """_query_terms must be additive over _tokenize, not a
          replacement for it -- document-side indexing calls _tokenize
          directly and must keep seeing interrogatives, or every
          document's IDF moves for a change the roadmap explicitly
          declined."""
          assert retrieval._tokenize("what why how") == ["what", "why", "how"]
  ```

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_retrieval.py::TestQueryTerms -v
  ```

  Expected: FAIL with `AttributeError: module 'chitragupta.retrieval'
  has no attribute '_query_terms'`.

- [ ] Implement, in `chitragupta/retrieval.py` directly below the
  `_STOPWORDS` block (before the BM25 constants):

  ```python
  # Question words and question-forming auxiliaries -- rare in academic
  # PDFs, so they carry high IDF and out-compete the terms a question is
  # actually about. Query-side only: see _query_terms below.
  # docs/CORPUS-SEARCH.md has the measurement.
  _INTERROGATIVES = {
      "what", "why", "how", "who", "whom", "whose", "which", "when",
      "where", "can", "could", "would", "should", "will", "shall",
      "does", "did",
  }


  def _query_terms(query: str) -> list[str]:
      """`_tokenize(query)` with interrogatives also dropped -- query-side
      only, so a document's own term frequencies and every IDF stay put."""
      return [w for w in _tokenize(query) if w not in _INTERROGATIVES]
  ```

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest \
    tests/test_retrieval.py::TestQueryTerms tests/test_retrieval.py::TestTokenize -v
  ```

  Expected: PASS, all 8.

- [ ] Run: `.venv-full/bin/python -m pytest tests/test_code_standards_scan.py -v`
  Expected: PASS (confirms the C2 budget above).

- [ ] Commit.

  ```bash
  git add chitragupta/retrieval.py tests/test_retrieval.py
  git commit -m "retrieval: add _query_terms, a query-side interrogative filter"
  ```

### Task 2: wire `_query_terms()` into `search()`

**Files:** modify `chitragupta/retrieval.py:244`; modify `tests/test_retrieval.py`.

- [ ] Write the failing test, in `TestSearch`:

  ```python
  def test_a_question_and_its_keyword_form_rank_the_same(self, ledger_con):
      ledger.upsert_reference(
          ledger_con, make_reference(citekey="a2024", title="Structural Health Monitoring")
      )
      ledger.upsert_reference(
          ledger_con, make_reference(citekey="b2024", title="Unrelated Paper About Cats")
      )
      keyword_hits = [r.citekey for r in retrieval.search("structural health monitoring")]
      question_hits = [
          r.citekey for r in retrieval.search("what is structural health monitoring")
      ]
      assert keyword_hits == question_hits == ["a2024"]
  ```

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest \
    tests/test_retrieval.py::TestSearch::test_a_question_and_its_keyword_form_rank_the_same -v
  ```

  Expected: FAIL -- `what` survives into `question_hits`' term set and,
  depending on corpus contents, either still passes (if `what` doesn't
  shift the ranking here) or the assertion on
  `keyword_hits == question_hits` is the one actually pinned; if the
  fixture above happens not to fail red before the fix, strengthen it
  by seeding a third title containing the literal word "what" so the
  interrogative's IDF becomes the deciding term -- the point is a red
  run before the change, not this exact fixture.

- [ ] Implement: in `chitragupta/retrieval.py::search()`, change

  ```python
  terms = _tokenize(query)
  ```

  to

  ```python
  terms = _query_terms(query)
  ```

- [ ] Run the same test. Expected: PASS.

- [ ] Run the full `TestSearch` and `TestIndexCaching` classes to
  confirm document-side scoring is unaffected:

  ```bash
  .venv-full/bin/python -m pytest \
    tests/test_retrieval.py::TestSearch tests/test_retrieval.py::TestIndexCaching -v
  ```

  Expected: PASS, all.

- [ ] Commit.

  ```bash
  git add chitragupta/retrieval.py tests/test_retrieval.py
  git commit -m "retrieval: search() strips interrogatives from the query"
  ```

### Task 3: wire `_query_terms()` into `evidence()` and `DriftIndex.matches()`

**Files:** modify `chitragupta/retrieval_cli.py:31,73`; modify
`chitragupta/dossier/_drift.py:138`; modify `tests/test_retrieval.py`;
modify `tests/test_dossier.py`.

- [ ] Write the failing test for `evidence()`, in `TestCli`:

  ```python
  def test_evidence_strips_interrogatives_from_the_query(self, ledger_con, tmp_path):
      self._seed(ledger_con, tmp_path)
      with_question = retrieval_cli.evidence("a2024", "what are architecture patterns")
      without_question = retrieval_cli.evidence("a2024", "architecture patterns")
      assert with_question == without_question
  ```

- [ ] Write the failing test for `DriftIndex.matches()`, in
  `tests/test_dossier.py::TestDrift` (mirrors
  `test_a_new_paper_matching_a_recorded_query_is_a_candidate`, changing
  only the recorded query text):

  ```python
  def test_a_recorded_question_form_query_finds_what_search_would(self, draft):
      """DriftIndex.matches() replays a recorded query outside search()
      -- it must strip interrogatives the same way search() does, or
      drift reporting silently disagrees with what search() itself
      would return for the same human-typed query."""
      dossier.init(draft, "survey")
      target = dossier.dossier_dir(draft)
      (target / "evidence.md").write_text(
          "# Kept evidence\n\n## `kept_paper_2024`\n\nWhy kept.\n"
      )
      (target / "sections.md").write_text(
          "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
          "| 1. First | `kept_paper_2024` |\n"
      )
      dossier.log_retrieval(draft, "search", "what is digital twin", 15, 15, 2400)
      _seed_corpus(
          [
              ("kept_paper_2024", "Kept", "digital twin architecture"),
              ("fresh_twin_2026", "A fresh twin paper", "digital twin co-simulation study"),
          ]
      )
      report = _drift.drift(target)
      assert [c.citekey for c in report.candidates] == ["fresh_twin_2026"]
  ```

- [ ] Run both new tests. Expected: FAIL (or pass vacuously if the
  fixture doesn't force a divergence -- if so, strengthen the same way
  as Task 2's test, by seeding content where the literal interrogative
  is the deciding term).

- [ ] Implement, in `chitragupta/retrieval_cli.py`:

  ```python
  from chitragupta.retrieval import SearchResult, _full_text, _query_terms, _windows, search
  ```

  (replaces the `_tokenize` import), and in `evidence()`:

  ```python
  terms = set(_query_terms(query))
  ```

- [ ] Implement, in `chitragupta/dossier/_drift.py::DriftIndex.matches()`:

  ```python
  terms = retrieval._query_terms(query)
  ```

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest \
    tests/test_retrieval.py::TestCli tests/test_dossier.py::TestDrift -v
  ```

  Expected: PASS, all.

- [ ] Commit.

  ```bash
  git add chitragupta/retrieval_cli.py chitragupta/dossier/_drift.py tests/test_retrieval.py tests/test_dossier.py
  git commit -m "retrieval_cli, dossier/_drift: strip interrogatives from a replayed or looked-up query too"
  ```

### Task 4: citation-marker hygiene (`_clean_window`)

**Files:** modify `chitragupta/retrieval.py`; modify `tests/test_retrieval.py`.

- [ ] Write the failing tests, in `TestWindows` and `TestSnippet`:

  ```python
  # in TestWindows
  def test_strips_a_numeric_citation_marker(self):
      text = "the result [12] shows a clear trend in the data"
      windows = retrieval._windows(text, {"result", "trend"}, width=50, count=1)
      assert "[12]" not in windows[0]
      assert "result" in windows[0] and "trend" in windows[0]

  def test_does_not_strip_a_non_numeric_bracket(self):
      text = "the result [Figure 2] shows a clear trend in the data here"
      windows = retrieval._windows(text, {"result", "trend"}, width=50, count=1)
      assert "[Figure 2]" in windows[0]

  # in TestSnippet
  def test_fallback_snippet_also_strips_a_citation_marker(self):
      text = "no query terms appear here [3, 7] at all, just filler " + "x" * 100
      snippet = retrieval._snippet(text, {"nonexistentterm"}, window=40)
      assert "[3, 7]" not in snippet
  ```

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest \
    tests/test_retrieval.py::TestWindows tests/test_retrieval.py::TestSnippet -v
  ```

  Expected: 3 new FAIL, existing ones still PASS.

- [ ] Implement, in `chitragupta/retrieval.py` directly above `_windows()`:

  ```python
  # Bracketed digits/commas/hyphens only, so a real citation marker
  # ([12], [3, 7], [12-14]) is stripped and [Figure 2] / [sic] survive.
  # 22.8% of retrieved snippets carry one of the corpus's own markers
  # and nothing downstream ever needs it -- OpenScholar's
  # remove_citations is the idea; not its regex, which also globally
  # deletes every ']'.
  _CITATION_MARKER = re.compile(r"\[\d+(?:\s*[,-]\s*\d+)*\]")


  def _clean_window(text: str) -> str:
      """Whitespace-normalized `text` with a numeric citation marker
      stripped."""
      return " ".join(_CITATION_MARKER.sub("", text).split())
  ```

  Then change `_windows()`'s return line to:

  ```python
  return [_clean_window(text[begin:end]) for begin, end in sorted(chosen)]
  ```

  and `_snippet()`'s fallback line to:

  ```python
  return _clean_window(text[:window])
  ```

- [ ] Run: `.venv-full/bin/python -m pytest tests/test_retrieval.py -v`
  Expected: PASS, all.

- [ ] Run: `.venv-full/bin/python -m pytest tests/test_code_standards_scan.py -v`
  Expected: PASS (final confirmation of the 241-code-line estimate above).

- [ ] Commit.

  ```bash
  git add chitragupta/retrieval.py tests/test_retrieval.py
  git commit -m "retrieval: strip a source's own citation markers from returned windows"
  ```

### Task 5: extend the bench script, don't add one

**Files:** modify `bench/bench_retrieval_keyword_selfretrieval.py`.

`bench/`'s convention (`plans/356-bench-self-check-convention.md`) is
that a script publishing a number fabricates a difference and asserts it
sees it, and a new `bench/*.py` file reddens the test that counts them
-- this extends the existing keyword self-retrieval script rather than
adding one.

- [ ] Add a `wrapped_and_stripped_rows(ground_truth)` function beside
  `bm25_row()` that runs three more query forms per ground-truth row --
  wrapped as a question (`f"what is {row['query']}"`), that question with
  `_query_terms` applied, and the bare keyword query with `_query_terms`
  applied -- and returns four `score_keyword_rows(...)`-shaped dicts
  labelled to match the table in
  [What was measured](#-what-was-measured-and-what-it-does-not-license)
  above.

- [ ] Extend `self_check()` to prove the stripping actually changes
  something, not just that it runs -- assert the wrapped-question row's
  `recall@{K_REPORT}` is strictly less than the baseline row's, and that
  the stripped-keyword row's is *equal* to the baseline row's (the
  +0.000 property), against a small in-process fixture rather than the
  full 208-row corpus, so the check stays cheap.

- [ ] Run the extended script against the real corpus (needs
  `CONTENT_DIR=/workspace/content` and `.venv-full`) and record the
  output under `bench/results/<tag>/`, tagged
  `2026-08-29-retrieval-interrogative-strip` or the actual run date.

  ```bash
  CONTENT_DIR=/workspace/content .venv-full/bin/python \
    bench/bench_retrieval_keyword_selfretrieval.py --tag 2026-08-29-retrieval-interrogative-strip
  ```

- [ ] Add the four-row table (with the real, current-corpus numbers,
  not the ones quoted above from CORPUS-SEARCH.md's already-published
  measurement) to `bench/RESULTS.md`, in B4's table shape (#380), and
  state explicitly in the same entry: templates are synthetic and no
  claim-form regression was run -- carrying the "what this plan still
  owes" note forward as a recorded gap, not a silent omission.

- [ ] Commit.

  ```bash
  git add bench/bench_retrieval_keyword_selfretrieval.py bench/results bench/RESULTS.md
  git commit -m "bench: extend keyword self-retrieval with the interrogative-stripping rows"
  ```

### Task 6: consolidate the stopword core with `passages.py`

**Files:** modify `chitragupta/passages.py`, `chitragupta/retrieval.py`,
`code-standards-register.toml`, `docs/CODE-STANDARDS.md`,
`docs/TECHNICAL-DEBT.md`.

- [ ] Run the existing passage tests first, to have a known-green
  baseline for a change with no new test of its own (this is a pure
  dedup; `distinctive()`'s behavior must not move at all):

  ```bash
  .venv-full/bin/python -m pytest tests/test_passages.py tests/test_retrieval.py::TestTokenize -v
  ```

  Expected: PASS (this is the baseline, not a red-first step -- there is
  no new behavior to pin, only old behavior to preserve).

- [ ] In `chitragupta/passages.py`, replace the flat `_STOPWORDS` set
  literal with:

  ```python
  _CORE_STOPWORDS = {
      "a", "an", "the", "of", "on", "in", "for", "and", "to", "with",
      "is", "are", "be", "this", "that", "as", "by", "from", "at",
  }

  # Shared with chitragupta/retrieval.py, which imports _CORE_STOPWORDS
  # from here (this module has no drafting-layer dependents, so this is
  # the direction that keeps the corpus/enrichment/review layers
  # independent of drafting). Editing this constant moves retrieval.py's
  # BM25 index too and needs _INDEX_SCHEMA_VERSION bumped there --
  # passages.py's own extras just below are free to change on their own.
  _STOPWORDS = _CORE_STOPWORDS | {
      "it", "its", "can", "has", "have", "was", "were", "which", "such",
      "these", "those", "their", "than", "then", "but", "not", "also",
  }
  ```

- [ ] In `chitragupta/retrieval.py`, delete the local `_STOPWORDS` set
  literal entirely and add, alongside the existing `from chitragupta
  import bib_collections, ledger, retrieval_cache` line:

  ```python
  from chitragupta.passages import _CORE_STOPWORDS as _STOPWORDS
  ```

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_passages.py tests/test_retrieval.py -v
  ```

  Expected: PASS, all -- identical content through a different source,
  so nothing about `_tokenize`'s or `distinctive()`'s output changes.

- [ ] Delete `chitragupta/passages.py`'s entry from
  `code-standards-register.toml`'s `[[c2]]` table (the module is now
  under 250 code lines). Confirm the exact new count before editing the
  docs below:

  ```bash
  .venv-full/bin/python -c "
  from scripts.code_standards import code_lines
  print(code_lines(open('chitragupta/passages.py', encoding='utf-8').read()))
  "
  ```

- [ ] In `docs/CODE-STANDARDS.md` (around line 298) and
  `docs/TECHNICAL-DEBT.md` (around line 101), change "**7 modules**" to
  "**6 modules**" in both places -- leave "**3 functions**" untouched,
  the C1 register is unaffected.

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_code_standards_scan.py tests/test_technical_debt_scan.py -v
  ```

  Expected: PASS, all -- confirms the register, its recorded count, and
  both docs' stated sizes agree.

- [ ] Commit.

  ```bash
  git add chitragupta/passages.py chitragupta/retrieval.py \
    code-standards-register.toml docs/CODE-STANDARDS.md docs/TECHNICAL-DEBT.md
  git commit -m "passages, retrieval: share the 19-word stopword core instead of duplicating it"
  ```

## 📚 Docs and roadmap sweep

**Files:** modify `docs/CORPUS-SEARCH.md`, `docs/RAG.md`,
`docs/FEATURE-ROADMAP.md`.

- [ ] `docs/CORPUS-SEARCH.md`, directly after the sentence ending "...
  compete for the ranking against the terms you meant" (the paragraph
  right after the `_tokenize` illustration): add a sentence naming the
  fix and clarifying the illustration's scope, since `_tokenize` itself
  is deliberately unchanged --

  > **Fixed query-side, in `_query_terms()` (`chitragupta/retrieval.py`).**
  > `_tokenize` above is unchanged -- a symmetric fix would re-rank every
  > query in the corpus for no further gain, so `_INDEX_SCHEMA_VERSION`
  > and every document's term frequencies stay exactly as they were.
  > `search()`, `evidence()`, and `dossier/_drift.py`'s replay of a
  > recorded query all call `_query_terms()` instead: `_tokenize()` plus
  > a small, hand-maintained set of wh-words and question auxiliaries.
  > The illustration above still describes `_tokenize()` exactly; it is
  > `_query_terms()`, not `_tokenize()`, that a real query is scored
  > against.

  Then, in the "Three things follow" list further down, change "So
  `plans/outline-driven-drafting-and-manual-edits.md`'s proposal to
  strip interrogatives is worth doing and is **not** a licence to write
  queries as questions" to "So stripping interrogatives (shipped, above)
  was worth doing and is **not** a licence to write queries as
  questions" -- the rest of that sentence and "Keywords remain the
  advice" stand unchanged, because the fix is partial and the advice it
  supports does not change.

- [ ] `docs/RAG.md`, in "One measured hazard belongs here": change "BM25
  over whitespace tokens with a 20-word stopword list containing **no
  interrogatives** scores `what`, `why` and `does` as ordinary terms" to
  "BM25 over whitespace tokens used to score `what`, `why` and `does` as
  ordinary terms when a query was phrased as a question -- fixed
  query-side (`chitragupta/retrieval.py::_query_terms()`), leaving the
  shared tokenizer and its stopword list alone." The recall-table
  paragraph that follows stays as the historical measurement backing the
  fix.

- [ ] `docs/FEATURE-ROADMAP.md`: per this repo's convention for a
  shipped item (twelve prior items "removed from this document rather
  than marked" -- what they became is described in FEATURES.md instead),
  delete:
  - The whole `### ❓ E1: strip interrogatives on the query side`
    section.
  - The build-order table row:

    ```text
    | 1 | [E1](#-e1-strip-interrogatives-on-the-query-side) strip interrogatives | E | S | -- |
    ```

    Leave E2's row's "Depends on: E1" cell as plain text unchanged --
    that already matches how a shipped dependency reads elsewhere in the
    same table (B4's row still says "Depends on: B1" though B1 has no
    row of its own).
  - The rationale paragraph beginning "**E1 leads because it is cheap,
    measured, and a prerequisite that gets more expensive to add
    later**" -- it argues for E1's position in the table, which no
    longer exists.
  - `docs/FEATURES.md` does **not** need a new row: this is an internal
    quality fix to the existing `draft retrieve` / `BM25 search` entry,
    not a new command or capability, matching how B3 (section thesis)
    and similar internal-only roadmap items landed without one.

## ✅ Verification

Before calling E1 done, per DEVELOPER-AGENTS.md's "Before claiming a
task complete":

```bash
.venv-full/bin/python -m pytest --cov --cov-report=term-missing
pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks
ruff check chitragupta scripts .claude/hooks
ruff format --check chitragupta scripts tests bench .claude/hooks
markdownlint-cli2 "*.md" "docs/**/*.md" ".claude/**/*.md" "plans/**/*.md"
poetry check
```

Plus one real smoke test beyond the unit suite: run `python -m
chitragupta.draft retrieve "what is <a real keyword from the corpus>"`
against the real ledger and confirm the top hits match what the same
query with the interrogative removed returns, and that a snippet
containing a known `[N]`-style marker in a real parsed PDF comes back
without it.

**Record the outcome.** When this merges, add a line at the top of this
file saying which PR closed it and what, if anything, changed from this
plan on the way -- this directory's one contract (plans/README.md).
