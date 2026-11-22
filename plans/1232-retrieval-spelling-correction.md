# 1232: opt-in, announced spelling correction for retrieval queries

Status: **design approved, not built.** Written 2026-11-21, for
[issue 1232](https://github.com/prasadtalasila/chitragupta/issues/1232).

**Written for** whoever builds #1232. **Assumed:** #789's acronym
expansion (`chitragupta/retrieval_expansion.py`) and #953's single
`retrieval.query_terms()` pipeline, both of which this follows rather
than re-argues. **Not covered here:** turning the default on (the issue
rejects that until a bench run supports it, and it would need a plan for
existing drift baselines); document-side correction; any change to how
citekeys are handled.

## Why

BM25 matches words exactly. A query word the corpus has never seen
scores zero for every paper, and nothing tells the user it was ignored,
so a typo such as `strucutral` silently returns nothing or the wrong
snippets. The only warning today, `short_query_terms`, covers
one-character words.

## Goals, non-goals, anti-goals

**Goals.** When `[retrieval].spelling_correction` is on, a typed query
word the corpus has never seen gains at most one corpus word as an
*added* term. The CLI announces the addition, `--log` records it, and
every path that ranks or windows a query uses it.

**Non-goals.** Correcting words the corpus already contains. Correcting
draft prose. Context-aware correction: "aeing" is one slip from both
"ageing" and "being", and no method here will tell them apart.

**Anti-goals.** These would make the feature a failure even if it worked:

- A correction that *replaces* the typed word. A genuine domain term the
  corpus lacks must still be searched as typed.
- Any change to ranking when the setting is off.
- Touching a citekey, `--citekey`, or the gate. SOUL.md's one invariant
  applies; this is free-text query words only.
- A correction the user cannot see.

## Constraints

- **Tier 1: stdlib only.** A direct one-slip lookup; no `difflib`, no
  `rapidfuzz`. The spike below shows neither is needed.
- **C2, 250 code lines per module** (`scripts/code_standards.py`).
  `retrieval.py` is at 249, `retrieval_cli.py` at 250, `config.py` at
  247 and `discover/__init__.py` at 245. New logic goes in the new
  module. **A file that this work pushes over 250 is refactored**:
  split along an existing seam into a sibling module, as the
  `retrieval_*` modules were. It is not squeezed back under by
  contortion, and it is not added to the code-standards register. The
  owner decided this.
- **No circular import.** `retrieval.py` imports the new module, so the
  new module cannot import `retrieval`. Pass functions in, the way
  `retrieval_expansion.expand(typed, _tokenize)` and
  `retrieval_cache._load_index(items, tokenize_item)` already do.
- **`retrieval_expansion.py` cannot host this.** Its docstring forbids it
  from reading an index or growing a second vocabulary source.
- **Line and branch coverage stay at 100%.** No fabricated citekeys in
  test fixtures: reuse the fixture corpus the retrieval tests already use.

## Approaches considered

Where `query_terms()` gets the corpus vocabulary, given that it runs
before any index is loaded and takes only the query string:

1. **Build it on demand from the document BM25 index.** *Chosen.* One
   vocabulary for every caller (document search, passage search,
   `evidence` windows, the CLI note, drift), so the note always matches
   what was ranked, which is the property #953 restored for acronyms. It
   costs nothing when off and about 0.2 s once per process when on.
2. **Write a vocabulary file next to the BM25 cache.** Fastest per query,
   but it is one more file to invalidate, and it is stale until the
   first search after a sync. Kept as the fallback if (1) proves slow on
   a much larger corpus. The switch would stay inside the new module.
3. **Have callers pass their index in.** Rejected. The CLI note and
   `evidence` have no index, and passage search has a different one, so
   corrections would differ between units and the note could describe
   something that was never ranked (#953 again).

## The design

### Setting

- `[retrieval].spelling_correction`, boolean, **default `false`**.
- In `config.py`: `SPELLING_CORRECTION = _get_bool("RETRIEVAL_SPELLING_CORRECTION",
  "retrieval", "spelling_correction", default=False)`. This brings
  `config.py` to exactly 250 lines.
- Documented in `config.toml.example` next to `acronym_expansion`, and in
  `docs/CONFIG.md` and `docs/RETRIEVAL.md`. The comment says that
  switching it on re-baselines drift (see below), and points at the
  bench result.

### Off is structural

With the setting off, the correction function returns `[]` before it
loads anything, exactly as `retrieval_expansion.expand` does. `query_terms`
output is then byte-identical to today, by construction rather than by
test, though a test should also pin it.

### Which words are corrected

A typed term (the output of `_query_terms`, before acronym expansion) is
a correction candidate only if all of these hold:

1. it appears in **no** paper's `term_freqs` (rule 1 of the issue: a
   word in even one paper is never touched);
2. it is at least **5 characters** long;
3. it is all letters. A token with a digit (`iso23247`, `10000`) is
   never corrected: a neighbouring number is never what was meant.
   A fragment from a non-ASCII word (`Schrödinger` tokenizes to
   `schr`, `dinger`) is accepted and pinned by a test.

### How a correction is chosen

Settled by the spike below, not guessed:

1. **Candidate pool:** all-letter corpus words that appear in **at least
   2 papers**, minus `retrieval._INTERROGATIVES` (passed in): those are
   in the document index but dropped from queries on purpose, and a
   correction must not add one back.
   56% of the vocabulary appears in only one paper, and that tail is
   mostly OCR noise (`architecutre`). Excluding it as a *target* never
   affects rule 1, which still checks the full vocabulary.
2. Generate every string **one slip** from the typed word: one letter
   deleted, one adjacent pair swapped, one letter replaced or one
   inserted, over `a`-`z`. That is about 54n + 25 strings for an
   n-letter word. Keep those in the pool.
3. Among those, the candidate in the **most papers** wins. A remaining
   tie goes to the alphabetically first, for determinism.
4. No candidate left means no correction.

This replaced an approved `difflib.get_close_matches(n=5, cutoff=0.80)`
stage after review: every one-slip neighbour of a 5+-letter word
already scores at least 0.80, so `difflib` only truncated the list to
five, which could drop the right answer. The direct lookup gives the
same accuracy at under 1 ms per word (table below).

At most one added word per typed word.

### Where the vocabulary comes from

The union of `term_freqs` keys over the document index, with the paper
count per word, taken from the same parsed-only rows `search` ranks
(`status == PARSED`, #1118), so the vocabulary is exactly what the
ranker sees. Memoize it on the ledger's
`(path, size, mtime_ns)` and the BM25 cache file's `mtime_ns`, the way
`_json_cache.MemoisedJson` stamps its path. A sync, a cache rewrite or a
different test tree then invalidates it, which matters for the
long-lived discover web app as much as for tests.

**Built read-only. It never writes the BM25 cache.** `retrieval_cache._load_index`
saves the cache whenever a fingerprint moved, which after a sync is
guaranteed. `dossier/_drift.py`'s `_ephemeral_index` exists because a
report must not "mutate the corpus layer it is inspecting", and drift
reaches this code through `query_terms`. So:

- Move `_ephemeral_index` from `dossier/_drift.py` into
  `retrieval_cache.py` (97 code lines, room to spare) as a shared
  read-only builder, taking `tokenize_item` as an argument for the
  usual circular-import reason. It seeds from the memoized `_load_cache()`
  where fingerprints match, tokenizes the rest in memory, and never saves.
- Drift and spelling correction both call it.
- It reads the ledger through `ledger.reading()`, which is
  `read_connection()` plus a close: no write lock, no migration, the
  same opener `search` uses.
- It keeps `_load_index`'s shape check (#504): a cached entry is reused
  only if `term_freqs` is a dict and `length` an int, so a malformed
  cache costs a re-tokenization, never a crash in `query_terms`.
- It holds a one-entry memo keyed on the rows' fingerprints, so drift
  and the vocabulary share one cold-cache tokenization per process
  rather than paying it twice.

This was settled in brainstorming after the builder check. The cost: on
a warm cache the build takes about 0.2 s. On a cold cache, meaning the
first process after a sync with correction on, it costs one extra
in-memory tokenization of the corpus. `search` then writes the cache as
it does today, so the next process is warm again. The bench should
record the cold-cache figure.

### Interaction with acronym expansion

Both read the *typed* terms only. A corrected word is never corrected
again and never acronym-expanded, and an acronym expansion is never
spelling-corrected. This is the issue's "never fed back through itself"
rule. A corrected word the user also typed elsewhere in the query is not
added twice, matching `expand`.

### Telling corrections from acronyms

`query_terms` returns `(terms, added)`. Today `added` is `(typed, term)`
pairs, and `announce`/`describe` label every pair as an acronym. Each
entry gains a source, `acronym` or `spelling`, so the note and the log
can tell them apart. The exact shape (a third tuple element or a small
named tuple) is the builder's call. Every caller of `query_terms` has to
keep working.

- **CLI note**, on stderr like the acronym note:
  `[note] spelling: searched 'structural' for 'strucutral'`. One note per
  correction or one line listing them all is the builder's call.
- **`--log` `expanded` column:** acronym entries render exactly as today
  (`DT -> digital twin`), so existing logs read the same. Spelling
  entries render as `strucutral ~> structural`, joined by a semicolon and a space.
  Nothing parses this column today; `_retrieval_queries.py` only reads
  it as a cell.
- Prefer keeping `retrieval_expansion.announce(query_terms(args.query)[1])`
  as the CLI's one call site, with `announce`/`describe` (or whatever
  replaces them) handling both sources. If `retrieval_cli.py` has to
  grow anyway, refactor it under the C2 rule above.

### Announced wherever a person reads the output

The owner chose this after the builder check found three more callers of
`retrieval.search()` that would otherwise correct silently, which is one
of the anti-goals:

- **`discover search`** (`discover/__init__.py:204`, `_search_view`)
  prints the same stderr note as `retrieve`. Stderr, because under
  `--json` stdout is the payload.
- **Citation coverage** (`review/citation_coverage.py:85`,
  `compute_coverage`) records the corrections each query received and
  shows them next to that query in both the Markdown report and the JSON
  envelope. The `corrections` key is omitted when empty, so the payload
  with the setting off is identical to today's.
- **The drift report** (`dossier status`) stays silent. This is
  documented beside the setting, because the owner decided drift follows
  the current setting.

`search()` returns results only, so these callers read the corrections
through `query_terms(query)`, the same way `retrieval_cli` does (#953:
read the pairs that were actually ranked, never recompute them).

### Every path gets it for free

`search`, `retrieval_passages.search_passages`, `evidence` windows
(snippets anchor on the corrected word too, rule 2 of the issue) and
`dossier/_drift.py` all go through `query_terms`, so their ranking needs
no edits. Only the announcements above do, plus drift's move to the
shared read-only builder.

- **Drift follows the current setting.** Decided by the owner. Switching
  correction on means the next `dossier status` re-ranks every recorded
  query with it on, and a dossier whose queries held a typo can show
  drift. Document this beside the setting. No replay of what was logged.
- **`--y-prev`'s appended prose** goes through `query_terms` too, so
  prose words unseen in the corpus can be corrected without a note. This
  is the same exception acronyms already have, documented in the comment
  above `query_terms`. Accept it and extend that comment. The bench
  should record how many corrections a typical `--y-prev` round adds.
- **`retrieval_iterative.py` and `discover/_resolve.py`** call the private
  `_query_terms` and get neither expansion nor correction. Leave them.

## Spike results (2026-11-21, throwaway, not committed)

These came from this host's corpus: 497 parsed papers, 69,454 distinct
words, 964 distinct logged queries, and 5,559 synthetic typos (one swap,
deletion, substitution and insertion each) of every 5+-letter query word.

| Method | Right when it corrects | Typos fixed | Time per word |
| --- | --- | --- | --- |
| difflib n=1, cutoff 0.85, all words | 88.9% | 79.8% | 42 ms |
| same, candidates in ≥2 papers | 92.3% | 80.5% | 18 ms |
| n=5, cutoff 0.80, ≥2 papers, one slip, most papers | 95.7% | 94.3% | 24 ms |
| **direct one-slip lookup, ≥2 papers, most papers** | **95.7%** | **94.3%** | **< 1 ms** |

Building the vocabulary from the cache JSON took 0.19 s. Most of the
remaining wrong corrections sit one slip from two real words ("aeing"
could be "ageing" or "being"), and only context could resolve them.

In the real query logs there were **zero genuine typos**. The 5 words the
corpus had never seen were all valid: `disagrees` gained `disagree`
(useful), `tumbling` gained `stumbling` (wrong, but announced and
harmless because the typed word stays), and `gluing`, `modeldescription`
and `rebuildable` were left alone. Agent-written queries rarely contain
typos, so the feature mainly serves people typing queries by hand. This
is one more reason it ships off.

## Bench (the issue's checklist item)

`bench/bench_retrieval_spelling.py`, through the real `chitragupta` code
rather than a re-implementation, with results under
`bench/results/<date>-spelling-correction/`, following
`bench_retrieval_acronym_expansion.py`. The owner confirmed all three
arms. Only arm 2 is the issue's own requirement:

1. **Correction accuracy and timing.** The synthetic-typo set above:
   right, wrong and none. Typos that are themselves corpus words (blocked
   by rule 1) and typos under 5 characters stay in the denominator as
   their own buckets, not silently dropped. Report time per word next to
   the pool size, with cold- and warm-cache vocabulary builds separately.
2. **On vs off ranking (harm check).** The logged queries with the
   setting off and on. They hold no genuine typos, so this arm measures
   harm only, and is labelled that way. Report which queries moved.
3. **Recovery.** Self-retrieval queries with one typo injected into a
   5+-letter word (`random.Random(1232)`): recall@1/@5 and MRR off vs on,
   overall *and* on the affected queries alone, because the untouched
   words dilute the overall figure.

Every arm flips `config.SPELLING_CORRECTION` in one process, holds acronym
expansion fixed, and builds through the read-only builder, so the bench
never writes the cache.

## Left to the builder

- The module name (`retrieval_spelling.py` is the working name) and how
  it shares `announce`/`describe` with `retrieval_expansion.py`.
- The shape of the source tag on `added` entries.
- How the in-memory vocabulary is cached and reset for tests.
- Note wording, within the forms above.
- Where to split a file that goes over 250 lines, provided the split
  follows an existing seam.
