# E4: the draft is the query

Status: **planned**, not yet built. This file is the plan; no PR closes
it yet.

Written 2026-08-30, for
[issue #456](https://github.com/prasadtalasila/chitragupta/issues/456) --
E4 in [docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md), Theme E.
Task 5 of this plan removes E4's own heading from that file once it
ships (this repo's convention for a shipped item -- see that file's own
opening paragraph), so this plan does not link to it by anchor.

**Written for** whoever builds E4. **Assumed:** the ITER-RETGEN
background and the three measured requirements this plan's own commit
history removes from `docs/FEATURE-ROADMAP.md` on the way (recorded
here instead, in "What this closes" below) and
[docs/RAG.md](../docs/RAG.md#-stage-4-query-manufacture-the-stage-most-systems-skip)
(iteration-2 recall gain, FlashRAG's uncapped-merge bug, the
bag-of-words-swamping argument for bounding appended prose) -- this plan
does not re-derive them, only implements what they already argue for.
**Not covered here:** any change to the *corpus*-drift re-grounding flow
("Re-grounding after the corpus moves" in `.claude/skills/draft-reviser/SKILL.md`,
R1-R5) -- that is a different mechanism (recorded queries replayed
against a grown ledger) this plan does not touch; and any change to the
four other genre skills or `corpus-reviser`, which do not reference the
draft fingerprint at all and are out of scope unless a later item
extends this mechanism there. **Also not a trigger, stated explicitly
because it is easy to expect otherwise:** editing `outline.md`'s
`queries:` for a section, on its own, with the draft untouched. The
fingerprint digests the draft only, so that edit produces no `CHANGED`
and step 1 makes no offer -- it surfaces only through the existing
`declared_vs_actual` path (the new query text matches no `retrieval.md`
row and reads as `not_run`). `outline.md` is read live on every call
(`declared_vs_actual`'s `parse(path.read_text(...))`), never cached, so
there is no version of it to go stale -- "the section's declared query"
always means whatever `outline.md` currently says, composed with
whatever the draft currently says. The two are different fields, not
competing versions of one field, so nothing here needs a precedence
rule.

This plan shares Theme E with
[outline-driven-drafting-and-manual-edits.md](outline-driven-drafting-and-manual-edits.md)
(PR 1/E1, PR 2/E2, PR 3/E3) -- per that file's own "PR 3" section and
FEATURE-ROADMAP.md's own statement that E4 shares it. That file gets a
short recap section once this ships (Task 5 below); this file carries
the actual task-by-task build.

## 🧭 Table of contents

- [What this closes, and the shape it takes](#-what-this-closes-and-the-shape-it-takes)
- [Design decisions this plan makes explicit](#-design-decisions-this-plan-makes-explicit)
- [The change, drawn](#-the-change-drawn)
- [The C2 line budget](#-the-c2-line-budget)
- [Build order](#-build-order)
- [Docs and roadmap sweep](#-docs-and-roadmap-sweep)
- [Verification](#-verification)

## 🔁 What this closes, and the shape it takes

The draft fingerprint (#454/#462) says *that* a hand-edited section
moved. E4 uses *what* moved: once `dossier status` reports `CHANGED
since last stamp`, `draft-reviser` can carry that section's own new
prose into one extra retrieval round for that section -- ITER-RETGEN
(Shao et al., *Findings of EMNLP 2023*) with a person in the model's
`y_{t-1}` slot. Two rounds, never more; round 1 is the plain query,
round 2 appends the bounded prose; both rounds' results are merged by
citekey and capped back to the caller's `k`.

## 🧩 Design decisions this plan makes explicit

Three questions the roadmap entry and the issue text leave to the
implementer. Answered here, once, rather than left for Task 1-4 to
answer differently from each other.

**1. Where does the primitive live?** `chitragupta/retrieval.py` is at
233 of the 250 C2 code lines (docstrings count, comments don't) --
17 lines of headroom, not enough for a merge-then-cap function with this
project's documentation density. New module: `chitragupta/retrieval_iterative.py`,
composing over `chitragupta.retrieval.search()` rather than reimplementing
ranking. (See "The C2 line budget" below.)

**2. What happens when the query itself is empty or the y_prev
candidate is empty?** `search("")` already returns `[]` -- no terms,
nothing to rank. But `search_iterative("", "some prose")` must **not**
fall through to a round-2 search on the prose alone: that would be
prose-only retrieval with no sub-theme anchor, a different feature
nobody asked for. E4 is "declared query **plus** prose," not "prose
instead of a query." `search_iterative` therefore skips round 2 whenever
`query` itself tokenizes to no terms (`chitragupta.retrieval._query_terms`),
in addition to skipping it when the bounded `y_prev` is blank. Caught
during review of this plan, not after Task 1 shipped -- Task 1's test
suite includes the case (`test_empty_query_with_y_prev_still_returns_nothing`).

**3. Does a `reground`-origin call count toward `declared_vs_actual`'s
"run" set?** `tests/test_dossier_outline.py::test_an_unspecified_origin_call_is_neither_run_nor_actual`
exists specifically to stop `run` from silently widening ("would make
the diff always report compliance"). Adding `"reground"` to that set is
not the same widening that test guards against, and the argument has to
survive contact with a reviewer who remembers that test:

- An **unspecified** origin (`None`/empty, that test's actual subject)
  means a call that *never declared* which query it was running --
  admitting it into `run` would make every undeclared call read as
  compliant, which is the exact failure `origin` was invented to catch
  (#455).
- A **`reground`** call is the opposite case: it is logged with `query`
  equal to the section's own declared query text (Task 2's CLI shape
  logs the round-1 query, not the round-2 concatenation, as the row's
  `query` cell), and `origin="reground"` is a deliberate, explicit third
  state -- never a fallback default anything reaches by omission. The
  declared query genuinely did run; it ran with one extra round appended
  on top. Reporting it as `not_run` would be the dishonest reading, not
  the honest one -- the whole point of the `origin` column.
- `OutlineDrift.regrounded` (Task 3) keeps the distinction visible
  regardless: `run` says "the declared query executed," `regrounded`
  says "...and got an extra round." Neither list is dropped in favour of
  the other.

**One row per CLI invocation, stated plainly.** `search_iterative` runs
two BM25 searches internally, but `retrieve search --y-prev ... --log`
(Task 2) writes exactly **one** `retrieval.md` row -- `query` is the
original, undecorated query text; `k`/`results`/`chars` describe the
merged, capped output. `retrieval_cost`'s `calls` therefore counts CLI
invocations (what actually reached the caller's context, which is what
`--log`'s docstring says it measures), not the two searches a `--y-prev`
call ran underneath. This is a deliberate reading of an existing
contract, not a side effect discovered later.

## 🛠 The change, drawn

```text
chitragupta/retrieval_iterative.py         new module
├── Y_PREV_MAX_CHARS                       new: 1500, module constant
├── _bound_y_prev(y_prev, limit)           new: collapse + word-boundary truncate
└── search_iterative(query, y_prev, k, ...) new: two-round search, merge, cap

chitragupta/retrieval_cli.py
├── import                                 + retrieval_iterative
├── p_search.add_argument("--y-prev", ...)  new flag, search-only
├── --origin choices                       + "reground"
└── _run_search()                          modified: branches on args.y_prev

chitragupta/dossier/_outline.py
├── OutlineDrift.regrounded                new field
└── declared_vs_actual()                   modified: "reground" origin joins `run`; new `regrounded` list

chitragupta/dossier/_status.py
└── _print_status_outline()                modified: reports regrounded count + list

.claude/skills/draft-reviser/SKILL.md
├── step 1 (fingerprint branch)            + the reground offer
└── step 4 (search decision)               + the --y-prev invocation shape
```

## 📏 The C2 line budget

Current code-line counts (`scripts/code_standards.py`'s count --
docstrings count, `#` comments don't), measured before this plan's
changes:

| File | Code lines | Ceiling headroom |
| --- | --- | --- |
| `chitragupta/retrieval.py` | 233 | 17 -- not enough; stays untouched, per design decision 1 |
| `chitragupta/retrieval_cli.py` | 192 | 58 -- Task 2's addition (~20 lines) fits |
| `chitragupta/dossier/_outline.py` | 233 | 17 -- Task 3's addition (~6 lines) fits, checked explicitly in Task 3 |
| `chitragupta/dossier/_status.py` | 231 | 19 -- Task 3's addition (~5 lines) fits, checked explicitly in Task 3 |
| `chitragupta/retrieval_iterative.py` | 0 (new) | 250 -- new module, no register entry needed |

If Task 3's additions push either dossier file over 250, split following
the `_retrieval.py`/`_retrieval_queries.py` precedent (#467) rather than
shrinking a docstring to dodge it.

## 🏗 Build order

Each task ends green and independently committable, per
DEVELOPER-AGENTS.md's small-increment, test-first convention.

### Task 1: `search_iterative()`, the merge-then-cap primitive

**Files:** create `chitragupta/retrieval_iterative.py`; create
`tests/test_retrieval_iterative.py`.

- [ ] Write the failing tests:

  ```python
  """chitragupta/retrieval_iterative.py: ITER-RETGEN (Shao et al.,
  Findings of EMNLP 2023) with a human's own hand-edited prose standing
  in for the model generation the paper calls y_{t-1} --
  FEATURE-ROADMAP.md's E4."""

  from chitragupta import ledger, retrieval, retrieval_iterative

  from tests.conftest import make_reference


  class TestBoundYPrev:
      def test_short_text_is_returned_unchanged(self):
          bounded, truncated = retrieval_iterative._bound_y_prev("short prose")
          assert bounded == "short prose"
          assert truncated is False

      def test_long_text_is_cut_at_the_limit_on_a_word_boundary(self):
          text = "word " * 500  # 2500 chars, over the 1500 default
          bounded, truncated = retrieval_iterative._bound_y_prev(text)
          assert truncated is True
          assert len(bounded) <= retrieval_iterative.Y_PREV_MAX_CHARS
          assert bounded.endswith("word")

      def test_collapses_whitespace_before_measuring(self):
          bounded, truncated = retrieval_iterative._bound_y_prev("a\n\nb   c")
          assert bounded == "a b c"
          assert truncated is False

      def test_a_single_word_over_the_limit_still_returns_something(self):
          text = "x" * 2000
          bounded, truncated = retrieval_iterative._bound_y_prev(text, limit=100)
          assert truncated is True
          assert bounded

      def test_blank_text_is_not_truncated(self):
          bounded, truncated = retrieval_iterative._bound_y_prev("   \n  ")
          assert bounded == ""
          assert truncated is False


  class TestSearchIterative:
      def test_blank_y_prev_skips_round_two_and_matches_plain_search(self, ledger_con):
          ledger.upsert_reference(ledger_con, make_reference(citekey="a2024", title="Digital Twin"))
          plain = retrieval.search("digital twin")
          found, truncated = retrieval_iterative.search_iterative("digital twin", "   ")
          assert [r.citekey for r in found] == [r.citekey for r in plain]
          assert truncated is False

      def test_empty_query_with_y_prev_still_returns_nothing(self, ledger_con):
          """A query with no terms must not fall through to a round-2
          search on y_prev alone -- that would be prose-only retrieval
          with no sub-theme anchor, not what E4 describes."""
          ledger.upsert_reference(ledger_con, make_reference(citekey="a2024", title="Digital Twin"))
          found, truncated = retrieval_iterative.search_iterative("", "digital twin prose")
          assert found == []
          assert truncated is False

      def test_round_two_surfaces_a_citekey_round_one_missed(self, ledger_con):
          ledger.upsert_reference(
              ledger_con, make_reference(citekey="a2024", title="Digital Twin Overview")
          )
          ledger.upsert_reference(
              ledger_con, make_reference(citekey="b2024", title="Greenhouse Actuator Calibration")
          )
          found, _ = retrieval_iterative.search_iterative(
              "digital twin", "the greenhouse actuator calibration drifted", k=5
          )
          assert {"a2024", "b2024"} <= {r.citekey for r in found}

      def test_a_citekey_in_both_rounds_is_not_duplicated(self, ledger_con):
          ledger.upsert_reference(
              ledger_con, make_reference(citekey="a2024", title="Digital Twin Digital Twin")
          )
          found, _ = retrieval_iterative.search_iterative(
              "digital twin", "digital twin appears in the draft prose too"
          )
          citekeys = [r.citekey for r in found]
          assert citekeys.count("a2024") == 1

      def test_result_is_capped_at_k_even_after_merging_two_rounds(self, ledger_con):
          for i in range(8):
              ledger.upsert_reference(
                  ledger_con, make_reference(citekey=f"item{i}_2024", title="Digital Twin Paper")
              )
          found, _ = retrieval_iterative.search_iterative(
              "digital twin", "digital twin architecture prose", k=3
          )
          assert len(found) <= 3

      def test_truncated_flag_reflects_bound_y_prev(self, ledger_con):
          ledger.upsert_reference(ledger_con, make_reference(citekey="a2024", title="Digital Twin"))
          long_prose = "digital twin " * 300
          _, truncated = retrieval_iterative.search_iterative("digital twin", long_prose)
          assert truncated is True
  ```

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_retrieval_iterative.py -v
  ```

  Expected: `ModuleNotFoundError: No module named 'chitragupta.retrieval_iterative'`.

- [ ] Implement:

  ```python
  """ITER-RETGEN (Shao et al., Findings of EMNLP 2023) with a human's own
  hand-edited prose standing in for the model generation the paper calls
  y_{t-1} -- FEATURE-ROADMAP.md's E4, "the draft is the query". The
  paper forms its next query by concatenating the previous generation
  with the original question (y_{t-1} || q); no model writes it, so the
  retrieval path stays deterministic. Here y_{t-1} is a section's own
  hand-edited prose (the draft fingerprint, #454/#462, is what says it
  changed), not a model's output -- see docs/RAG.md's "Stage 11:
  revision" for why that sidesteps the paper's own dominant failure mode
  (a bad first generation entrenching a bad query).

  Deliberately two rounds, never more (docs/RAG.md: iteration 2 gains
  13.7-16.6 recall points, iterations 3-7 gain about one) -- there is no
  parameter here to ask for a third. Deliberately merge-then-cap, not
  FlashRAG's IRCoT shape, which merges two rounds with max(old, new) but
  never truncates the result (a live crash in their own issue tracker,
  per docs/RAG.md). Both rounds are computed against the whole corpus by
  chitragupta.retrieval.search() regardless of k (k only truncates the
  returned list, not what gets scored), so there is no candidate loss
  from using the same k for each round and the final cap.
  """

  from chitragupta.retrieval import SearchResult, _query_terms, search

  # Characters of hand-edited section prose appended to a query before a
  # second retrieval round. A long section would otherwise swamp the
  # sub-theme's own query terms in a bag-of-words score -- the reason
  # this is an explicit, documented character cut (matching
  # chitragupta/retrieval_cli.py's EVIDENCE_CHARS/EVIDENCE_WINDOWS shape)
  # rather than a token limit some downstream call would apply silently.
  # Unmeasured, same as EVIDENCE_CHARS: FEATURE-ROADMAP.md's E4 asks for
  # an explicit bound, not a specific number backed by a benchmark.
  Y_PREV_MAX_CHARS = 1500


  def _bound_y_prev(y_prev: str, limit: int = Y_PREV_MAX_CHARS) -> tuple[str, bool]:
      """`y_prev` collapsed to single-spaced text and cut to at most
      `limit` characters, on a word boundary where one exists in range.

      Returns `(bounded_text, truncated)` so a caller can say so -- a
      silent clip is exactly what this replaces. Blank input (including
      whitespace-only) returns `("", False)`.
      """
      flat = " ".join(y_prev.split())
      if len(flat) <= limit:
          return flat, False
      cut = flat[:limit].rsplit(" ", 1)[0]
      return cut, True


  def search_iterative(
      query: str,
      y_prev: str,
      k: int = 5,
      snippet_chars: int = 500,
      collection: str | None = None,
  ) -> tuple[list[SearchResult], bool]:
      """Two-round retrieval: round 1 is `search(query, ...)` unchanged;
      round 2 appends a bounded `y_prev` (`_bound_y_prev`) to `query` and
      searches again. Results are merged by citekey -- when a citekey
      scored in both rounds, the higher score wins -- re-sorted
      descending by score (ties broken on citekey, for a deterministic
      order), and sliced to `k`.

      Returns `(results, y_prev_truncated)`. Round 2 is skipped -- and
      round 1's own result returned unchanged -- whenever `y_prev` bounds
      to nothing, or `query` itself tokenizes to no terms
      (`_query_terms`): a query with no terms has no sub-theme anchor for
      `y_prev` to extend, and round 2 would be prose-only retrieval, a
      different feature from what E4 describes.
      """
      round1 = search(query, k=k, snippet_chars=snippet_chars, collection=collection)
      bounded, truncated = _bound_y_prev(y_prev)
      if not bounded or not _query_terms(query):
          return round1, truncated

      round2 = search(
          f"{query} {bounded}", k=k, snippet_chars=snippet_chars, collection=collection
      )
      merged: dict[str, SearchResult] = {}
      for result in (*round1, *round2):
          current = merged.get(result.citekey)
          if current is None or result.score > current.score:
              merged[result.citekey] = result
      ranked = sorted(merged.values(), key=lambda r: (-r.score, r.citekey))
      return ranked[:k], truncated
  ```

- [ ] Run: `.venv-full/bin/python -m pytest tests/test_retrieval_iterative.py -v`
  Expected: PASS, all.

- [ ] Run: `.venv-full/bin/python -m pytest tests/test_code_standards_scan.py -v`
  Expected: PASS.

- [ ] Commit.

  ```bash
  git add chitragupta/retrieval_iterative.py tests/test_retrieval_iterative.py
  git commit -m "feat: add search_iterative, ITER-RETGEN with a human's draft as y_{t-1}"
  ```

### Task 2: wire `--y-prev` and `--origin reground` into `retrieve search`

**Files:** modify `chitragupta/retrieval_cli.py`; modify
`tests/test_retrieval.py`.

- [ ] Write the failing tests, added to `class TestCli` (reuse its
  existing `_seed` helper):

  ```python
      def test_y_prev_widens_results_beyond_a_plain_search(self, ledger_con, tmp_path, capsys):
          self._seed(ledger_con, tmp_path)
          greenhouse = tmp_path / "b2024.txt"
          greenhouse.write_text("padding " * 50 + "greenhouse actuator calibration drifted")
          ledger.upsert_reference(
              ledger_con, make_reference(citekey="b2024", title="Greenhouse Actuator")
          )
          ledger.mark_parsed(ledger_con, "b2024", greenhouse)

          assert (
              retrieval.main(
                  [
                      "search",
                      "digital twin architecture",
                      "--y-prev",
                      "the greenhouse actuator calibration drifted overnight",
                  ]
              )
              == 0
          )
          out = capsys.readouterr().out
          assert "a2024" in out
          assert "b2024" in out

      def test_y_prev_truncation_is_reported(self, ledger_con, tmp_path, capsys):
          from chitragupta import retrieval_iterative

          self._seed(ledger_con, tmp_path)
          long_prose = "digital twin " * 300
          assert (
              retrieval.main(["search", "digital twin architecture", "--y-prev", long_prose]) == 0
          )
          out = capsys.readouterr().out
          assert f"{retrieval_iterative.Y_PREV_MAX_CHARS} characters" in out

      def test_no_y_prev_flag_behaves_exactly_as_before(self, ledger_con, tmp_path, capsys):
          self._seed(ledger_con, tmp_path)
          assert retrieval.main(["search", "digital twin architecture"]) == 0
          assert "[note]" not in capsys.readouterr().out

      def test_log_records_reground_origin(self, ledger_con, tmp_path, capsys):
          from chitragupta import dossier
          from chitragupta.dossier import _retrieval

          self._seed(ledger_con, tmp_path)
          draft = config.DRAFTS_DIR / "survey.md"
          draft.parent.mkdir(parents=True, exist_ok=True)
          draft.write_text("# s\n")

          assert (
              retrieval.main(
                  [
                      "search",
                      "digital twin architecture",
                      "--y-prev",
                      "hand-edited prose",
                      "--log",
                      str(draft),
                      "--origin",
                      "reground",
                  ]
              )
              == 0
          )
          pairs = _retrieval.recorded_queries_with_origin(dossier.dossier_dir(draft))
          assert ("digital twin architecture", "reground") in pairs

      def test_log_records_one_row_not_two_for_a_y_prev_call(self, ledger_con, tmp_path):
          from chitragupta import dossier

          self._seed(ledger_con, tmp_path)
          draft = config.DRAFTS_DIR / "survey.md"
          draft.parent.mkdir(parents=True, exist_ok=True)
          draft.write_text("# s\n")

          retrieval.main(
              [
                  "search",
                  "digital twin architecture",
                  "--y-prev",
                  "hand-edited prose",
                  "--log",
                  str(draft),
                  "--origin",
                  "reground",
              ]
          )
          calls, _ = dossier.retrieval_cost(dossier.dossier_dir(draft))
          assert calls == 1
  ```

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_retrieval.py -k "y_prev or reground" -v
  ```

  Expected: FAIL with `error: unrecognized arguments: --y-prev` (or
  `--origin: invalid choice: 'reground'`).

- [ ] Implement. Add the import, alongside the existing one:

  ```python
  from chitragupta import config, ledger, retrieval_iterative
  from chitragupta.retrieval import SearchResult, _full_text, _query_terms, _windows, search
  ```

  Add `--y-prev` to `p_search` only, in `_build_parser`, after the
  existing `--collection` argument and before `p_evidence = sub.add_parser(...)`:

  ```python
      p_search.add_argument(
          "--y-prev",
          metavar="TEXT",
          help="A hand-edited section's own prose (FEATURE-ROADMAP.md's E4: "
          "ITER-RETGEN with a human in the generation slot). Appended to the "
          "query for a second retrieval round, merged with the first and "
          f"capped back to --k. Bounded to {retrieval_iterative.Y_PREV_MAX_CHARS} "
          "characters explicitly; omit for an ordinary single-round search",
      )
  ```

  Extend `--origin`'s choices, in the `for each in (p_search, p_evidence):` loop:

  ```python
          each.add_argument(
              "--origin",
              choices=("declared", "extended", "reground"),
              help="With --log: this query came verbatim from outline.md "
              "(declared), was added because a declared section came up "
              "thin (extended), or is a --y-prev re-grounding round after a "
              "hand edit (reground). Omit for a call outline.md had no say in",
          )
  ```

  Replace `_run_search`:

  ```python
  def _run_search(args) -> tuple[int, int]:
      """The search subcommand: prints the ranking and returns
      (results, chars)."""
      if args.y_prev:
          found, truncated = retrieval_iterative.search_iterative(
              args.query, args.y_prev, k=args.k, snippet_chars=args.chars, collection=args.collection
          )
          if truncated:
              print(
                  f"  [note] --y-prev was cut to {retrieval_iterative.Y_PREV_MAX_CHARS} "
                  "characters before it was appended to the query."
              )
      else:
          found = search(args.query, k=args.k, snippet_chars=args.chars, collection=args.collection)
      if not found:
          print("No results.")
      chars = _print_results(found)
      if found:
          print(
              "\n  Judge each snippet yourself -- a high score means the query's "
              "words are in the document, not that it supports your claim. Run "
              "`evidence --citekey <key>` where a snippet is not enough to decide."
          )
      return len(found), chars
  ```

  `_log_call`'s existing `query=args.query` (unchanged) is what makes
  the "one row, original query text" logging choice real -- it already
  logs `args.query`, never the round-2 concatenation, so no change is
  needed there for the single-row-per-call semantics design decision 3
  states.

- [ ] Run: `.venv-full/bin/python -m pytest tests/test_retrieval.py -v`
  Expected: PASS, all -- including every pre-existing `TestCli` test
  (unchanged behaviour when `--y-prev` is omitted).

- [ ] Commit.

  ```bash
  git add chitragupta/retrieval_cli.py tests/test_retrieval.py
  git commit -m "feat: --y-prev and --origin reground on retrieve search"
  ```

### Task 3: `declared_vs_actual` counts a `reground` round as a run

**Files:** modify `chitragupta/dossier/_outline.py`; modify
`chitragupta/dossier/_status.py`; modify `tests/test_dossier_outline.py`;
modify `tests/test_dossier.py`.

Read `tests/test_dossier_outline.py::TestDeclaredVsActual` and
`tests/test_dossier.py::TestStatusLines` first -- reuse their exact
fixture/construction patterns for the new tests below rather than
inventing a new shape.

- [ ] Write the failing tests, added to `TestDeclaredVsActual`:

  ```python
      def test_a_regrounded_query_is_reported_run_and_regrounded(self, draft):
          dossier.init(draft, "survey")
          dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 5, 100, origin="reground")
          outline_ = _outline.parse(
              "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
          )
          drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
          assert drift.sections["Failure modes"].run == ["timestep mismatch"]
          assert drift.sections["Failure modes"].not_run == []
          assert drift.regrounded == ["timestep mismatch"]

      def test_regrounded_is_reported_flat_not_per_section(self, draft):
          dossier.init(draft, "survey")
          dossier.log_retrieval(draft, "search", "surrogate model twin", 5, 5, 100, origin="reground")
          outline_ = _outline.parse("## Family 3\n\nbrief: text\n\nqueries:\n- corrected physics\n")
          drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
          assert drift.regrounded == ["surrogate model twin"]
          assert drift.sections["Family 3"].not_run == ["corrected physics"]

      def test_an_unspecified_origin_is_still_neither_run_nor_regrounded(self, draft):
          """Regression guard for the risk this task is named for: only
          the literal "reground" string joins `run`. An unspecified
          origin must still read as not-run, same as before this task."""
          dossier.init(draft, "survey")
          dossier.log_retrieval(draft, "search", "timestep mismatch", 5, 5, 100)
          outline_ = _outline.parse(
              "## Failure modes\n\nbrief: text\n\nqueries:\n- timestep mismatch\n"
          )
          drift = _outline.declared_vs_actual(dossier.dossier_dir(draft), outline_)
          assert drift.sections["Failure modes"].not_run == ["timestep mismatch"]
          assert drift.regrounded == []
  ```

- [ ] Write the failing test, added to `tests/test_dossier.py`'s
  `TestStatusLines` (match that class's existing `Status`/`OutlineDrift`
  construction pattern -- read a neighbouring test in the class first and
  follow its exact fixture shape rather than the sketch below if it
  differs):

  ```python
      def test_regrounded_count_is_reported(self, capsys):
          from chitragupta.dossier._outline import OutlineDrift, SectionDrift
          from chitragupta.dossier._status import Status, _print_status_outline

          report = Status(
              declared_vs_actual=OutlineDrift(
                  sections={"S": SectionDrift(heading="S", run=["q"], not_run=[])},
                  regrounded=["q"],
              )
          )
          _print_status_outline(report)
          out = capsys.readouterr().out
          assert "1 regrounded" in out
          assert "regrounded  'q'" in out
  ```

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_dossier_outline.py tests/test_dossier.py -k "reground" -v
  ```

  Expected: FAIL -- `AttributeError: 'OutlineDrift' object has no
  attribute 'regrounded'`.

- [ ] Implement. In `chitragupta/dossier/_outline.py`, extend
  `OutlineDrift`:

  ```python
  @dataclass
  class OutlineDrift:
      """ "Did this draft follow its declared outline?", read from
      `retrieval.md`'s `origin` column rather than trusted.

      `extended` is flat, not per-section: `retrieval.md` records no
      section for a call, only the query text and its origin, so an
      `--extend` addition can be reported as having happened but not
      attributed to the section that came up thin. `regrounded` is the
      same shape, for a `--y-prev` re-grounding round after a hand edit
      (FEATURE-ROADMAP.md's E4) -- counted in `run` too, since the
      underlying declared query did in fact execute (the CLI logs the
      original query text, not the round-2 concatenation); listed
      separately so `dossier status` can still say a hand-edit round
      happened.
      """

      sections: "dict[str, SectionDrift]" = field(default_factory=dict)
      extended: list[str] = field(default_factory=list)
      regrounded: list[str] = field(default_factory=list)
  ```

  And `declared_vs_actual`:

  ```python
      pairs = recorded_queries_with_origin(dossier)
      run = {_normalised(query) for query, origin in pairs if origin in ("declared", "reground")}
      extended = [query for query, origin in pairs if origin == "extended"]
      regrounded = [query for query, origin in pairs if origin == "reground"]

      sections = {
          heading: SectionDrift(
              heading=heading,
              run=[q for q in section.queries if _normalised(q) in run],
              not_run=[q for q in section.queries if _normalised(q) not in run],
          )
          for heading, section in outline.sections.items()
      }
      return OutlineDrift(sections=sections, extended=extended, regrounded=regrounded)
  ```

  In `chitragupta/dossier/_status.py`, extend `_print_status_outline`:

  ```python
  def _print_status_outline(report: Status) -> None:
      """ "Did this draft follow outline.md?", from `declared_vs_actual`
      (#455) -- absent when there is no outline.md to have followed."""
      if report.declared_vs_actual is None:
          return
      drift = report.declared_vs_actual
      run = [q for s in drift.sections.values() for q in s.run]
      not_run = [(s.heading, q) for s in drift.sections.values() for q in s.not_run]
      extended = drift.extended
      regrounded = drift.regrounded
      print(
          f"\nOutline: {len(run)} declared quer{'y' if len(run) == 1 else 'ies'} run, "
          f"{len(not_run)} not, {len(extended)} extended, {len(regrounded)} regrounded."
      )
      for heading, query in not_run:
          print(f"  not run   {heading}: {query!r}")
      for query in extended:
          print(f"  extended  {query!r}")
      for query in regrounded:
          print(f"  regrounded  {query!r}")
  ```

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_dossier_outline.py tests/test_dossier.py -v
  ```

  Expected: PASS, all -- including every pre-existing test in both files
  (`test_an_unspecified_origin_call_is_neither_run_nor_extended` must
  still pass unchanged: it never logs `origin="reground"`, so widening
  `run` to include that literal does not touch it).

- [ ] Run: `.venv-full/bin/python -m pytest tests/test_code_standards_scan.py -v`
  Expected: PASS -- confirms the C2 budget table above held for both
  files. If either crossed 250, split following the
  `_retrieval.py`/`_retrieval_queries.py` precedent (#467).

- [ ] Commit.

  ```bash
  git add chitragupta/dossier/_outline.py chitragupta/dossier/_status.py tests/test_dossier_outline.py tests/test_dossier.py
  git commit -m "feat: count a reground origin as its declared query having run"
  ```

### Task 4: wire the offer into `draft-reviser`

**Files:** modify `.claude/skills/draft-reviser/SKILL.md`.

- [ ] In the "1. Locate the draft and read its state" section, insert
  immediately after the existing table of four staleness findings and
  its following "not recorded" paragraph, before "Then read `scope.md`
  and `steering.md`.":

  ```markdown
  **A `CHANGED` fingerprint is also FEATURE-ROADMAP.md's E4 trigger**: "a
  draft fingerprint is what says the query moved." Once the four
  findings above are settled -- never before, and never folded into the
  same offer -- and only for a section `outline.md` declares one or more
  `queries:` for, offer one more thing: *"Since you hand-edited
  `<heading>`, I can also re-run that section's own declared query --
  currently `<query, read fresh from outline.md>` -- with your new
  wording appended: ITER-RETGEN with you in the generation slot, not a
  model. Want me to?"* Always show the query text verbatim in the offer,
  not just its existence -- `outline.md` is read fresh every time (never
  cached), so if it was edited alongside the draft, this is the only
  place that edit becomes visible before a real retrieval call spends
  on it. If they agree, carry that section's current prose into step 4
  below as `--y-prev`. If they decline, the section has no declared
  query, or there is no `outline.md` for this draft **-- the common
  case, since `outline.md` is opt-in --** say so and move on: there is
  no declared query for round 2 to anchor to, so no offer is made at
  all, not a silently degraded one. Never run this more than once per
  section per revision session; two rounds is the whole mechanism, not
  a loop to repeat. (Editing `outline.md`'s `queries:` alone, with the
  draft untouched, is not itself a trigger -- see "What this closes"
  above.)
  ```

- [ ] In the "4. Decide whether you need to search at all" section,
  insert immediately after the existing bash block (the one with
  `retrieve search "<query>" --k 15 ...` and `retrieve evidence ...`),
  before the `(or chitragupta.enrich.embed_index.search() ...)`
  parenthetical:

  ````markdown
  **If step 1's offer was accepted**, run that section's query as a
  re-grounding round instead of a plain search:

  ```bash
  python -m chitragupta.draft retrieve search "<the section's declared query>" \
      --y-prev "<the section's current, hand-edited prose>" \
      --k 15 --collection "<from scope.md>" --log content/drafts/<path> --origin reground
  ```

  The CLI bounds `--y-prev` itself (1500 characters, on a word boundary,
  and reports it if anything was cut) and merges the two rounds' results
  before capping back to `--k` -- nothing here hand-truncates or
  hand-merges. `--origin reground` is what lets `dossier status` count
  this as the section's declared query having run, distinct from an
  ordinary `declared` or `extended` call.
  ````

- [ ] Run: `markdownlint-cli2 ".claude/skills/draft-reviser/SKILL.md"`
  Expected: 0 issues.

- [ ] Commit.

  ```bash
  git add .claude/skills/draft-reviser/SKILL.md
  git commit -m "docs: wire E4's draft-as-query round into draft-reviser's fingerprint branch"
  ```

## 📚 Docs and roadmap sweep

**Files:** modify `docs/DOSSIER.md`, `docs/CLI.md`, `docs/RAG.md`,
`docs/FEATURES.md`, `docs/FEATURE-ROADMAP.md`,
`outline-driven-drafting-and-manual-edits.md`; add
`tests/test_retrieval.py::TestDocsQuoteTheActualDefaults`'s companion
case.

- [ ] `docs/DOSSIER.md`: insert a new subsection immediately after "The
  draft fingerprint" section ends (after the paragraph ending "...a
  reworded sentence."):

  ````markdown
  ### 🔁 The fingerprint as a retrieval trigger (#456, FEATURE-ROADMAP.md's E4)

  A `CHANGED` fingerprint is also ITER-RETGEN's `y_{t-1}` (Shao et al.,
  *Findings of EMNLP 2023*, docs/RAG.md) with a person in the generation
  slot instead of a model: a hand-edited section's own prose can stand
  in for the paper's "previous generation" and drive one extra
  retrieval round for that section, rather than a plain single-round
  search. `draft-reviser` offers this once the four staleness findings
  above are settled, and only for a section `outline.md` declares a
  query for -- never applies it unasked, same as every other repair
  this fingerprint gates.

  ```bash
  python -m chitragupta.draft retrieve search "<query>" \
      --y-prev "<section's current prose>" --origin reground --log <draft>
  ```

  Exactly two rounds, never more (`chitragupta/retrieval_iterative.py`):
  round 1 is the plain query, round 2 appends the prose (bounded to
  1500 characters, on a word boundary), and the two rounds' results are
  merged by citekey and capped back to `--k` -- accumulate, then cap,
  not FlashRAG's uncapped `IRCoT` merge. The prose itself never becomes
  draft content, an `evidence.md` block, or anything else persisted
  beyond the query string.
  ````

- [ ] `docs/CLI.md`: add a row to the existing flag table, after the
  `--origin` row:

  ```markdown
  | `--y-prev TEXT` | `search` | -- | Append this text (bounded to 1500 characters) to the query for a second retrieval round, merged with the first and capped back to `--k` -- FEATURE-ROADMAP.md's E4 |
  ```

  Change the `--origin` row's flag column to
  `` `--origin declared\|extended\|reground` `` and extend its
  description:

  ```markdown
  | `--origin declared\|extended\|reground` | all | -- | With `--log`: whether this query came from `outline.md` verbatim, extended a section that came up thin, or re-ran a section's query with `--y-prev` after a hand edit |
  ```

  Add a second example, after the existing one:

  ```bash
  chitragupta draft retrieve search "digital twin architecture" \
      --y-prev "the drift compensator now recomputes offset every cycle" \
      --k 15 --origin reground --log content/drafts/survey.md
  ```

- [ ] `docs/RAG.md`: replace "Stage 11: revision"'s closing sentence
  ("Its one real remaining gap is honest: nothing fingerprints the
  draft, so on *hand-edit* detection this pipeline is no better than the
  other six.") with:

  ```markdown
  That gap closed at #462 (the draft fingerprint, which says *that* a
  section moved) and #456 (`chitragupta/retrieval_iterative.py`, which
  uses what moved): a hand-edited section's own prose can stand in for
  `y_{t-1}` and drive one extra, capped retrieval round for that
  section, merged with what round 1 already found rather than replacing
  it.
  ```

- [ ] `docs/FEATURES.md`: insert a new paragraph after the existing
  "#455" paragraph (ending "...becomes decidable rather than trusted.")
  and before the "### 📖 Evidence" heading:

  ```markdown
  **A hand-edited section's own prose can re-run its own retrieval
  (#456).** Once `dossier status` reports the draft fingerprint
  `CHANGED`, `draft-reviser` can offer one extra retrieval round for the
  section that changed, using the section's new wording as ITER-RETGEN's
  `y_{t-1}` (Shao et al., *Findings of EMNLP 2023*) -- a human in the
  generation slot a model would otherwise occupy. Exactly two rounds,
  merged and capped, never applied unasked.
  ```

- [ ] `docs/FEATURE-ROADMAP.md`: per this repo's convention for a
  shipped item (fourteen prior items "removed from this document rather
  than marked"):
  1. Delete the whole "### 🔁 E4: the draft is the query" section.
  2. In the Theme E intro paragraph, delete "`plans/outline-driven-drafting-and-manual-edits.md`
     is the plan and carries the measurements for both; only E4 below is
     still open." and replace with a sentence noting Theme E has no open
     items, matching how other closed-out themes in this file read.
  3. Delete the build-order table row for E4 (`| 9 | [E4]... |`) and
     renumber rows 10-11 to 9-10.
  4. In the "Some items have written plans" paragraph, delete "and
     Theme E's remaining item, E4, shares
     `plans/outline-driven-drafting-and-manual-edits.md`", keeping the
     rest of the sentence (B4/B5/C3) grammatically intact.

- [ ] `outline-driven-drafting-and-manual-edits.md`: add a short recap
  section after "## 🔁 Amendments owed to B5, not a new item" and before
  "## 🔗 Adjacent, deliberately not bundled", following "PR 3"'s
  shape -- a pointer to this file, not a duplicate of it:

  ```markdown
  ## ▶ PR 4: the draft is the query

  FEATURE-ROADMAP.md's E4, issue #456. Full design and build order in
  [e4-draft-is-the-query.md](e4-draft-is-the-query.md). Once merged,
  that file's own header records the closing PR per this directory's
  convention.
  ```

- [ ] Pin the new documented constant, in
  `tests/test_retrieval.py::TestDocsQuoteTheActualDefaults`:

  ```python
      def test_y_prev_bound_is_pinned_in_cli_md(self):
          from chitragupta import retrieval_iterative

          cli = (config.shipped("docs", "CLI.md")).read_text(encoding="utf-8")
          y_prev_row = next(line for line in cli.splitlines() if "`--y-prev TEXT`" in line)
          assert f"{retrieval_iterative.Y_PREV_MAX_CHARS} characters" in y_prev_row
  ```

  (This is why the CLI.md row above writes "1500 characters", not
  "1,500" -- the pin does a plain string match against the constant.)

- [ ] Run:

  ```bash
  .venv-full/bin/python -m pytest tests/test_retrieval.py::TestDocsQuoteTheActualDefaults -v
  markdownlint-cli2 "*.md" "docs/**/*.md" "plans/**/*.md"
  ```

  Expected: PASS / 0 issues.

- [ ] Commit.

  ```bash
  git add docs/DOSSIER.md docs/CLI.md docs/RAG.md docs/FEATURES.md docs/FEATURE-ROADMAP.md \
      plans/outline-driven-drafting-and-manual-edits.md tests/test_retrieval.py
  git commit -m "docs: document E4, the draft-as-query retrieval round"
  ```

## ✅ Verification

Before calling E4 done, per DEVELOPER-AGENTS.md's "Before claiming a
task complete":

```bash
.venv-full/bin/python -m pytest --cov --cov-report=term-missing
pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks
ruff check chitragupta scripts .claude/hooks
ruff format --check chitragupta scripts tests bench .claude/hooks
markdownlint-cli2 "*.md" "docs/**/*.md" ".claude/**/*.md" "plans/**/*.md"
python scripts/code_standards.py
poetry check
```

A bare worktree checkout has pre-existing, unrelated failures (missing
`config.toml`/`.claude/settings.json` -- see the worktree's own baseline
before attributing any red test to this change); diff pass/fail counts
against a `git stash`-and-rerun baseline rather than assuming 0 is
required.

**One real smoke test beyond the unit suite**, against the real corpus,
in a scratch draft under `content/drafts/_scratch/` (never a real draft
-- deleted after):

```bash
python -m chitragupta.draft dossier init content/drafts/_scratch/e4-smoke.md survey --outline
# hand-write a one-section outline.md with a queries: entry, hand-edit
# the draft body, stamp, then:
python -m chitragupta.draft dossier status content/drafts/_scratch/e4-smoke.md
python -m chitragupta.draft retrieve search "<declared query>" \
    --y-prev "<edited section prose>" --origin reground --log content/drafts/_scratch/e4-smoke.md
python -m chitragupta.draft dossier status content/drafts/_scratch/e4-smoke.md  # confirms "1 regrounded"
```

Also run `/open-code-review:delegate-review` (Markdown files are
`unsupported_ext` -- review those diffs by hand against the same rule
set, same as #462's precedent) before opening the PR. Check
`scripts/check_version_bump.py` / open PRs for a version-collision
before picking the next MINOR version number.

**Record the outcome.** When this merges, add a line at the top of this
file saying which PR closed it and what, if anything, changed from this
plan on the way -- this directory's one contract (plans/README.md).
