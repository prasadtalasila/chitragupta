# Claim-support checking (C2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a seventh review aid, `python -m chitragupta.review support <draft>`, that scores whether each citation's own claim is actually entailed by the passage of the source it cites — using a real NLI entailment model, never lexical overlap — and is permanently advisory (surfaced, never auto-repaired).

**Architecture:** A new top-level module, `chitragupta/entailment.py`, is the only place that reaches the optional NLI model (mirrors `chitragupta/overlap_chroma.py`'s "one seam" shape) and is gated behind the already-existing `enrich` extra — `sentence_transformers.CrossEncoder` is already part of that pinned dependency, so this needs **zero new pyproject.toml entries** (verified below, not guessed). A new aid module, `chitragupta/review/claim_support.py`, reuses `citation_provenance.claims()` for `(line, citekey, claim)` extraction and `passages.source_passages()` for the source text — both public, both already used together elsewhere in this codebase (`bench/bench_paraphrase_hunt.py`) — and swaps `citation_provenance.score_claim`'s lexical overlap for a real entailment score from `entailment.Entailer`. Rendering is split into `chitragupta/review/_claim_support_render.py`, the same one-way split `_uncited_render.py` established. The report is **ranked, never banded** — no "supported"/"weak" labels like `provenance` has — because the issue and `docs/PLAGIARISM-DESIGN.md`'s tier-3 precedent both say a threshold here would claim a precision this corpus's retrieval bias doesn't support.

**Tech Stack:** Python 3.11+, stdlib + `sentence_transformers.CrossEncoder` (already pinned, `enrich` extra), pytest with `sys.modules` stubbing for the optional model (same technique `tests/test_overlap_embed.py` uses) and constructor injection for the aid's own tests (same technique `overlap_embed.align_draft(scope, ...)` uses — the entailer is a parameter, not a hidden import).

**Spec:** GitHub issue [#386](https://github.com/prasadtalasila/chitragupta/issues/386), `docs/FEATURE-ROADMAP.md` "Theme C: verify faithful use" → C2, `docs/REQUIREMENTS.md` §1.2, `docs/AUTO-IMPROVEMENT.md` (R2, R10), `docs/PLAGIARISM-DESIGN.md` (tier-3 weak-discriminator precedent). This plan travels with those documents; executors should read the issue in full before Task 1.

## Why this is one plan, not two

`writing-plans`' Scope Check asks whether this should split into independent plans. It was considered and rejected: the issue's own scope bundles "an honest limits section... next to the aid's own output" and a "measurement over the project's own real drafts" into one PR, and the limits section cannot be written honestly before the measurement exists — a plan that shipped the aid first and measured second would either lie in its own docs on day one or ship with a placeholder, which this project's own rule (no fabrication, no placeholders) forbids either way. So the tasks below are ordered so the measurement (Task 7) runs before the doc text that depends on it (Task 8) is finalized, inside one sequential plan.

## A note on "build order item 9"

The issue cites "build order item 9" in `docs/FEATURE-ROADMAP.md`. As of this writing C2 is item **8** in that table — C1 (uncited-prose) shipped as PR #350 and was pruned from the "only unbuilt work appears here" table per that doc's own stated policy, which shifted C2 up one slot. The dependency this plan actually relies on (C2 depends on C1) is unambiguous either way; this is a numbering artifact, not a blocker.

## Global Constraints

- **≤25 statements per function**, ast-counted, ratcheted (`tests/test_code_standards_scan.py`). A function that would exceed this must be split, not exempted.
- **≤250 non-blank/non-comment lines per module** under `chitragupta/`, `scripts/` (not `tests/`), ratcheted. This is why the aid is three files (`claim_support.py`, `_claim_support_render.py`, `entailment.py`), not one.
- **Every `def` needs a return type annotation** (`tests/test_annotation_scan.py`, zero gaps allowed).
- **Coverage bar is 100%, line and branch** (`fail_under = 100` in `pyproject.toml`). No real model download is needed to hit it — everything ML-shaped is stubbed.
- **`chitragupta/review/__main__.py` raises `RuntimeError` at import** if `set(__main__.AIDS) != set(review.AIDS)` — both dicts must be edited in the same commit or the whole test suite fails to import.
- **No new dependency without cause, and this feature needs none**: `sentence_transformers.CrossEncoder` ships inside `sentence-transformers>=5.6,<6.0`, already pinned under the `enrich` group/extra for the embedding tier. Verify this before Task 1 (step 0) rather than trusting this note blindly.
- **Naming**: an advisory aid may not be called `audit`, `reckoning`, `verdict`, `ruling` or `triage`. This one is `support` (module `claim_support.py`) — already clear of the list.
- **No timestamp in any report** — inherited automatically from `review.header()`/`review.envelope()`; do not add one.
- **Advisory only, exit 0 always** — this aid never returns a non-zero exit for what it finds, only for a draft the layer refuses to read at all (matches every existing aid).
- **Never wire this into an unattended repair.** `docs/CODE-STANDARDS.md`'s R3 (via `AUTO-IMPROVEMENT.md`): "An unattended item's check is binary. No continuous score is ever the thing being optimised." The entailment score is continuous and is read by a human; nothing in this plan feeds it back into a gate, a reviser, or an agenda auto-fix.
- **Real venv only.** `pip install` outside a venv is blocked (PEP 668) on this host; use `.venv-full` for anything that imports `sentence_transformers` for real (Task 7, Task 8, and the pre-PR smoke test).

---

## Task 1: `chitragupta/entailment.py` — the one seam that reaches the optional model

**Files:**
- Create: `chitragupta/entailment.py`
- Modify: `chitragupta/config.py` (add `ENTAILMENT_MODEL`, near `EMBEDDING_MODEL` at line ~819)
- Test: `tests/test_entailment.py`

**Interfaces:**
- Produces: `entailment.optional_stack() -> Any | None` (the `CrossEncoder` class, or `None` if `sentence_transformers` isn't installed); `entailment.Entailer` (constructor `Entailer(model=None)`, method `.score(pairs: list[tuple[str, str]]) -> list[float]`); `entailment.unavailable_reason() -> str | None`; `entailment.open_entailer() -> tuple[Entailer | None, str | None]`.
- Consumes: `chitragupta.config.ENTAILMENT_MODEL` (new).

- [ ] **Step 0: Confirm the zero-new-dependency claim and the label-index attribute, for real**

  In `.venv-full` (per `[[memory: venv-pytest-cov-off-pin]]` — that's the in-pin venv), run:

  ```bash
  .venv-full/bin/python -c "
  from sentence_transformers import CrossEncoder
  m = CrossEncoder('cross-encoder/nli-deberta-v3-small')
  print(type(m.model))
  print(m.model.config.id2label)
  print(m.predict([('A cat sat on the mat.', 'An animal was on a mat.')]))
  "
  ```

  Record the exact printed `id2label` mapping and whether `predict()` returns raw logits or already-softmaxed probabilities (shape and value range tell you which — logits are usually not in `[0, 1]` and don't sum to 1 across the row). Task 1's implementation below assumes `m.model.config.id2label` exists and `predict()` returns raw logits requiring a softmax; if the real output differs, adjust `Entailer.score` accordingly before writing its test — do not ship the assumption unverified. This step is real investigation, not a placeholder: it produces the one fact the rest of this task's code depends on.

- [ ] **Step 1: Add the config knob**

  In `chitragupta/config.py`, immediately after the `EMBEDDING_MODEL` definition (~line 819):

  ```python
  ENTAILMENT_MODEL = _get(
      "ENTAILMENT_MODEL",
      "enrich",
      "entailment_model",
      default="cross-encoder/nli-deberta-v3-small",
  )
  ```

  `[enrich]`, not a dedicated `[entailment]` table: `EMBEDDING_MODEL` (the sibling this knob sits beside) already reads from `[enrich].embedding_model` despite living in a top-level module (`chitragupta/overlap_embed.py`), not under `chitragupta/enrich/` — so `[enrich]` is this project's actual convention for "config gated by the `enrich` optional-dependency group," not "config for the `chitragupta/enrich/` package" specifically. A dedicated table would be its own inconsistency.

  (The exact default model name is finalized by Task 6's investigation; this default is a placeholder for *which model*, not for the mechanism — update it here once Task 6 concludes, and note that update in Task 6 itself rather than leaving two sources of truth.)

- [ ] **Step 2: Write the failing test for `optional_stack`**

  ```python
  # tests/test_entailment.py
  """chitragupta/entailment.py: the one seam that reaches the optional
  NLI cross-encoder. sentence_transformers is mocked via sys.modules,
  the same way tests/test_overlap_embed.py does it for the embedding
  stack -- imported lazily inside functions, so patching sys.modules
  before the call shadows the real package without needing it
  uninstalled."""

  import sys
  import types

  import pytest

  from chitragupta import entailment


  def test_optional_stack_is_none_without_sentence_transformers(monkeypatch):
      monkeypatch.setitem(sys.modules, "sentence_transformers", None)
      assert entailment.optional_stack() is None
  ```

- [ ] **Step 3: Run it to see it fail**

  Run: `.venv-full/bin/pytest tests/test_entailment.py -v`
  Expected: FAIL — `entailment` module doesn't exist yet.

- [ ] **Step 4: Write `optional_stack`**

  ```python
  # chitragupta/entailment.py
  """The one seam that reaches the optional NLI entailment model.

  Mirrors chitragupta/overlap_chroma.py's shape: everything else this
  aid touches (chitragupta/review/claim_support.py's extraction and
  passage lookup) is stdlib-only and testable without the enrich group
  present. Only this module has to be probed for.

  Needs sentence_transformers.CrossEncoder, which is already part of
  the enrich group's sentence-transformers pin (>=5.6,<6.0) -- the
  same package chitragupta/overlap_chroma.py's Embedder loads
  SentenceTransformer from. No new pyproject.toml entry: CrossEncoder
  and SentenceTransformer are two classes in one already-pinned
  package.
  """

  from typing import Any

  from chitragupta import config


  def optional_stack() -> Any | None:
      """The `CrossEncoder` class, or `None` if sentence_transformers is
      not installed. Same probe shape as overlap_chroma.optional_stack."""
      try:
          from sentence_transformers import CrossEncoder
      except ImportError:
          return None
      return CrossEncoder
  ```

- [ ] **Step 5: Run it to see it pass**

  Run: `.venv-full/bin/pytest tests/test_entailment.py -v`
  Expected: PASS

- [ ] **Step 6: Write the failing test for `Entailer.score`**

  Add to `tests/test_entailment.py`:

  ```python
  class FakeCrossEncoderModel:
      """Stands in for the underlying transformers model CrossEncoder
      wraps -- only `.config.id2label` is read off it."""

      def __init__(self, id2label):
          self.config = types.SimpleNamespace(id2label=id2label)


  class FakeCrossEncoder:
      """Stands in for sentence_transformers.CrossEncoder itself.

      `logits` is keyed by the exact (premise, hypothesis) pair handed
      to `.predict()`, so a test can say "this pair scores these raw
      logits" without a real model anywhere.
      """

      def __init__(self, logits, id2label):
          self.logits = logits
          self.model = FakeCrossEncoderModel(id2label)
          self.calls = []

      def predict(self, pairs):
          self.calls.append(list(pairs))
          return [self.logits[pair] for pair in pairs]


  def test_score_picks_the_entailment_column_by_label_not_position():
      """The label order is a model property, not a convention this
      module may assume -- entailment sits at index 1 here and would
      break silently if the code hard-coded index 0."""
      fake = FakeCrossEncoder(
          logits={("premise a", "claim a"): [-10.0, 10.0, -10.0]},
          id2label={0: "contradiction", 1: "entailment", 2: "neutral"},
      )
      entailer = entailment.Entailer(model=fake)
      scores = entailer.score([("premise a", "claim a")])
      assert len(scores) == 1
      assert scores[0] == pytest.approx(1.0, abs=1e-3)

  def test_score_is_low_for_a_contradiction_logit():
      # Same logits as the test above, id2label swapped -- proves the
      # lookup goes by label, not position: entailment now sits at
      # index 0, which holds the *minimum* of this vector.
      fake = FakeCrossEncoder(
          logits={("premise b", "claim b"): [-10.0, 10.0, -10.0]},
          id2label={0: "entailment", 1: "contradiction", 2: "neutral"},
      )
      entailer = entailment.Entailer(model=fake)
      scores = entailer.score([("premise b", "claim b")])
      assert scores[0] == pytest.approx(0.0, abs=1e-3)

  def test_score_handles_several_pairs_in_one_call():
      fake = FakeCrossEncoder(
          logits={
              ("p1", "c1"): [0.0, 0.0, 0.0],
              ("p2", "c2"): [-10.0, 10.0, -10.0],
          },
          id2label={0: "contradiction", 1: "entailment", 2: "neutral"},
      )
      entailer = entailment.Entailer(model=fake)
      scores = entailer.score([("p1", "c1"), ("p2", "c2")])
      assert scores[0] == pytest.approx(1 / 3, abs=1e-3)
      assert scores[1] == pytest.approx(1.0, abs=1e-3)
  ```

- [ ] **Step 7: Run to see it fail**

  Run: `.venv-full/bin/pytest tests/test_entailment.py -v`
  Expected: FAIL — `Entailer` doesn't exist.

- [ ] **Step 8: Implement `Entailer`**

  Append to `chitragupta/entailment.py`:

  ```python
  import math


  def _softmax(logits: list[float]) -> list[float]:
      top = max(logits)
      exps = [math.exp(v - top) for v in logits]
      total = sum(exps)
      return [v / total for v in exps]


  class Entailer:
      """The NLI cross-encoder, loaded on first use.

      Lazy for the same reason chitragupta/overlap_chroma.py's Embedder
      is lazy: loading it costs real time and memory, and a draft with
      no citations at all must not pay that to find out it has nothing
      to score.

      `.score` takes (premise, hypothesis) pairs and returns the
      entailment probability for each -- softmaxed here rather than
      trusting the model's own `apply_softmax` kwarg, whose availability
      and default have moved across sentence-transformers releases; this
      way the contract is this module's own and stable regardless.
      """

      def __init__(self, model=None) -> None:
          self._model = model

      @property
      def model(self) -> Any:
          if self._model is None:
              from sentence_transformers import CrossEncoder

              self._model = CrossEncoder(config.ENTAILMENT_MODEL)
          return self._model

      def score(self, pairs: list[tuple[str, str]]) -> list[float]:
          if not pairs:
              return []
          id2label = self.model.model.config.id2label
          index = next(i for i, label in id2label.items() if label == "entailment")
          raw = self.model.predict(list(pairs))
          return [_softmax(list(row))[index] for row in raw]
  ```

- [ ] **Step 9: Run to see it pass**

  Run: `.venv-full/bin/pytest tests/test_entailment.py -v --cov=chitragupta.entailment --cov-report=term-missing`
  Expected: PASS, and coverage on `entailment.py` not yet 100% (the `model` property's lazy-import branch and `unavailable_reason`/`open_entailer` are still unwritten).

- [ ] **Step 10: Write the failing tests for the degrade-gracefully gate**

  ```python
  def test_unavailable_reason_names_the_missing_group(monkeypatch):
      monkeypatch.setattr(entailment, "optional_stack", lambda: None)
      reason = entailment.unavailable_reason()
      assert reason is not None
      assert "enrich" in reason

  def test_unavailable_reason_is_none_when_the_stack_is_present(monkeypatch):
      monkeypatch.setattr(entailment, "optional_stack", lambda: object())
      assert entailment.unavailable_reason() is None

  def test_open_entailer_returns_reason_when_unavailable(monkeypatch):
      monkeypatch.setattr(entailment, "optional_stack", lambda: None)
      entailer, reason = entailment.open_entailer()
      assert entailer is None
      assert reason is not None

  def test_open_entailer_returns_an_entailer_when_available(monkeypatch):
      monkeypatch.setattr(entailment, "optional_stack", lambda: object())
      entailer, reason = entailment.open_entailer()
      assert isinstance(entailer, entailment.Entailer)
      assert reason is None
  ```

- [ ] **Step 11: Run to see it fail**

  Run: `.venv-full/bin/pytest tests/test_entailment.py -v`
  Expected: FAIL — `unavailable_reason`/`open_entailer` don't exist.

- [ ] **Step 12: Implement the gate**

  Append to `chitragupta/entailment.py`:

  ```python
  def unavailable_reason() -> str | None:
      """Why claim-support checking cannot run, or None when it can.

      A sentence, not a code -- printed to a person mid-review, the same
      contract overlap_embed.unavailable_reason() carries for tier 3.
      """
      if optional_stack() is None:
          return (
              "the enrichment layer is not installed -- `poetry install --with enrich` "
              "adds the sentence-transformers package this aid scores with"
          )
      return None


  def open_entailer() -> tuple[Entailer | None, str | None]:
      """`(entailer, None)` when this aid can run, `(None, reason)` when
      it cannot. No built index or dossier is needed here, unlike tier
      3 -- only the import has to succeed."""
      reason = unavailable_reason()
      if reason is not None:
          return None, reason
      return Entailer(), None
  ```

- [ ] **Step 13: Run full file, confirm 100% coverage**

  Run: `.venv-full/bin/pytest tests/test_entailment.py -v --cov=chitragupta.entailment --cov-report=term-missing`
  Expected: PASS, 100% line+branch on `chitragupta/entailment.py`. If the `model` property's real-import branch shows as uncovered, that's expected and correct — `pyproject.toml`'s `[tool.coverage.run]` `omit` list already excludes the equivalent lazy-import lines in sibling enrich-gated modules; check whether `chitragupta/entailment.py` needs adding there or whether the property needs a `# pragma: no cover` on just the import line (`from sentence_transformers import CrossEncoder`), matching whichever convention `chitragupta/overlap_chroma.py`'s `Embedder.model` property uses — read that property's coverage handling before choosing.

- [ ] **Step 14: Commit**

  ```bash
  git add chitragupta/entailment.py chitragupta/config.py tests/test_entailment.py
  git commit -m "Add the entailment scoring seam claim-support checking will use"
  ```

---

## Task 2: `chitragupta/review/claim_support.py` — extraction, scoring orchestration, `Report`

**Files:**
- Create: `chitragupta/review/claim_support.py`
- Test: `tests/test_review_claim_support.py`

**Interfaces:**
- Consumes: `citation_provenance.claims(draft_text: str) -> list[tuple[int, str, str]]`; `passages.source_passages(con, citekey: str) -> tuple[list[Passage], str | None]`; `passages.Passage` (`.page`, `.words`, `.text`, `.label`, `.quotable`); `entailment.Entailer.score(pairs: list[tuple[str, str]]) -> list[float]`.
- Produces: `Finding` dataclass; `Report` dataclass (`.draft`, `.findings: list[Finding]`, `.unscoreable: dict[str, str]`); `build_report(draft_path: Path, entailer) -> Report`; `finding_id(citekey: str, claim: str) -> str`; `findings(report: Report) -> list[dict]` (keys: `id, line, citekey, claim, score, note`).

- [ ] **Step 1: Write the failing test for scoring one claim against its source's best passage**

  ```python
  # tests/test_review_claim_support.py
  """chitragupta/review/claim_support.py: does the cited source actually
  entail the claim citing it, per a real NLI model (stubbed here --
  the module's own logic is what is under test, not the model)."""

  import json

  import pytest

  from chitragupta import config, ledger
  from chitragupta.review import claim_support


  def _add_item(citekey, parsed_text=None, title="T"):
      parsed_path = None
      if parsed_text is not None:
          config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
          parsed_path = config.PARSED_DIR / f"{citekey}.txt"
          parsed_path.write_text(parsed_text, encoding="utf-8")
          parsed_path = str(parsed_path)
      con = ledger.connect()
      try:
          con.execute(
              "INSERT OR REPLACE INTO items (citekey, title, status, parsed_path, pdf_path, last_synced)"
              " VALUES (?, ?, 'parsed', ?, NULL, '2026-01-01')",
              (citekey, title, parsed_path),
          )
          con.commit()
      finally:
          con.close()


  def _sidecar(citekey, records):
      config.DOCLING_DIR.mkdir(parents=True, exist_ok=True)
      (config.DOCLING_DIR / f"{citekey}.passages.json").write_text(json.dumps(records))


  class FakeEntailer:
      """Scores by exact-pair table lookup -- no model anywhere."""

      def __init__(self, scores):
          self.scores = scores
          self.calls = []

      def score(self, pairs):
          self.calls.append(list(pairs))
          return [self.scores.get(pair, 0.0) for pair in pairs]


  def _draft(config_dir, text):
      draft = config_dir.DRAFTS_DIR / "topic" / "draft.md"
      draft.parent.mkdir(parents=True, exist_ok=True)
      draft.write_text(text, encoding="utf-8")
      return draft


  class TestBuildReport:
      def test_scores_a_claim_against_its_citekeys_best_passage(self, isolated_config):
          _add_item("good_2024")
          _sidecar("good_2024", [{"text": "Twins close the control loop.", "page": 1}])
          draft = _draft(config, "Digital twins close the loop [@good_2024].\n")
          fake = FakeEntailer(
              {("Twins close the control loop.", "Digital twins close the loop."): 0.91}
          )
          report = claim_support.build_report(draft, fake)
          assert len(report.findings) == 1
          finding = report.findings[0]
          assert finding.citekey == "good_2024"
          assert finding.score == pytest.approx(0.91)
          assert finding.passage.text == "Twins close the control loop."
  ```

- [ ] **Step 2: Run to see it fail**

  Run: `.venv/bin/pytest tests/test_review_claim_support.py -v`
  Expected: FAIL — `claim_support` module doesn't exist.

- [ ] **Step 3: Write the minimal `Finding`/`Report`/`build_report`**

  ```python
  # chitragupta/review/claim_support.py
  """Claim-support report: does the cited source actually entail the
  claim citing it -- scored by a real NLI entailment model, never
  lexical overlap.

  `chitragupta/review/citation_provenance.py` asks a related question
  with a lexical scorer and answers it cheaply; this aid exists because
  the roadmap's own argument for why that is not enough: a paraphrase
  that subtly misstates a paper passes the gate (real citekey), passes
  the verbatim scan (wording now differs), and passes provenance (the
  source remains topically related). Only reading whether the source's
  own words actually entail the claim catches that.

  Reuses citation_provenance.claims() for extraction (line, citekey,
  claim) rather than re-parsing -- the same function
  bench/bench_paraphrase_hunt.py already reuses for the same reason --
  and passages.source_passages() for the source text. Only the scorer
  differs: chitragupta/entailment.py's Entailer, injected rather than
  imported here, so this module's own logic is testable with no model
  anywhere (chitragupta/entailment.py's own tests cover the model seam).

  Ranked, never banded. Unlike provenance's "no support found / weak /
  supported" bands, this aid publishes a bare score. Retrieval already
  selected these passages by similarity, so the discriminator here is
  weak in the same way docs/PLAGIARISM-DESIGN.md records for tier 3 --
  and a band would claim a precision this corpus does not support. See
  docs/REVIEW.md's limits section.

  **Surfaced, never repaired unattended, and permanently.**
  docs/AUTO-IMPROVEMENT-RATIONALE.md settles this by mechanism, not
  policy: every check this loop owns returns clean on its worst output,
  which is exactly the paraphrase case above. An unattended reviser
  chasing a higher score would make a claim look supported without
  making it supported.

  Needs the `enrich` extra (chitragupta/entailment.py). Advisory like
  the other six -- exit 0 whatever it finds, no lock, no draft blocked.

  Usage:
      python -m chitragupta.review support content/drafts/<slug>.md
      python -m chitragupta.review support <draft.md> --json --write
  """

  import hashlib
  from dataclasses import dataclass, field
  from pathlib import Path

  from chitragupta import ledger
  from chitragupta.passages import Passage, source_passages
  from chitragupta.review import citation_provenance


  @dataclass
  class Finding:
      line: int
      citekey: str
      claim: str
      score: float
      passage: Passage | None = None
      note: str | None = None


  @dataclass
  class Report:
      draft: Path
      findings: list[Finding] = field(default_factory=list)
      unscoreable: dict[str, str] = field(default_factory=dict)


  def _quotable(passages: list[Passage]) -> list[Passage]:
      """Only passages with real text -- an entailment model needs an
      actual premise, unlike provenance's lexical scorer, which can
      still compare against a page-level bag of words."""
      return [p for p in passages if p.quotable]


  def _score_claim(
      entailer, claim: str, passages: list[Passage]
  ) -> tuple[float, Passage | None]:
      quotable = _quotable(passages)
      if not quotable:
          return 0.0, None
      scores = entailer.score([(p.text, claim) for p in quotable])
      best_index = max(range(len(scores)), key=scores.__getitem__)
      return scores[best_index], quotable[best_index]


  def build_report(draft_path: Path, entailer) -> Report:
      text = Path(draft_path).read_text(encoding="utf-8")
      report = Report(draft=Path(draft_path))
      with ledger.connection() as con:
          cache: dict[str, tuple[list[Passage], str | None]] = {}
          for line_no, citekey, claim in citation_provenance.claims(text):
              if citekey not in cache:
                  cache[citekey] = source_passages(con, citekey)
              passages, reason = cache[citekey]
              if not _quotable(passages):
                  report.unscoreable[citekey] = reason or (
                      "the source's passages carry no readable text to score "
                      "against (page-level only)"
                  )
                  score, passage, note = 0.0, None, report.unscoreable[citekey]
              else:
                  score, passage = _score_claim(entailer, claim, passages)
                  note = None
              report.findings.append(
                  Finding(line=line_no, citekey=citekey, claim=claim, score=score,
                          passage=passage, note=note)
              )
      report.findings.sort(key=lambda f: (f.score, f.line))
      return report
  ```

- [ ] **Step 4: Run to see it pass**

  Run: `.venv/bin/pytest tests/test_review_claim_support.py -v`
  Expected: PASS

- [ ] **Step 5: Add and pass tests for the unscoreable path, sort order, and `finding_id`/`findings()`**

  Add to `tests/test_review_claim_support.py`:

  ```python
  class TestUnscoreable:
      def test_a_citekey_with_no_passages_at_all_is_noted_not_scored(self, isolated_config):
          draft = _draft(config, "A claim about nothing on record [@missing_2024].\n")
          report = claim_support.build_report(draft, FakeEntailer({}))
          assert report.findings[0].score == 0.0
          assert "missing_2024" in report.unscoreable

      def test_a_citekey_with_only_page_level_passages_is_noted_not_scored(self, isolated_config):
          _add_item("pageonly_2024", parsed_text="whole page one text\fwhole page two text")
          draft = _draft(config, "A claim citing a page scan [@pageonly_2024].\n")
          report = claim_support.build_report(draft, FakeEntailer({}))
          assert report.findings[0].passage is None
          assert "pageonly_2024" in report.unscoreable


  class TestOrderingAndId:
      def test_worst_scoring_claim_sorts_first(self, isolated_config):
          _add_item("weak_2024")
          _sidecar("weak_2024", [{"text": "Unrelated source text.", "page": 1}])
          _add_item("strong_2024")
          _sidecar("strong_2024", [{"text": "Twins close the loop.", "page": 1}])
          draft = _draft(
              config,
              "Weak claim here [@weak_2024]. Strong claim here [@strong_2024].\n",
          )
          fake = FakeEntailer(
              {
                  ("Unrelated source text.", "Weak claim here."): 0.05,
                  ("Twins close the loop.", "Strong claim here."): 0.95,
              }
          )
          report = claim_support.build_report(draft, fake)
          assert [f.citekey for f in report.findings] == ["weak_2024", "strong_2024"]


  class TestFindingId:
      def test_stable_across_runs(self):
          assert claim_support.finding_id("k", "c") == claim_support.finding_id("k", "c")

      def test_differs_for_a_different_claim_on_the_same_citekey(self):
          assert claim_support.finding_id("k", "c1") != claim_support.finding_id("k", "c2")


  class TestFindings:
      def test_one_dict_per_finding_no_band(self, isolated_config):
          _add_item("good_2024")
          _sidecar("good_2024", [{"text": "Twins close the loop.", "page": 1}])
          draft = _draft(config, "Digital twins close the loop [@good_2024].\n")
          fake = FakeEntailer({("Twins close the loop.", "Digital twins close the loop."): 0.9})
          found = claim_support.findings(claim_support.build_report(draft, fake))
          assert found == [
              {
                  "id": claim_support.finding_id("good_2024", "Digital twins close the loop."),
                  "line": 1,
                  "citekey": "good_2024",
                  "claim": "Digital twins close the loop.",
                  "score": pytest.approx(0.9),
                  "note": None,
              }
          ]
  ```

- [ ] **Step 6: Run to see them fail**

  Run: `.venv/bin/pytest tests/test_review_claim_support.py -v`
  Expected: FAIL — `finding_id`/`findings` don't exist.

- [ ] **Step 7: Implement `finding_id` and `findings`**

  Append to `chitragupta/review/claim_support.py`:

  ```python
  def finding_id(citekey: str, claim: str) -> str:
      """A finding's identity, stable across runs (R2) -- keyed on the
      same (citekey, claim) pair citation_provenance.finding_id uses,
      because this is the same underlying question asked by a different
      scorer. Defined locally rather than imported: every aid in this
      layer owns its own finding_id, even when the formula matches."""
      digest = hashlib.sha256(f"{citekey}\x00{claim}".encode())
      return digest.hexdigest()[:12]


  def findings(report: Report) -> list[dict]:
      """One object per citation, worst-scoring first -- already the
      Report's own sort order, so this only shapes the dicts."""
      return [
          {
              "id": finding_id(f.citekey, f.claim),
              "line": f.line,
              "citekey": f.citekey,
              "claim": f.claim,
              "score": f.score,
              "note": f.note,
          }
          for f in report.findings
      ]
  ```

- [ ] **Step 8: Run full file, confirm passing and check coverage**

  Run: `.venv/bin/pytest tests/test_review_claim_support.py -v --cov=chitragupta.review.claim_support --cov-report=term-missing`
  Expected: PASS. Coverage will not be 100% yet — `build_parser`/`main`/`run` don't exist (Task 3).

- [ ] **Step 9: Commit**

  ```bash
  git add chitragupta/review/claim_support.py tests/test_review_claim_support.py
  git commit -m "Score each citation's claim against its source with a real entailment model"
  ```

---

## Task 3: `chitragupta/review/_claim_support_render.py` — how the report reads

**Files:**
- Create: `chitragupta/review/_claim_support_render.py`
- Test: `tests/test_review_claim_support.py` (same file, new test classes)

**Interfaces:**
- Consumes: `Report`, `findings(report) -> list[dict]`, `review.header(draft, aid, command) -> list[str]`.
- Produces: `render_markdown(report, command: str, found: list[dict]) -> str`; `format_report(report, found: list[dict]) -> str`.

- [ ] **Step 1: Write the failing tests**

  ```python
  # tests/test_review_claim_support.py, appended
  from chitragupta.review import _claim_support_render as render


  class TestRenderMarkdown:
      def test_includes_the_ranked_not_banded_caveat(self, isolated_config):
          draft = _draft(config, "No citations here.\n")
          report = claim_support.build_report(draft, FakeEntailer({}))
          text = render.render_markdown(report, "cmd", claim_support.findings(report))
          assert "ranked" in text.lower()
          assert "not a fact-check" in text.lower()

      def test_lists_a_finding_with_its_score_and_claim(self, isolated_config):
          _add_item("good_2024")
          _sidecar("good_2024", [{"text": "Twins close the loop.", "page": 1}])
          draft = _draft(config, "Digital twins close the loop [@good_2024].\n")
          fake = FakeEntailer({("Twins close the loop.", "Digital twins close the loop."): 0.9})
          report = claim_support.build_report(draft, fake)
          found = claim_support.findings(report)
          text = render.render_markdown(report, "cmd", found)
          assert "good_2024" in text
          assert "90%" in text

      def test_notes_an_unscoreable_citekey(self, isolated_config):
          draft = _draft(config, "A claim citing nothing on record [@missing_2024].\n")
          report = claim_support.build_report(draft, FakeEntailer({}))
          found = claim_support.findings(report)
          text = render.render_markdown(report, "cmd", found)
          assert "missing_2024" in text
          assert "not in the ledger" in text or "no readable text" in text


  class TestFormatReport:
      def test_plain_text_has_no_markdown_headings(self, isolated_config):
          draft = _draft(config, "No citations here.\n")
          report = claim_support.build_report(draft, FakeEntailer({}))
          text = render.format_report(report, claim_support.findings(report))
          assert "##" not in text
  ```

- [ ] **Step 2: Run to see them fail**

  Run: `.venv/bin/pytest tests/test_review_claim_support.py -v -k Render or FormatReport`
  Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the render module**

  ```python
  # chitragupta/review/_claim_support_render.py
  """How a claim-support report reads: the Markdown document and the
  plain-text stdout form.

  Split from claim_support.py the same way _uncited_render.py is split
  from uncited_prose.py -- nothing here imports it back, keeping the
  dependency one-way.

  One paragraph here is load-bearing and must not be trimmed: the
  caveat that a low score is not a fact-check and a high score is not
  proof, because retrieval already selected these passages by
  similarity. Dropping it is exactly the failure mode
  docs/REVIEW.md's "Two limits" section (soon three) warns against --
  a score read as a verdict.
  """

  from chitragupta import review

  _HOW_TO_READ = [
      "## How to read this",
      "",
      "Each entry pairs a citing sentence with the passage of its cited",
      "source an entailment model scored as the best match, ranked",
      "**worst first**. There are no bands here, unlike `provenance` --",
      "retrieval already selected these passages by similarity, so the",
      "model is discriminating inside a set chosen for being similar,",
      "and a threshold would claim a precision this corpus does not",
      "support (see docs/PLAGIARISM-DESIGN.md's tier 3 for the same",
      "argument made about wording overlap instead of entailment).",
      "",
      "**A low score is not a fact-check, and a high score is not proof.**",
      "A correct paraphrase can score low if it drifts from the source's",
      "own wording style; a claim that happens to echo its source's",
      "vocabulary can score high while misrepresenting it. The score is",
      "where to spend attention, not a verdict.",
      "",
      "A citekey whose source has no passage with readable text (a",
      "page-level scan, or nothing parsed at all) cannot be scored and",
      "is noted rather than given a score of zero standing for \"checked",
      "and found wanting\".",
      "",
  ]


  def _summary(report, found: list[dict]) -> list[str]:
      lines = [
          "## Summary",
          "",
          f"**{len(found)}** citation{'s' if len(found) != 1 else ''} scored, "
          f"**{len(report.unscoreable)}** citekey{'s' if len(report.unscoreable) != 1 else ''} "
          "could not be scored.",
          "",
      ]
      if report.unscoreable:
          lines += ["### Not scored", ""]
          for citekey, reason in sorted(report.unscoreable.items()):
              lines.append(f"- `{citekey}`: {reason}")
          lines.append("")
      return lines


  def _finding_lines(finding: dict) -> list[str]:
      return [
          f"- **line {finding['line']}** `[@{finding['citekey']}]` "
          f"({finding['score']:.0%}) (`{finding['id']}`)",
          f"  > {finding['claim']}" if finding["claim"] else "  > (no claim text)",
      ]


  def render_markdown(report, command: str, found: list[dict]) -> str:
      lines = review.header(report.draft, "support", command)
      lines += _HOW_TO_READ
      lines += _summary(report, found)
      lines += ["## Findings", ""]
      if not found:
          lines += ["No citations found in this draft.", ""]
      for finding in found:
          lines += _finding_lines(finding)
      return "\n".join(lines)


  def format_report(report, found: list[dict]) -> str:
      lines = [
          f"Claim support in {report.draft}",
          f"{len(found)} citations scored, {len(report.unscoreable)} not scored",
      ]
      for finding in found:
          lines.append(
              f"  {finding['score']:.0%} line {finding['line']} "
              f"[@{finding['citekey']}]: {finding['claim']}"
          )
      for citekey, reason in sorted(report.unscoreable.items()):
          lines.append(f"  n/a  {citekey}: {reason}")
      return "\n".join(lines)
  ```

- [ ] **Step 4: Run to see them pass**

  Run: `.venv/bin/pytest tests/test_review_claim_support.py -v`
  Expected: PASS

- [ ] **Step 5: Confirm 100% coverage on the render module**

  Run: `.venv/bin/pytest tests/test_review_claim_support.py --cov=chitragupta.review._claim_support_render --cov-report=term-missing`
  Expected: 100%. Add a test for the zero-unscoreable / zero-findings branches if anything shows missing (e.g. a report with findings but no unscoreable citekeys, and a report with neither).

- [ ] **Step 6: Commit**

  ```bash
  git add chitragupta/review/_claim_support_render.py tests/test_review_claim_support.py
  git commit -m "Render the claim-support report as Markdown and plain text"
  ```

---

## Task 4: CLI wiring and registration in both `AIDS` dicts

**Files:**
- Modify: `chitragupta/review/claim_support.py` (add `build_parser`, `main`, `run`, `_command`, `support_payload`)
- Modify: `chitragupta/review/__init__.py` (add `"support": "Claim support"` to `AIDS`)
- Modify: `chitragupta/review/__main__.py` (import `claim_support`, add `"support": (claim_support, "does the cited source entail this claim?")` to `AIDS`)
- Test: `tests/test_review_claim_support.py`

**Interfaces:**
- Produces: `build_parser(parser=None) -> argparse.ArgumentParser`; `main(argv=None) -> int`; `run(args) -> int`; `support_payload(report, command) -> dict`.
- Consumes: `entailment.open_entailer() -> tuple[Entailer | None, str | None]`; `review.require_reviewable`, `review.envelope`, `review.write`, `review.write_json`, `review.print_written`.

- [ ] **Step 1: Write the failing registration test**

  ```python
  # tests/test_review_claim_support.py, appended
  from chitragupta import review
  from chitragupta.review import __main__ as review_main


  class TestRegistration:
      def test_the_aid_is_in_both_tables(self):
          assert "support" in review.AIDS
          assert "support" in review_main.AIDS

      def test_it_files_its_report_beside_the_others(self, isolated_config):
          draft = config.DRAFTS_DIR / "dt" / "survey.md"
          assert review.report_path(draft, "support") == (
              config.REVIEW_DIR / "dt" / "survey.support.md"
          )
  ```

- [ ] **Step 2: Run to see it fail**

  Run: `.venv/bin/pytest tests/test_review_claim_support.py::TestRegistration -v`
  Expected: FAIL — `"support"` not in either dict yet.

- [ ] **Step 3: Register in `review/__init__.py`**

  In `chitragupta/review/__init__.py`, add to the `AIDS` dict (after `"uncited"`):

  ```python
  AIDS = {
      "provenance": "Citation provenance",
      "verbatim": "Verbatim scan",
      "coverage": "Citation coverage",
      "synthesis": "Multi-source synthesis",
      "figure": "TikZ layout check",
      "uncited": "Uncited prose",
      "support": "Claim support",
  }
  ```

- [ ] **Step 4: Write `build_parser`, `_command`, `support_payload`, `main`, `run`**

  Append to `chitragupta/review/claim_support.py`:

  ```python
  import argparse
  import json
  import shlex
  import sys

  from chitragupta import config, entailment, review


  def _command(draft: Path, as_json: bool, write: bool) -> str:
      parts = ["python", "-m", "chitragupta.review", "support", str(draft)]
      if as_json:
          parts += ["--json"]
      if write:
          parts += ["--write"]
      return shlex.join(parts)


  def support_payload(report: Report, command: str) -> dict:
      payload = review.envelope(report.draft, "support", command)
      payload.update(
          {
              "scored": len(report.findings) - len(report.unscoreable),
              "unscoreable": dict(sorted(report.unscoreable.items())),
              "findings": findings(report),
          }
      )
      return payload


  def build_parser(parser=None) -> argparse.ArgumentParser:
      if parser is None:
          parser = argparse.ArgumentParser(
              description="Does the cited source actually entail the claim citing it?",
          )
      parser.add_argument("draft", help="Path to the draft to check")
      parser.add_argument(
          "--json", action="store_true",
          help="Print the findings as JSON instead of as text. "
          "--write files it beside the report either way.",
      )
      parser.add_argument(
          "--write", action="store_true",
          help="Also write the report to content/review/, mirroring the "
          "draft's path. Off by default: printing is the usual use.",
      )
      parser.add_argument(
          "--formats", default="md,tex,pdf",
          help="Additional formats to render beside the Markdown report "
          "(default: md,tex,pdf). Needs pandoc/pdflatex on PATH.",
      )
      return parser


  def main(argv: list[str] | None = None) -> int:
      return run(build_parser().parse_args(argv))


  def run(args: argparse.Namespace) -> int:
      """Advisory: exits 0 whatever it finds, including when the
      enrichment layer is not installed at all -- an unbuilt optional
      check is not a failure, matching how tier 3 of the verbatim scan
      degrades."""
      try:
          draft_path = review.require_reviewable(Path(args.draft))
      except (FileNotFoundError, config.OutsideContentDir) as exc:
          print(exc, file=sys.stderr)
          return 1

      entailer, reason = entailment.open_entailer()
      if entailer is None:
          print(f"support: not run -- {reason}", file=sys.stderr)
          return 0

      report = build_report(draft_path, entailer)
      found = findings(report)

      if not (args.json or args.write):
          print(_render.format_report(report, found))
          return 0

      command = _command(draft_path, args.json, args.write)
      payload = support_payload(report, command)
      print(json.dumps(payload, indent=2) if args.json else _render.format_report(report, found))

      if args.write:
          formats = [f.strip() for f in args.formats.split(",") if f.strip()]
          written = review.write(
              draft_path, "support", _render.render_markdown(report, command, found), formats
          )
          written["json"] = review.write_json(draft_path, "support", payload)
          review.print_written(written, stream=sys.stderr if args.json else sys.stdout)
      return 0
  ```

  **Add these imports to `claim_support.py`'s existing top-of-file import block** (the one Task 2 created — do not create a second import block partway through the file):

  ```python
  from chitragupta.review import _claim_support_render as _render
  ```

  and change the two render calls above to `_render.format_report(...)` / `_render.render_markdown(...)` (avoids a name collision with this module's own `Report` type).

- [ ] **Step 5: Register in `review/__main__.py`**

  In `chitragupta/review/__main__.py`:

  ```python
  from chitragupta.review import (
      citation_coverage,
      citation_provenance,
      claim_support,
      figure_layout,
      synthesis,
      uncited_prose,
      verbatim_check,
  )

  AIDS = {
      "provenance": (citation_provenance, "what in the source supports this claim?"),
      "verbatim": (verbatim_check, "verbatim overlap with one source, or with the whole corpus"),
      "coverage": (citation_coverage, "retrieval surfaced it -- did the draft cite it?"),
      "synthesis": (synthesis, "how many sources does each unit of the draft rest on?"),
      "figure": (figure_layout, "what a TikZ figure's own geometry says about it"),
      "uncited": (uncited_prose, "which sentences of the draft carry no citation?"),
      "support": (claim_support, "does the cited source entail this claim?"),
  }
  ```

- [ ] **Step 6: Run the registration test**

  Run: `.venv/bin/pytest tests/test_review_claim_support.py::TestRegistration -v`
  Expected: PASS

- [ ] **Step 7: Write and pass the CLI/`--json`/`--write`/unavailable tests**

  ```python
  class TestCli:
      def test_run_prints_plain_text_by_default(self, isolated_config, capsys, monkeypatch):
          monkeypatch.setattr(entailment, "open_entailer", lambda: (FakeEntailer({}), None))
          draft = _draft(config, "No citations here.\n")
          args = claim_support.build_parser().parse_args([str(draft)])
          assert claim_support.run(args) == 0
          assert "Claim support" in capsys.readouterr().out

      def test_run_prints_json_and_writes(self, isolated_config, capsys, monkeypatch):
          monkeypatch.setattr(entailment, "open_entailer", lambda: (FakeEntailer({}), None))
          draft = _draft(config, "No citations here.\n")
          args = claim_support.build_parser().parse_args([str(draft), "--json", "--write"])
          assert claim_support.run(args) == 0
          out = capsys.readouterr().out
          payload = json.loads(out)
          assert payload["aid"] == "support"
          assert (config.REVIEW_DIR / "topic" / "draft.support.json").exists()

      def test_run_exits_0_and_says_why_when_unavailable(self, isolated_config, capsys, monkeypatch):
          monkeypatch.setattr(entailment, "open_entailer", lambda: (None, "not installed"))
          draft = _draft(config, "No citations here.\n")
          args = claim_support.build_parser().parse_args([str(draft)])
          assert claim_support.run(args) == 0
          assert "not installed" in capsys.readouterr().err

      def test_run_returns_1_for_a_missing_draft(self, isolated_config, capsys):
          args = claim_support.build_parser().parse_args(["content/drafts/nope.md"])
          assert claim_support.run(args) == 1
  ```

- [ ] **Step 8: Run full test file, confirm 100% coverage**

  Run: `.venv/bin/pytest tests/test_review_claim_support.py -v --cov=chitragupta.review.claim_support --cov-report=term-missing`
  Expected: PASS, 100% line+branch. Fill any gap with a targeted test (likely the `--formats` split, or the `render_output.MissingBinary` path already covered generically by `review.write`'s own tests — confirm it doesn't need re-covering here).

- [ ] **Step 9: Run the whole suite to confirm nothing else broke**

  Run: `.venv/bin/pytest --cov --cov-report=term-missing`
  Expected: PASS, 100% overall (the two AIDS dicts are the same size again, so `__main__`'s `RuntimeError` guard doesn't fire).

- [ ] **Step 10: Commit**

  ```bash
  git add chitragupta/review/claim_support.py chitragupta/review/__init__.py \
          chitragupta/review/__main__.py tests/test_review_claim_support.py
  git commit -m "Wire the claim-support aid into the review layer's CLI"
  ```

---

## Task 5: Documentation sweep (R10), the parts that don't depend on the measurement

**Scope note, added after Task 4's review:** Task 4's review ran the full suite before and after that task's commit and found registering the seventh aid breaks four cross-reference test files this plan's original Task 5 scope never covered — `tests/test_architecture_review_layer.py`, `tests/test_diagrams_in_sync.py`, `tests/test_features_doc.py`, `tests/test_packaging_command_table.py`, none of them optional (all part of the ordinary suite, not gated on the `enrich` extra). Ruling: these are exactly what R10's "and appears in AGENTS.md, CLI.md, the README tables and mkdocs.yml" sweep is *for* — the plan's original file list was simply incomplete relative to what the live suite actually enforces — so they're added to this task rather than spun into a new one. The file list and steps below are the corrected, complete scope; the version of this task that shipped without them was a plan defect, not a later task's problem.

**Files:**
- Modify: `AGENTS.md` (layer-4 bullet list, ~line 192-201)
- Modify: `docs/CLI.md` (TOC entry + new `### 🔬 chitragupta review support` section, alphabetically between `provenance` and `synthesis`)
- Modify: `docs/REVIEW.md` ("The six aids" → "The seven aids", new bullet)
- Modify: `README.md` ("six advisory aids" → "seven advisory aids", ~line 81-83)
- Modify: `docs/AUTO-IMPROVEMENT.md` (item-class table's `unsupported-claim` row Source column, ~line 117-124)
- Modify: `docs/ARCHITECTURE.md` (Layer 4 section's opening aid-count word, checked by `tests/test_architecture_review_layer.py`)
- Modify: `docs/FEATURES.md` (review-section aid list and stated count, checked by `tests/test_features_doc.py`)
- Modify: `docs/PACKAGING.md` (command-surface table's review row and its arithmetic breakdown, checked by `tests/test_packaging_command_table.py`)
- Modify: `tests/test_packaging_command_table.py` (`REVIEW_FLAT_AIDS` constant, line ~53 — this is a hand-maintained test fixture, not generated, and it does not currently include `"support"`)
- Modify: `docs/DIAGRAMS.md` (three fenced Mermaid blocks — `v3-artifacts`, `g1-corpus-led`, `extra-sequence` — whichever of their labels enumerate the review aids by name)
- Modify: `docs/diagrams/{v3-artifacts,g1-corpus-led,extra-sequence}.mmd` and `docs/diagrams/svg/{v3-artifacts,g1-corpus-led,extra-sequence}.svg` (re-rendered from the fenced blocks above, checked by `tests/test_diagrams_in_sync.py`)
- Modify: `chitragupta/review/__main__.py` (`DESCRIPTION` string, line ~92: "six read-only aids" → "seven")
- Modify: `chitragupta/review/__init__.py` (module docstring's "six"/"all six" occurrences describing the aid count, NOT `chitragupta/review/claim_support.py:36`'s "Advisory like the other six" — that one is correct as written, since it means the six *other* aids, and must not be touched)

- [ ] **Step 1: AGENTS.md layer-4 bullet**

  Add `chitragupta/review/claim_support.py` to the layer-4 module list, in the same style as the existing entries (path only, matching the existing bullet's format — read the surrounding lines first to match punctuation exactly).

- [ ] **Step 2: docs/CLI.md**

  Add `support` to the TOC (alphabetical: coverage, figure, provenance, **support**, synthesis, uncited, verbatim) and add a `### 🔬 chitragupta review support` section mirroring the `uncited` section's shape exactly: one-line description, advisory/exit-0 boilerplate sentence, a flag table (`-h/--help`, `<draft>`, `--json`, `--write`, `--formats` — no `--genre`, this aid has none), a `bash` usage example, and a paragraph on what `--json` adds to the envelope (`scored`, `unscoreable`, one `findings` object per citation — `id`, `line`, `citekey`, `claim`, `score`, `note`). Task 4's review flagged that `"scored"` counts *findings* and `"unscoreable"` counts *citekeys* — deliberately different units (a citekey cited twice that turns out unscoreable is one `unscoreable` entry but zero of the two findings count as scored) — state this distinction explicitly rather than implying they're the same kind of count.

- [ ] **Step 3: docs/REVIEW.md — the aid list**

  Change the section heading "The six aids" to "The seven aids", and add a new bolded-lead-in paragraph for `support` in the same voice as the existing six (see `uncited`'s paragraph as the template), placed after `uncited`'s. Contrast it explicitly against `provenance` — same underlying question (does the source support this claim), different mechanism (entailment model vs. lexical overlap) and different output shape (ranked, no bands).

  Do **not** write the "Limits" bullet yet — that is Task 8, after the measurement exists to inform it honestly.

- [ ] **Step 4: README.md**

  Change "six advisory aids... provenance, verbatim, coverage, synthesis, figure layout and uncited prose" to seven, adding "claim support" to the list in the same sentence.

- [ ] **Step 5: docs/AUTO-IMPROVEMENT.md's item-class table**

  The `unsupported-claim` row's Source column currently reads `provenance`. Change it to `provenance, support` — both aids now feed this class; `provenance` is not being retired.

- [ ] **Step 6: docs/ARCHITECTURE.md — Layer 4's aid count**

  `tests/test_architecture_review_layer.py::TestTheCountAgrees::test_it_matches_the_number_of_aids` reads the Layer 4 section (`## Layer 4: the review layer`, to the next `## `) and asserts it opens with `_NUMBER_WORDS[len(review.AIDS)]` — with `review.AIDS` now at 7 entries, that word is `"Seven"` (`_NUMBER_WORDS = {..., 6: "Six", 7: "Seven", ...}`, `tests/test_architecture_review_layer.py:46-57`). Find wherever the section currently states "Six aids" (or similar) and change it to "Seven". The companion test, `test_no_stale_count_survives_alongside_it`, fails if *any* other `"<word> aids"` phrase remains in the same section after the fix — so grep the whole Layer 4 section for other stale count words, not just the first one you find.

- [ ] **Step 7: docs/FEATURES.md — the review-section aid list and count**

  `tests/test_features_doc.py` parametrizes `test_it_is_named` over `sorted(review.AIDS)` and asserts `` `review {aid}` `` (backticked) appears in the document for every aid — add a `` `review support` `` mention. `test_the_stated_aid_count_matches` asserts the document says `"Seven advisory aids"` (again via `_NUMBER_WORDS`, this file's own copy at `tests/test_features_doc.py:36`) — update the stated count the same way as Step 6.

- [ ] **Step 8: docs/PACKAGING.md and its test fixture — the command-surface table**

  Two things move together here, and the test file is genuinely part of this task's file list, not generated from the doc:

  1. In `tests/test_packaging_command_table.py`, add `"support"` to `REVIEW_FLAT_AIDS` (line ~53): `REVIEW_FLAT_AIDS = {"provenance", "coverage", "synthesis", "figure", "uncited", "support"}`. This set is hand-maintained (the file's own docstring: "a hand-maintained structure here, cross-checked against the real `--help` output... and against docs/PACKAGING.md's own text") — it will not update itself.
  2. In `docs/PACKAGING.md`, add `support` to the review command's row/list of aids, and update the two arithmetic breakdowns `tests/test_packaging_command_table.py`'s `TestTheStatedBreakdownIsRight` class checks term-by-term (`test_the_stated_verb_total_matches_the_live_structures`, `test_the_stated_leaf_total_matches_the_live_structures`, and the two `..._breakdown_matches_it_term_by_term` tests) — these parse the *actual numbers* docs/PACKAGING.md states in prose, so both the total and the term-by-term list need the new aid counted in. Run `pytest tests/test_packaging_command_table.py -v` after editing and read any failure's message directly — each one states the exact pattern/number it expected, which is the fastest way to find every place the count needs to change.

- [ ] **Step 9: docs/DIAGRAMS.md and its exports — the three diagrams that enumerate the aids**

  `tests/test_diagrams_in_sync.py::TestTheReviewLayerDiagramsStayCurrent::test_it_names_every_aid` (parametrized over `["v3-artifacts", "g1-corpus-led", "extra-sequence"]`, per that file's own `NAMES`-derived subset) asserts every `sorted(review.AIDS)` name appears in each of these three fenced Mermaid blocks in `docs/DIAGRAMS.md`; `test_the_svg_carries_the_same_aids` asserts the same against the checked-in `.svg` exports.

  1. Find the three fenced blocks in `docs/DIAGRAMS.md` (search for the diagram titles in the "Editing these" table: "4. Everything on disk" → `v3-artifacts`, "Genre A: corpus-led" → `g1-corpus-led`, "Appendix: one draft, in time order" → `extra-sequence`) and add `support` wherever each block lists the review aids by name, matching that block's existing label style.
  2. Re-render both exports per `docs/DIAGRAMS.md`'s own "Editing these" section: `mmdc -i docs/diagrams/<name>.mmd -o docs/diagrams/svg/<name>.svg -b white -w 1900` for each of the three names — but first copy the edited fenced block into the `.mmd` file (`tests/test_diagrams_in_sync.py::test_the_mmd_is_the_block` checks the `.mmd` is byte-identical to the fenced block, title front matter aside, so the `.mmd` edit is not optional even though `mmdc` reads it as input). If bare `mmdc` fails or hangs in this environment, it needs a Puppeteer config enabling `--no-sandbox` (a known constraint on this class of host) — pass one via `mmdc`'s `-p`/`--puppeteerConfigFile` flag rather than assuming the bare command works.
  3. Confirm with `pytest tests/test_diagrams_in_sync.py -v` — note its own docstring's stated limit: SVG freshness is checked for *label text* only, not a full visual re-render, so this catches the missing-aid-name defect exactly but would not catch a layout-only drift.

- [ ] **Step 10: `chitragupta/review/__main__.py` and `chitragupta/review/__init__.py` — the stale "six" in live `--help` text and module docstrings**

  Task 4's review confirmed `python -m chitragupta.review --help` prints `chitragupta/review/__main__.py`'s `DESCRIPTION` string ("The review layer: six read-only aids over a finished draft. No gate.") directly above the seven listed subcommands — change "six" to "seven". Separately, `chitragupta/review/__init__.py`'s module docstring has several "six"/"all six" occurrences describing the aid count (its opening list of six module names, "all six are interpreter tier 1", "obey one output contract instead of six") — update the count and add `claim_support.py` to the opening list of module names, matching the existing list's style. **Do not touch** `chitragupta/review/claim_support.py:36`'s "Advisory like the other six" — that sentence is already correct (it means the six aids *other than* this one) and "fixing" it to "seven" would make it wrong.

  No test in the plan's earlier tasks (`test_review_claim_support.py`, `test_review_entrypoint.py`, `test_review.py`, `test_cli_help_is_short.py`) asserts the word "six" one way or the other, so this step is driven by the two files above being genuinely stale, not by a new failing test — verify by re-reading `python -m chitragupta.review --help`'s actual output after the edit.

- [ ] **Step 11: Run the docs checks and the full regression set this task exists to close**

  Run: `mkdocs build --strict` (from repo root; `docs_dir: .` per `mkdocs.yml`) and `markdownlint-cli2 "**/*.md"` (or whatever the project's existing lint invocation is — check `DEVELOPER-AGENTS.md`'s shipping-cycle section for the exact command). Expected: no new warnings/errors. No `mkdocs.yml` nav entry is needed — `support` has no dedicated doc page, matching the majority of the six existing aids (only `provenance` and `verbatim` have their own pages, via `docs/CITATION-PROVENANCE.md` and `docs/PLAGIARISM.md`).

  Then run the four test files Task 4's review found newly red, plus the full suite, to confirm this task actually closes the gap it exists to close:

  ```bash
  /workspace/.venv-full/bin/pytest tests/test_architecture_review_layer.py tests/test_diagrams_in_sync.py \
      tests/test_features_doc.py tests/test_packaging_command_table.py -v
  /workspace/.venv-full/bin/pytest -q
  ```

  Expected: all four pass, and the full run returns to exactly the documented 16-failure baseline (missing root `config.toml` in a worktree checkout) — no more, no fewer. If the full suite is not back at the 16-failure baseline after this task, the task is not done, regardless of how the individual files above look in isolation — this is the exact promise Task 4's own brief made and could not keep alone, because the fix lives in files outside that task's scope.

- [ ] **Step 12: Commit**

  ```bash
  git add AGENTS.md docs/CLI.md docs/REVIEW.md README.md docs/AUTO-IMPROVEMENT.md \
          docs/ARCHITECTURE.md docs/FEATURES.md docs/PACKAGING.md \
          docs/DIAGRAMS.md docs/diagrams/v3-artifacts.mmd docs/diagrams/g1-corpus-led.mmd docs/diagrams/extra-sequence.mmd \
          docs/diagrams/svg/v3-artifacts.svg docs/diagrams/svg/g1-corpus-led.svg docs/diagrams/svg/extra-sequence.svg \
          chitragupta/review/__main__.py chitragupta/review/__init__.py \
          tests/test_packaging_command_table.py
  git commit -m "Document the claim-support aid everywhere the review layer's aid count is checked"
  ```

---

## Task 6: Model-choice investigation and `docs/CONFIG.md`'s candidate table

**Files:**
- Modify: `docs/CONFIG.md` (new subsection, after "Choosing an embedding model")
- Modify: `chitragupta/config.py` (confirm/update `ENTAILMENT_MODEL`'s default from Task 1 step 1, if the investigation changes it)

This task is real investigation, run for real in `.venv-full`, not desk research — the table's numbers must come from actually loading each candidate, the same way `docs/CONFIG.md`'s existing embedding-model table states a resolution/verification date per entry.

- [ ] **Step 1: Load each candidate and record what actually happens**

  For each of these three candidates, in `.venv-full`:

  ```bash
  .venv-full/bin/python -c "
  from sentence_transformers import CrossEncoder
  m = CrossEncoder('<model-name>')
  print(m.model.config.id2label)
  print(m.model.num_parameters())
  import time
  pairs = [('The digital twin mirrors the physical asset in real time.',
            'A digital twin is a live mirror of a physical asset.')] * 8
  start = time.time()
  m.predict(pairs)
  print('elapsed', time.time() - start)
  "
  ```

  Run this for:
  - `cross-encoder/nli-deberta-v3-small` (candidate default from Task 1)
  - `cross-encoder/nli-deberta-v3-base` (larger, same family)
  - `cross-encoder/nli-MiniLM2-L6-H768` (smallest, different family)

  Record the real `id2label`, real parameter count, and real elapsed time for each — these are the table's actual numbers, not estimates.

- [ ] **Step 2: Record why the rejected candidates are rejected**

  Two rejects to write up from what you already know without downloading anything (API-shape rejections, not accuracy rejections):
  - `facebook/bart-large-mnli` and `MoritzLaurer/*` zero-shot-MNLI models: these are `transformers.pipeline("zero-shot-classification")` models, not `sentence_transformers.CrossEncoder`-wrapped ones. Using either would mean a second ML code path (`AutoModelForSequenceClassification` + a hand-rolled `(premise, hypothesis)` tokenization) alongside the `CrossEncoder` path `overlap_embed.py`'s sibling tier already established — duplicated surface for no accuracy case made yet.
  - Confirm, don't assume: `pip show sentence-transformers` in `.venv-full` and check whether it already vendors `CrossEncoder` for the three candidates above without any additional install — this is the "no new dependency" claim from the plan header, verified for real, not just for the one default model.

- [ ] **Step 3: Pick the default, update `chitragupta/config.py` if the choice changed from Task 1's placeholder**

  If the investigation confirms `cross-encoder/nli-deberta-v3-small` (smallest, fastest, real accuracy differences from `-base` likely marginal for this corpus's purposes — but write down the actual measured elapsed-time ratio from Step 1, don't guess it), leave `ENTAILMENT_MODEL`'s default as-is. If a different candidate wins on the real numbers, update the default and say why in a code comment, matching the dated-verification-comment convention every other `enrich`-gated dependency in `pyproject.toml` already follows.

- [ ] **Step 4: Write the `docs/CONFIG.md` table**

  Add a new subsection after "Choosing an embedding model": `## 🧠 Choosing an entailment model`, same two-part shape (a "Drop-in" table, a "Not without a code change first" list), same column intent as the embedding table but with "Size" (real parameter count from Step 1) in place of "Dimensions" — an entailment cross-encoder has no embedding dimensionality to report. Populate every cell from Step 1's and Step 2's real output; do not carry over the placeholder default-model row without its real numbers filled in.

- [ ] **Step 5: Commit**

  ```bash
  git add docs/CONFIG.md chitragupta/config.py
  git commit -m "Record the entailment model choice and rejected candidates in CONFIG.md"
  ```

---

## Task 7: `bench/bench_claim_support.py` — the measurement over real drafts

**Files:**
- Create: `bench/bench_claim_support.py`
- Create (by the script, at run time): `bench/results/<tag>/candidates.md`, `bench/results/<tag>/labels.json`, `bench/results/<tag>/crosscheck.json`

This mirrors `bench/bench_paraphrase_hunt.py`'s two-phase shape (`--extract` then a human judges, then `--crosscheck`) and `bench/bench_overlap_embed.py`'s `self_check()` convention (a script publishing a number must fabricate a difference and assert it sees it) — read both scripts in full before writing this one; do not reinvent either convention.

- [ ] **Step 1: Write `self_check()` against a small fabricated fixture**

  Create a graded fixture, `bench/fixtures/graded-claim-support.md`, with (at minimum) one paragraph whose citation's source passage clearly entails its claim, and one whose citation's source passage clearly does not (a fabricated near-contradiction) — plus the two corresponding parsed-source fixtures under a location this script controls (not `content/`, matching `[[memory: never-smoke-test-against-real-content]]`: never touch real content with a script still being developed). `self_check()` runs the real `entailment.open_entailer()` (skipping — not failing — if the enrich group isn't installed in whatever venv runs this check, matching `bench_overlap_embed.py`'s own `--fixture` gating) over just these two pairs and asserts the entailed pair scores higher than the contradicted one. This is the "fabricate a difference and assert it sees it" self-check — it validates the scorer's plumbing, not the aid's usefulness on real content.

- [ ] **Step 2: Write the `--extract` phase**

  Over `content/drafts/digital-twins-for-software-engineers/{survey,book-chapter,tutorial,deep-research}.md` (the four real drafts — name them explicitly, matching `chitragupta/review/_claims.py`'s own docstring precedent, not "the project's real drafts" as a placeholder): run `claim_support.build_report()` for each, collect every finding, and write `bench/results/<tag>/candidates.md` — the N lowest-scored and N highest-scored findings (a natural place to look for separation or its absence), each with its claim text, citekey, and matched passage excerpt, laid out for a human to read and judge.

- [ ] **Step 3: A human judges the extracted candidates**

  This step cannot be automated and must not be simulated — judging "is this claim actually supported by its source" for real citations in this project's real drafts is exactly the kind of judgment call this whole feature exists to keep human, and fabricating judgments to make the measurement look clean would defeat the measurement's purpose. Whoever executes this plan reads `candidates.md` and writes `bench/results/<tag>/labels.json`, one entry per candidate, `{"id": ..., "judgment": "supported" | "unsupported" | "unclear"}`, with a one-line reason each — same shape as `bench_paraphrase_hunt.py`'s `labels.json`.

- [ ] **Step 4: Write the `--crosscheck` phase**

  Reads `labels.json` back, compares the entailment score's ranking against the human judgment (e.g.: does the median score of `"supported"`-labeled findings exceed the median of `"unsupported"`-labeled ones? By how much? Is there overlap in the distributions?), and writes `bench/results/<tag>/crosscheck.json` plus a printed summary. Report the real numbers, whatever they are — including if they show no separation. That is a valid, expected result per the issue ("`it does not separate supported from unsupported on this corpus` is a result, not a failure to deliver"), not a bug to chase with a threshold tweak.

- [ ] **Step 5: Run it for real**

  ```bash
  .venv-full/bin/python bench/bench_claim_support.py --extract \
      --drafts content/drafts/digital-twins-for-software-engineers \
      --tag 2026-08-26-claim-support-measurement
  # judge candidates.md into labels.json
  .venv-full/bin/python bench/bench_claim_support.py --crosscheck \
      --tag 2026-08-26-claim-support-measurement
  ```

  Record the outcome (separation found, or not, with the real numbers) — this is the input to Task 9.

- [ ] **Step 6: Add an entry to `bench/RESULTS.md`**

  Following that file's existing entry format, summarizing the method and the real result (whichever it was).

- [ ] **Step 7: Commit**

  ```bash
  git add bench/bench_claim_support.py bench/fixtures/graded-claim-support.md \
          bench/results/2026-08-26-claim-support-measurement bench/RESULTS.md
  git commit -m "Measure whether claim-support checking separates supported from unsupported claims on the real corpus"
  ```

---

## Task 8: Finish the honest limits section, and the full pre-PR cycle

**Files:**
- Modify: `docs/REVIEW.md` ("Two limits worth knowing" → "Three limits worth knowing", new bullet)
- Modify: `chitragupta/review/_claim_support_render.py` (only if Task 7's real result changes what the report's own caveat paragraph should say — e.g. if separation genuinely was found, the "not proof either way" framing may need a sentence acknowledging that, without ever claiming a verdict)

- [ ] **Step 1: Write the third limits bullet from the real Task 7 result**

  In `docs/REVIEW.md`'s "Two limits worth knowing" section (renamed "Three"), add a bullet in the same voice as the existing two (`verbatim`'s and `coverage`'s), stating plainly what Task 7 actually found: either "this aid's score does not reliably separate supported from unsupported claims on this corpus, for the same retrieval-bias reason `docs/PLAGIARISM-DESIGN.md` records for tier 3 — read every score as a place to look, never a verdict" (if that's the real result), or the more confident version if real separation was measured, with the actual numbers from `crosscheck.json` cited by file path so a reader can check them.

- [ ] **Step 2: Be willing to conclude it is not worth keeping**

  If Task 7's result is a clean null (no separation at all, not even a weak trend), stop here and write that up as the PR's own conclusion rather than shipping the aid silently — per the issue's explicit instruction. This does **not** mean deleting the code: "surfaced, ranked, no verdict" was always the design regardless of measured separation (matching tier 3's own precedent, which ships and is used precisely because it's advisory, not despite a weak-discriminator problem). Record the conclusion in the PR description; do not soften it in the docs.

- [ ] **Step 3: Run the full suite and every linter**

  ```bash
  .venv-full/bin/pytest --cov --cov-report=term-missing
  .venv-full/bin/pylint chitragupta/ scripts/ tests/ .claude/hooks
  .venv-full/bin/ruff check .
  .venv-full/bin/ruff format --check .
  markdownlint-cli2 "**/*.md"
  poetry check
  ```

  Expected: all green, 100% coverage overall.

- [ ] **Step 4: End-to-end smoke test against the real stack**

  Per `DEVELOPER-AGENTS.md`'s rule for anything touching an `enrich`-gated module: run the real command against real content, not just mocks.

  ```bash
  .venv-full/bin/python -m chitragupta.review support \
      content/drafts/digital-twins-for-software-engineers/survey.md
  ```

  Confirm it prints a real report with real scores (or the real "not run" message if the enrich group isn't actually installed in this environment) and exits 0.

- [ ] **Step 5: Bump the version**

  A new review aid is a MINOR bump per `DEVELOPER-AGENTS.md`'s versioning rule. Check `main` for the currently-owed version first (`[[memory: chitragupta-pr-stack]]` — two PRs picking the same version merge silently and lose the bump).

- [ ] **Step 6: OpenCodeReview, then PR, following `DEVELOPER-AGENTS.md`'s shipping cycle exactly**

  Run `delegate-review` before opening the PR. It cannot review Markdown, so the docs sweep (Tasks 5, 6, 8) needs a manual read-through in addition. Open the PR with `gh pr create`, body via `--body-file`, and follow the remaining shipping-cycle steps (CI green, Copilot review resolved — noting `[[memory: copilot-reviewer-unavailable]]` if it doesn't resolve — re-check `main` hasn't moved, squash-merge via `scripts/merge_pr.py`, tag, confirm release).

- [ ] **Step 7: Commit the final docs change**

  ```bash
  git add docs/REVIEW.md chitragupta/review/_claim_support_render.py
  git commit -m "Record what the real measurement found in REVIEW.md's limits section"
  ```

---

## Self-Review

**Spec coverage** — checked against the issue's own bullet list:
- "A new module under `chitragupta/review/`, behind the `enrich` extra... reusing `chitragupta/sentences.py`" — Tasks 1-2 (reused transitively via `citation_provenance.claims()`, which is itself built on `sentences.py`; verified, not assumed, in the research this plan is based on).
- "Registration in both AIDS dicts, R2's stable finding `id`, `--json` with no timestamp, and R10's sweep" — Task 4 (dicts, id, json), Task 5 (sweep).
- "Model choice documented in docs/CONFIG.md's candidate-model table shape, with the rejected candidates and why" — Task 6.
- "Tests to the 100% bar with a stub scorer" — Tasks 1-4, throughout.
- "An honest limits section in docs/REVIEW.md" — Task 8, informed by Task 7's real measurement.
- "report a measurement over the project's own real drafts" — Task 7.
- "Be willing to conclude it is not worth keeping" — Task 8, Step 2.

**Placeholder scan** — the only two intentionally-deferred facts are Task 1 Step 0 (the exact `id2label`/softmax behavior, which the step itself resolves by running real code) and Task 6 (the real candidate-model numbers, which that task's own steps resolve by running real code) — neither is a "TBD" left for someone else; each is a concrete command whose output the same task consumes.

**Type consistency** — `Report.findings: list[Finding]`, `Finding.passage: Passage | None` (from `chitragupta.passages`), `findings(report) -> list[dict]` with keys `id/line/citekey/claim/score/note` used identically in Task 2 (build), Task 3 (render), Task 4 (JSON payload) and Task 8 (nothing new). `entailment.Entailer.score(pairs: list[tuple[str, str]]) -> list[float]` is the one signature every task after Task 1 depends on and none of them redefines it differently.
