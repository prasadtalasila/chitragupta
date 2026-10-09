# 📋 Verbatim digest: a sixth genre and an eleventh review aid (#991)

> **For agentic workers:** REQUIRED SUB-SKILL: use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to carry out this plan task by task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **designed, unbuilt.** Written 2026-10-09 against `main` at
`8b588b5` (#1039), for
[discussion 991](https://github.com/prasadtalasila/chitragupta/discussions/991).
One PR, one MINOR bump (`6.138.0` → `6.139.0`).

**Written for** whoever builds #991: a session that changes
`chitragupta/review/`, `chitragupta/dossier/__init__.py`,
`chitragupta/review/_units.py`, `tests/`, the three skill trees,
`.gitignore` and `docs/`, and so is governed by `DEVELOPER-AGENTS.md`
and `docs/CODE-STANDARDS.md`. Every path below is from the repository
root.

**Assumed:** you have read the discussion itself (the goals, the
constraints, the component table, the classification rules, the
trade-off table and the four open questions), `docs/REVIEW.md`,
`docs/AGENDA.md`, `chitragupta/review/quotation.py` with
`_quotation_match.py` beside it, and `chitragupta/review/agenda/`
(`_identity.py`, `_recheck.py`, `__init__.py`'s `run`).

**Not covered here:** the NLI `support` tier for `unsupported-text`
(open question 4, declined below), a PDF render of the digest itself
(open question 3, declined below), and any change to `agenda`,
`agenda-reviser`, the five genre skills, the evidence sidecar or the
gate: the discussion rules those out and this plan keeps them
byte-identical except where a count they state becomes false.

**Goal:** a person can ask for a verbatim digest of a topic, get
`content/drafts/<topic>/<name>.digest.md` written mostly in the cited
papers' own words, and run `python -m chitragupta.review digest` on it
to see the copied fraction, every sentence that is not verified source
text, and whether a repair pass made that list shorter.

**Architecture:** one new genre (`digest` in `dossier.GENRES`, with a
`verbatim-digest-writer` skill per harness), one new review aid
(`chitragupta/review/verbatim_digest.py` plus four `_digest_*.py`
helpers), registered in `review.AIDS` and `review/_registry.AIDS` and
deliberately excluded from what `agenda` reads. The aid splits the
digest into citation-terminated runs, matches each run against the
cited source with `_quotation_match.locate`, drops to sentence level
only where a run breaks, and classifies what is left as
`unsupported-text`, `copy-mismatch` or `unquoted-text`, all
`[surfaced]`. `--baseline` compares a run against an earlier `.json`.

**Tech stack:** stdlib Python (interpreter tier 1, like every other
aid), pytest at 100% line and branch coverage, Markdown skill files in
three harness copies, `.opencode/opencode.json`.

**Spec:** discussion #991. This plan argues from it; read both.

## 🧭 Table of contents

- [Decisions this plan makes](#-decisions-this-plan-makes)
- [Global constraints](#-global-constraints)
- [File structure](#-file-structure)
- [Review focus](#-review-focus)
- [Task 1: `_claims.claim_blocks`, a seam the digest parser needs](#task-1-_claimsclaim_blocks-a-seam-the-digest-parser-needs)
- [Task 2: `_digest_runs.py`, the digest as citation-terminated runs](#task-2-_digest_runspy-the-digest-as-citation-terminated-runs)
- [Task 3: `_digest_match.py`, verification and the three classes](#task-3-_digest_matchpy-verification-and-the-three-classes)
- [Task 4: `_digest_render.py`, items, Markdown and the JSON payload](#task-4-_digest_renderpy-items-markdown-and-the-json-payload)
- [Task 5: `_digest_recheck.py`, `--baseline`](#task-5-_digest_recheckpy---baseline)
- [Task 6: `verbatim_digest.py`, the CLI, and registration](#task-6-verbatim_digestpy-the-cli-and-registration)
- [Task 7: the `digest` genre](#task-7-the-digest-genre)
- [Task 8: the ignore rule](#task-8-the-ignore-rule)
- [Task 9: the `verbatim-digest-writer` skill, three copies](#task-9-the-verbatim-digest-writer-skill-three-copies)
- [Task 10: documentation and the count sweep](#task-10-documentation-and-the-count-sweep)
- [Task 11: version, full checks, PR](#task-11-version-full-checks-pr)
- [Self-review against #991](#-self-review-against-991)

## ⚖ Decisions this plan makes

Each answers something the discussion left open or did not say. Where
a decision contradicts the discussion's wording it says so and why.

| Decision | Chosen | Why, and the alternative |
| --- | --- | --- |
| **Names** (open question 1) | Skill `verbatim-digest-writer`; aid key `digest`; module `chitragupta/review/verbatim_digest.py`; report label "Verbatim digest" | The discussion's own names. `review digest` reads as the other ten do, and the `.digest.md` report suffix is the one word that is not already an aid suffix |
| **Draft path and report path** | Draft `content/drafts/<topic>/<name>.digest.md`; report `content/review/<topic>/<name>.digest.md` + `.json`, exactly the discussion's mapping | `review.report_path` composes `<stem>.<aid>.md`, and the stem of `notes.digest.md` is `notes.digest`, which would file `notes.digest.digest.md`. The aid therefore hands `review.write`/`write_json` a sibling path with the `.digest` infix stripped (`report_target`, Task 6) and the real path to `header`/`envelope`. A draft not named `*.digest.md` is still accepted and files under the ordinary rule (`survey.md` → `survey.digest.md`), so the mapping is one rule either way. Changing `report_path` itself was rejected: `review/__init__.py` is at the C2 ceiling and the rule is right for the other ten |
| **Writes unconditionally** | `.md` and `.json` are filed on every run, as `agenda` does; `--json` only picks stdout; `--formats` as every aid | The `.json` is the next pass's `--baseline`, which is the reason `agenda` has no `--write` flag either (`agenda/__init__.py`'s `run` docstring) |
| **Page mismatch** (open question 2) | A note on the copied span (`cited p. 4-5, found on p. 7`), never a class | The three classes are what a person watches fall. A page note is a correction to make, not unsupported text, and a fourth count would dilute the metric the feature exists to minimise |
| **Rendering** (open question 3) | Markdown only. The report renders through `--formats` like every aid; the digest itself is not rendered by the skill | Private study notes. `python -m chitragupta.draft render` still works on the file if anyone wants a PDF, with no change needed |
| **Support tier** (open question 4) | Lexical only: `citation_provenance.score_claim` under `config.PROVENANCE_WEAK_SCORE`, the provenance aid's own weak band | Reuses a threshold that already ships and is already documented. `review support` can be run on a digest by hand today. An NLI tier is a later issue |
| **`copy-mismatch` boundary** | `MISMATCH_SHARE = 0.8`: a sentence `locate` cannot find whose distinctive words are at least 80% present on one page of the source | The discussion says "nearly matches" and names no number. `near_miss` already computes this share; the constant is published with its reason and is not to be tuned (docs/CODE-STANDARDS.md R3). Below it the sentence is the drafter's own and is `unquoted-text` |
| **A sentence is its own whole** | A finding carries the whole sentence; a half-copied sentence is a `copy-mismatch` with the missing words listed | The discussion's stated con. Splitting a sentence into copied and original halves is a second matcher this plan does not build |
| **Several citekeys in one bracket** | `[@a; @b]` closes one run matched against the union of both sources' passages; items carry every key, the id uses the first | One run, one citation, as the attribution rule says; the drafter who copied from two papers under one bracket gets the second paper's text as unmatched, which is the con the discussion records |
| **A citation anywhere closes a run** | The run ends at the bracket wherever it sits, even mid-sentence; what follows starts the next run | One rule with no special case. The skill writes citations at the end of a sentence, so the mid-sentence case is a drafting error the report will show as a broken run |
| **`agenda` does not read it** | `digest` joins `agenda` and `union` in `agenda/_sources.AID_NAMES`'s exclusion, and `TestAidNames` is updated to say so | Required by the discussion, and `AID_NAMES` is derived from `review.AIDS`, so without the exclusion every existing agenda would gain a "digest: read" line and `--baseline` would run the digest aid live. `_sources.py`'s comment asks an eleventh aid to decide; this is the decision |
| **Genre tables** | `_units.UNITS["digest"] = "document"`, `_units.UNCITED_PROSE["digest"] = "ordinary"` | Both tables are pinned to `dossier.GENRES` by tests. The multi-source rule is about fused prose and a digest fuses nothing, so the whole document is its unit, as for a tutorial. Connective sentences carry no citation by design, so uncited prose is ordinary; the digest aid is what judges them |
| **No prose check, no verbatim scan, no critique step in the skill** | The skill is named in `_HELPERS` of the style and verbatim-scan step scans and in `_EXCLUDED_SKILLS` of the pre-gate critique scan, each with its reason | A digest is verbatim by design: `verbatim scan` would flag every run, `draft style` would ask the drafter to restyle a source's wording, and the critique loop is about `claim:`/`quote:` packets a digest does not draft from. The acronym-vocabulary scan lists its skills by name and is left as is |
| **Item identity** | `agenda/_identity.item_id("digest", cls, section, first citekey, sentence)` and `section_anchor`, imported | The one place agenda items get an id, written so extractors cannot each invent a convention; a copy here would be exactly that, and `tests/test_duplicate_helper_scan.py` exists to catch it |
| **`review/__init__.py` at the C2 ceiling** | `require_reviewable` and `report_dir` move to `chitragupta/review/_paths.py` and are re-imported into `review/__init__.py` under their names | The module holds 250 code lines today and `AIDS` needs one more. The split is forced by the task and lands at the boundary the module's own docstring draws ("where a report goes" / "what it looks like"); `report_path` stays because it needs `AIDS`. No caller changes |
| **No sample-project report** | `docs/examples/sample-project/content/review/` gains nothing | A digest is never tracked (Task 8), so its report would document a file that cannot be committed; REVIEW.md's sentence about the sample set gets the exception named |

## 🔒 Global constraints

- A citekey appears in a test, a doc or the skill only if it is one the
  repository already uses in fixtures (`shao_analysis_2023`,
  `smith_example_2024`) or is a plainly synthetic one in a fixture that
  writes its own source text. Never a plausible real key (CLAUDE.md).
- Every check reports and exits 0. `review digest` returns 1 only for a
  draft the layer will not read and 2 only for a malformed invocation,
  the codes `chitragupta/review/__main__.py` documents. Nothing here is a
  gate, and nothing may be promoted to one.
- `chitragupta/` modules: at most 250 code lines each, at most 25
  statements per function, stdlib only, no `__main__` block in an aid
  module (`tests/test_review_entrypoint.py`). Measure with
  `python scripts/code_standards.py <path>` before committing a module.
- 100% line and branch coverage, enforced by `fail_under = 100`.
- The three `SKILL.md` copies are identical after
  `tests/fixtures/skill_harness_phrases.toml`'s substitutions and the
  `-opencode` suffix; the new skill names no harness tool, so it needs
  no phrase entry.
- Version: `6.139.0` in `pyproject.toml` (MINOR: a new module and a new
  subcommand).
- `python -m chitragupta.draft gate` runs on every digest, unchanged.

## 🗂 File structure

| Path | Status | Responsibility |
| --- | --- | --- |
| `chitragupta/review/_claims.py` | modify | gains `claim_blocks(text)`, the per-block half of `claim_sentences`, so the digest parser reads the same blocks the other aids do |
| `chitragupta/review/_digest_runs.py` | create | `Run`; `runs(text)` splits each claim-bearing block at its citation brackets into citation-terminated runs and an uncited tail; `cited_pages` |
| `chitragupta/review/_digest_match.py` | create | `Span`, `Finding`, `Checked`; `check_run` verifies one run against its sources and classifies what fails; `MISMATCH_SHARE`, `CLASSES` |
| `chitragupta/review/_digest_render.py` | create | `items` (ids, anchors, order), `payload`, `render_markdown` |
| `chitragupta/review/_digest_recheck.py` | create | `load_baseline`, `compare`, `recheck_command`, `recheck_payload`, `format_recheck` |
| `chitragupta/review/verbatim_digest.py` | create | `build_parser`, `run`, `build_report`, `report_target`, `INFIX` |
| `chitragupta/review/_paths.py` | create | `require_reviewable`, `report_dir`, moved out of `review/__init__.py` unchanged |
| `chitragupta/review/__init__.py` | modify | `AIDS["digest"]`; imports the two moved functions; docstring counts |
| `chitragupta/review/_registry.py` | modify | `AIDS["digest"]` |
| `chitragupta/review/__main__.py` | modify | docstring entry, `DESCRIPTION` count |
| `chitragupta/review/agenda/_sources.py` | modify | `AID_NAMES` excludes `digest`; comment |
| `chitragupta/dossier/__init__.py` | modify | `GENRES` gains `digest` |
| `chitragupta/review/_units.py` | modify | `UNITS` and `UNCITED_PROSE` gain `digest` |
| `tests/test_review_digest_runs.py` | create | Task 2 |
| `tests/test_review_digest_match.py` | create | Task 3 |
| `tests/test_review_digest.py` | create | Tasks 4, 5, 6, 8 (render, recheck, CLI, ignore rule) |
| `tests/test_review_claims.py` or the existing `tests/test_review_uncited.py` | modify | one test for `claim_blocks` |
| `tests/test_review_agenda.py`, `tests/test_review_units.py`, `tests/test_review_uncited.py`, `tests/test_architecture_review_layer.py`, `tests/test_features_doc.py`, `tests/test_skill_frontmatter.py`, `tests/test_skill_verbatim_scan_step.py`, `tests/test_skill_style_check_step.py`, `tests/test_skill_pregate_feedback_step.py` | modify | counts and exclusion sets, each named in the task that moves it |
| `.claude/skills/verbatim-digest-writer/SKILL.md`, `.agents/skills/verbatim-digest-writer/SKILL.md`, `.opencode/skills/verbatim-digest-writer-opencode/SKILL.md` | create | the genre skill |
| `.opencode/opencode.json` | modify | deny `verbatim-digest-writer` |
| `.gitignore` | modify | `content/drafts/**/*.digest.md` |
| `docs/VERBATIM-DIGEST.md` | create | the guide |
| `docs/REVIEW.md`, `docs/CLI.md`, `docs/GENRE.md`, `docs/FEATURES.md`, `docs/GLOSSARY.md`, `docs/DOSSIER.md`, `docs/WRITING-PROCESS.md`, `docs/ARCHITECTURE.md`, `docs/DIAGRAMS.md` + `docs/diagrams/00-main-workflow.mmd` + its SVG, `docs/CONFIG.md`, `docs/PERFORMANCE.md`, `AGENTS.md`, `README.md`, `DEVELOPER.md`, `mkdocs.yml`, `config.toml.example`, `docs/examples/*/config.toml`, `bench/bench_review_cost.py` | modify | Task 10 |
| `pyproject.toml` | modify | version |

## 🔍 Review focus

Inputs the discussion implies and a person will meet; each has its test
in the task named.

1. **A digest whose block ends with a citation and nothing after it**
   (the common case) must produce no uncited tail: an empty trailing
   segment is dropped, not reported as an empty `unquoted-text`.
   Task 2, `test_a_block_ending_in_a_citation_has_no_tail`.
2. **A citation bracket that is not a citation** (`[see 3]`, `[sic]`,
   a `[@label]` example reference) must not close a run.
   Task 2, `test_a_bracket_without_a_citekey_does_not_close_a_run`.
3. **A cited source with only page-level text** (a rung-3 parse) must
   land in `unverifiable` with a reason, and its words must count
   toward the total and never toward copied or toward a finding.
   Task 3, `test_a_source_without_reading_order_is_unverifiable`.
4. **A baseline that is another aid's `.json`** (the likeliest typo,
   `notes.agenda.json`) must be refused with exit 2 before any work.
   Task 5, `test_another_aids_payload_is_refused`; Task 6,
   `test_a_bad_baseline_exits_two_before_reading_the_ledger`.
5. **An empty digest or one with no runs at all** must report a copied
   fraction of 0.0 rather than divide by zero, and exit 0.
   Task 3, `test_an_empty_digest_has_fraction_zero`; Task 6,
   `test_a_digest_with_no_prose_exits_zero`.

---

### Task 1: `_claims.claim_blocks`, a seam the digest parser needs

`_claims.claim_sentences` already decides which blocks of a draft carry
a claim: code blanked, headings, captions, comments and table headers
excluded, the reference list cut off. The digest parser needs those same
blocks *before* they are split into sentences, because a citation
bracket is what splits a digest block, not a full stop. Expose the block
half as a public function and rebuild `claim_sentences` on it. No
behaviour changes.

**Files:**

- Modify: `chitragupta/review/_claims.py:186-225`
- Test: `tests/test_review_uncited.py` (the file that already covers
  `_claims`)

**Interfaces:**

- Produces: `claim_blocks(text: str) -> list[tuple[int, list[str], str]]`,
  one `(first line, raw lines, prose text)` per claim-bearing block in
  document order. `claim_sentences` keeps its signature and output.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_review_uncited.py`:

```python
class TestClaimBlocks:
    def test_yields_the_blocks_claim_sentences_is_built_from(self):
        """`claim_blocks` is the per-block half of `claim_sentences`:
        headings and the reference list are out, prose paragraphs are in,
        and the raw lines are the draft's own so a caller can map an
        offset back to a line."""
        text = (
            "# Title\n\nFirst para one. First para two.\n\n"
            "## Second\n\nSecond para [@smith_example_2024].\n\n"
            "## References\n\n[1] S. Smith, 2024.\n"
        )
        blocks = _claims.claim_blocks(text)
        assert [(line, prose) for line, _, prose in blocks] == [
            (3, "First para one. First para two."),
            (7, "Second para [@smith_example_2024]."),
        ]
        assert blocks[0][1] == ["First para one. First para two."]
        assert [s.text for s in _claims.claim_sentences(text)] == [
            "First para one.",
            "First para two.",
            "Second para [@smith_example_2024].",
        ]
```

Add `from chitragupta.review import _claims` to the imports if the file
does not already have it.

- [ ] **Step 2: Run it, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_uncited.py -k TestClaimBlocks -v
```

Expected: FAIL, `AttributeError: module ... has no attribute 'claim_blocks'`.

- [ ] **Step 3: Implement**

Replace `claim_sentences` in `chitragupta/review/_claims.py` with:

```python
def claim_blocks(text: str) -> list[tuple[int, list[str], str]]:
    """(first line, raw lines, prose text) for every block of `text`
    that carries a claim, in document order.

    The per-block half of `claim_sentences`, exposed on its own because
    the verbatim digest (`_digest_runs.py`) splits a block at its
    citation brackets rather than at sentence boundaries, and it must
    read exactly the blocks every other aid reads -- code blanked,
    headings and captions out, the reference list cut -- or two aids
    would disagree about what the draft's prose is.
    """
    lines = _body(text)
    found = []
    for start, end, block in _blocks.spans(lines):
        after = lines[end] if end < len(lines) else ""
        raw_block = lines[start - 1 : end]
        if block.strip() and not _excluded(raw_block, after):
            found.append((start, raw_block, block))
    return found


def claim_sentences(text: str) -> list[Sentence]:
    """Every sentence of `text` that carries a claim, in document order.

    The split is `chitragupta/sentences.py`'s, shared with tier 3 of the
    overlap scan and with `citation_provenance` -- C1's roadmap entry
    asks for a splitter "somewhere C2 can reuse it", and that module has
    been it since before C1 was planned. The blocks are `claim_blocks`,
    so a table row and a list item are each their own claim rather than
    fragments of one paragraph, and a block left empty by stripping its
    list marker is no claim at all.
    """
    found = []
    for start, raw_block, block in claim_blocks(text):
        block_cites = bool(citation_gate.extract_citekeys(block))
        for sent_start, sent_end in sentences.spans(block):
            found.append(
                Sentence(
                    _blocks.line_of_offset(start, raw_block, sent_start),
                    block[sent_start:sent_end],
                    bool(citation_gate.extract_citekeys(block[sent_start:sent_end])),
                    block_cites,
                )
            )
    return found
```

- [ ] **Step 4: Run the file and the uncited/provenance suites**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_uncited.py tests/test_citation_provenance.py -q
```

Expected: all pass, and `python scripts/code_standards.py
chitragupta/review/_claims.py` reports nothing.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/review/_claims.py tests/test_review_uncited.py
git commit -m "Expose the claim-bearing blocks of a draft as _claims.claim_blocks"
```

---

### Task 2: `_digest_runs.py`, the digest as citation-terminated runs

**Files:**

- Create: `chitragupta/review/_digest_runs.py`
- Test: `tests/test_review_digest_runs.py`

**Interfaces:**

- Consumes: `_claims.claim_blocks`, `_blocks.line_of_offset`,
  `sentences.spans`, `citation_gate.extract_citekeys_from_line`.
- Produces:

```python
@dataclass(frozen=True)
class Run:
    line: int                      # first line of the run's first sentence
    sentences: tuple[str, ...]     # the run's sentences, bracket excluded
    citekeys: tuple[str, ...]      # () for an uncited tail
    citation: str | None           # the bracket as written, None for a tail
    pages: tuple[int, int] | None  # the locator hint, (first, last)
    text -> str                    # sentences joined with one space
    words -> int                   # len(text.split())

def runs(text: str) -> list[Run]
def cited_pages(citation: str) -> tuple[int, int] | None
```

- [ ] **Step 1: Write the failing tests**

`tests/test_review_digest_runs.py`:

```python
"""chitragupta/review/_digest_runs.py: a verbatim digest read as runs.

The draft format has no markup: copied text is ordinary prose and a
citation ends each copied run (discussion #991). The attribution rule is
that a citation covers every sentence back to the previous citation, or
to the start of the block. These tests pin that rule, and the two
shapes it has to survive: a block that ends in a citation with nothing
after it, and a bracket that only looks like a citation.
"""

from chitragupta.review import _digest_runs as runs_mod

KEY = "shao_analysis_2023"
OTHER = "smith_example_2024"


def test_a_citation_covers_back_to_the_previous_citation():
    text = (
        "# Notes\n\n"
        f"One. Two. Three. [@{KEY}, p. 4-5]\n"
        "A connecting sentence of my own.\n"
        f"Four. [@{OTHER}, p. 12]\n"
    )
    found = runs_mod.runs(text)
    assert [(r.sentences, r.citekeys, r.pages) for r in found] == [
        (("One.", "Two.", "Three."), (KEY,), (4, 5)),
        (("A connecting sentence of my own.", "Four."), (OTHER,), (12, 12)),
    ]
    assert found[0].citation == f"[@{KEY}, p. 4-5]"
    assert found[0].text == "One. Two. Three."
    assert found[0].words == 3


def test_a_block_ending_in_a_citation_has_no_tail():
    text = f"Copied sentence. [@{KEY}]\n"
    assert [r.citekeys for r in runs_mod.runs(text)] == [(KEY,)]


def test_sentences_after_the_last_citation_are_an_uncited_tail():
    text = f"Copied. [@{KEY}] My own closing thought. And another.\n"
    found = runs_mod.runs(text)
    assert found[1].citekeys == ()
    assert found[1].citation is None
    assert found[1].pages is None
    assert found[1].sentences == ("My own closing thought.", "And another.")


def test_a_block_with_no_citation_is_one_uncited_run():
    found = runs_mod.runs("Only my words here. Two of them.\n")
    assert len(found) == 1 and found[0].citekeys == ()


def test_a_bracket_without_a_citekey_does_not_close_a_run():
    text = f"Shown [see 3] earlier. More [sic] text. [@{KEY}]\n"
    found = runs_mod.runs(text)
    assert len(found) == 1
    assert found[0].sentences == ("Shown [see 3] earlier.", "More [sic] text.")


def test_several_citekeys_in_one_bracket_close_one_run():
    found = runs_mod.runs(f"Copied. [@{KEY}; @{OTHER}]\n")
    assert found[0].citekeys == (KEY, OTHER)


def test_a_mid_sentence_citation_closes_the_run_there():
    found = runs_mod.runs(f"The first half [@{KEY}] and the rest.\n")
    assert [r.sentences for r in found] == [("The first half",), ("and the rest.",)]


def test_lines_are_the_drafts_own():
    text = f"# Title\n\nLine three. [@{KEY}]\n\nLine five. [@{OTHER}]\nLine six.\n"
    assert [r.line for r in runs_mod.runs(text)] == [3, 5, 6]


def test_headings_code_and_the_reference_list_are_not_runs():
    text = (
        "# Title\n\n```\nnot [@fake_key_2020] prose\n```\n\n"
        f"Real. [@{KEY}]\n\n## References\n\n[1] Entry.\n"
    )
    assert [r.sentences for r in runs_mod.runs(text)] == [("Real.",)]


class TestCitedPages:
    def test_a_range(self):
        assert runs_mod.cited_pages("[@k, pp. 4-5]") == (4, 5)

    def test_a_single_page(self):
        assert runs_mod.cited_pages("[@k, p. 12]") == (12, 12)

    def test_an_en_dash_and_reversed_order(self):
        assert runs_mod.cited_pages("[@k, p. 9–7]") == (7, 9)

    def test_no_locator(self):
        assert runs_mod.cited_pages("[@k]") is None
```

- [ ] **Step 2: Run, expect failure**

Run: `.venv-full/bin/python -m pytest tests/test_review_digest_runs.py -q`
Expected: FAIL at import, no module `_digest_runs`.

- [ ] **Step 3: Implement**

`chitragupta/review/_digest_runs.py`:

```python
"""A verbatim digest read as citation-terminated runs (#991).

The digest format carries no markup: copied text is ordinary prose and a
citation ends each copied run. The attribution rule is the whole of this
module -- **a citation covers every sentence back to the previous
citation, or to the start of the block** -- so a block is split at its
citation brackets, not at its sentence boundaries, and each piece is
then sentence-split for the fallback `_digest_match.py` needs when a
run is not found whole.

The blocks are `_claims.claim_blocks`', so a heading, a caption, a code
fence and the reference list are read the way every other aid reads
them. A bracket counts as a citation only if the citekey extractor finds
a key in it: `[see 3]` and `[sic]` leave a run open.

What follows the last citation in a block is a run with no citekeys --
the drafter's own tail -- and a block with no citation at all is one such
run. A citation with nothing before it (two brackets in a row) covers
nothing and is dropped.

Stdlib only, interpreter tier 1 like the aid that reads it.
"""

import re
from dataclasses import dataclass

from chitragupta import citation_gate, sentences
from chitragupta.review import _blocks, _claims

# A bracket holding at least one `@`. Whether it is a citation is the
# extractor's call, not this pattern's.
_BRACKET = re.compile(r"\[[^\[\]]*@[^\[\]]*\]")

# `p. 4`, `pp. 4-5`, `page 4`, `pages 4–5`. The hint pandoc passes
# through as a locator; the aid treats it as a hint and reports the page
# the text was actually found on.
_PAGES = re.compile(r"\b(?:pp?\.|pages?)\s*(\d+)(?:\s*[-–—]+\s*(\d+))?")


@dataclass(frozen=True)
class Run:
    """One citation-terminated run, or the uncited tail of a block."""

    line: int
    sentences: tuple[str, ...]
    citekeys: tuple[str, ...]
    citation: str | None
    pages: tuple[int, int] | None

    @property
    def text(self) -> str:
        return " ".join(self.sentences)

    @property
    def words(self) -> int:
        return len(self.text.split())


def cited_pages(citation: str) -> tuple[int, int] | None:
    """`(first, last)` from the bracket's page locator, or None."""
    match = _PAGES.search(citation)
    if match is None:
        return None
    first = int(match.group(1))
    last = int(match.group(2)) if match.group(2) else first
    return (min(first, last), max(first, last))


def _segments(block: str) -> list[tuple[int, str, str | None]]:
    """`(offset, text, citation)` per piece of `block`: the text before
    each citation bracket with that bracket, then whatever trails the
    last one with None."""
    found, at = [], 0
    for match in _BRACKET.finditer(block):
        if not citation_gate.extract_citekeys_from_line(match.group(0)):
            continue
        found.append((at, block[at : match.start()], match.group(0)))
        at = match.end()
    found.append((at, block[at:], None))
    return found


def runs(text: str) -> list[Run]:
    """Every run of `text`, in document order."""
    found = []
    for start, raw_block, block in _claims.claim_blocks(text):
        for offset, segment, citation in _segments(block):
            spans = sentences.spans(segment)
            if not spans:
                continue
            keys = tuple(citation_gate.extract_citekeys_from_line(citation)) if citation else ()
            found.append(
                Run(
                    _blocks.line_of_offset(start, raw_block, offset + spans[0][0]),
                    tuple(segment[a:b] for a, b in spans),
                    keys,
                    citation,
                    cited_pages(citation) if citation else None,
                )
            )
    return found
```

- [ ] **Step 4: Run, expect pass; measure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest_runs.py -q && python scripts/code_standards.py chitragupta/review/_digest_runs.py
```

Expected: all pass, no C1/C2 finding. If
`test_a_mid_sentence_citation_closes_the_run_there` fails on a trailing
space in the first sentence, the tightening in `sentences.spans` has
changed; the expected tuple is the stripped sentence.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/review/_digest_runs.py tests/test_review_digest_runs.py
git commit -m "Read a verbatim digest as citation-terminated runs"
```

---

### Task 3: `_digest_match.py`, verification and the three classes

**Files:**

- Create: `chitragupta/review/_digest_match.py`
- Test: `tests/test_review_digest_match.py`

**Interfaces:**

- Consumes: `Run` from Task 2; `_quotation_match.locate(quote, passages)`
  → `(tier, pages) | None`; `_quotation_match.near_miss(quote, passages)`
  → `(share, page)`; `citation_provenance.score_claim(claim, passages)`
  → `(score, passage)`; `passages.distinctive(text)` → `set[str]`;
  `config.PROVENANCE_WEAK_SCORE`.
- Produces:

```python
MISMATCH_SHARE = 0.8
CLASSES = ("unsupported-text", "copy-mismatch", "unquoted-text")   # worst first

@dataclass(frozen=True)
class Span:      # verified copied text
    line: int; citekeys: tuple[str, ...]; text: str; tier: str
    pages: tuple[int, ...]; cited: tuple[int, int] | None; note: str | None

@dataclass(frozen=True)
class Finding:
    cls: str; line: int; text: str; citekeys: tuple[str, ...]; detail: dict

@dataclass
class Checked:
    spans: list[Span]; findings: list[Finding]; unverifiable: list[dict]; words_total: int
    words_copied -> int; copied_fraction -> float

Lookup = Callable[[str], tuple[list[Passage], str | None]]
def check_run(run: Run, lookup: Lookup, checked: Checked) -> None
def page_note(cited, pages) -> str | None
```

- [ ] **Step 1: Write the failing tests**

`tests/test_review_digest_match.py`:

```python
"""chitragupta/review/_digest_match.py: is this run really in the source,
and what is each sentence that is not?

Four outcomes per run, in the order the module tries them: found whole
(one span), every sentence found separately (one span, "assembled"),
some sentences found (spans for those, findings for the rest), and a
source that cannot be checked at all. The three finding classes are the
discussion's: `copy-mismatch` for a sentence most of whose words are on
one page, `unquoted-text` for everything else the drafter wrote, and
`unsupported-text` on top of that where the cited source does not
lexically support it, or nothing cites it.
"""

import pytest

from chitragupta import config
from chitragupta.passages import Passage, distinctive
from chitragupta.review import _digest_match as match
from chitragupta.review._digest_runs import Run

KEY = "shao_analysis_2023"

SOURCE_P4 = (
    "Layered twins separate the physical entity from its models. "
    "Each layer exposes one interface to the next."
)
SOURCE_P7 = "Operators can start developing against the interface alone."


def passage(page: int, text: str) -> Passage:
    return Passage(page, distinctive(text), text)


def a_lookup(*passages: Passage, reason: str | None = None):
    calls = []

    def lookup(citekey: str):
        calls.append(citekey)
        return list(passages), reason

    lookup.calls = calls
    return lookup


def a_run(*sentences: str, citekeys=(KEY,), pages=None, line=3) -> Run:
    citation = f"[@{KEY}]" if citekeys else None
    return Run(line, tuple(sentences), tuple(citekeys), citation, pages)


def test_a_run_found_whole_is_one_span_and_no_finding():
    checked = match.Checked()
    run = a_run(
        "Layered twins separate the physical entity from its models.",
        "Each layer exposes one interface to the next.",
        pages=(4, 4),
    )
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert checked.findings == []
    assert len(checked.spans) == 1
    span = checked.spans[0]
    assert (span.tier, span.pages, span.note) == ("exact", (4,), None)
    assert checked.words_total == run.words
    assert checked.words_copied == run.words
    assert checked.copied_fraction == 1.0


def test_a_page_hint_the_text_is_not_on_becomes_a_note():
    checked = match.Checked()
    run = a_run("Operators can start developing against the interface alone.", pages=(4, 5))
    match.check_run(run, a_lookup(passage(7, SOURCE_P7)), checked)
    assert checked.spans[0].note == "cited p. 4-5, found on p. 7"


def test_sentences_found_in_different_places_are_one_assembled_span():
    checked = match.Checked()
    run = a_run(
        "Each layer exposes one interface to the next.",
        "Operators can start developing against the interface alone.",
    )
    match.check_run(run, a_lookup(passage(4, SOURCE_P4), passage(7, SOURCE_P7)), checked)
    assert checked.findings == []
    assert len(checked.spans) == 1
    assert checked.spans[0].pages == (4, 7)
    assert checked.spans[0].note == "assembled from 2 places"


def test_a_nearly_matching_sentence_is_a_copy_mismatch_naming_the_missing_words():
    checked = match.Checked()
    run = a_run("Layered twins separate the physical entity from its blueprints.")
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [f.cls for f in checked.findings] == ["copy-mismatch"]
    finding = checked.findings[0]
    assert finding.detail["page"] == 4
    assert finding.detail["missing"] == ["blueprints"]
    assert finding.detail["share"] >= match.MISMATCH_SHARE
    assert checked.spans == []


def test_the_drafters_own_supported_sentence_is_unquoted_only():
    checked = match.Checked()
    # Mostly the source's words, but below MISMATCH_SHARE: a paraphrase.
    run = a_run("Twins that are layered keep the physical entity apart from models of it.")
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [f.cls for f in checked.findings] == ["unquoted-text"]


def test_an_unsupported_sentence_carries_both_classes(monkeypatch):
    monkeypatch.setattr(config, "PROVENANCE_WEAK_SCORE", 0.5)
    checked = match.Checked()
    run = a_run("Pelicans migrate in autumn along the coast.")
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [f.cls for f in checked.findings] == ["unquoted-text", "unsupported-text"]
    assert checked.findings[1].detail["support_score"] < 0.5


def test_an_uncited_tail_is_unquoted_and_unsupported_without_a_lookup():
    checked = match.Checked()
    lookup = a_lookup(passage(4, SOURCE_P4))
    match.check_run(a_run("My own closing thought.", citekeys=()), lookup, checked)
    assert [f.cls for f in checked.findings] == ["unquoted-text", "unsupported-text"]
    assert lookup.calls == []
    assert checked.findings[0].citekeys == ()


def test_a_mixed_run_keeps_the_found_sentences_as_spans():
    checked = match.Checked()
    run = a_run(
        "Each layer exposes one interface to the next.",
        "Pelicans migrate in autumn along the coast.",
    )
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [s.text for s in checked.spans] == ["Each layer exposes one interface to the next."]
    assert [f.cls for f in checked.findings] == ["unquoted-text", "unsupported-text"]
    assert checked.words_copied == 8
    assert checked.words_total == run.words


def test_a_source_without_reading_order_is_unverifiable():
    checked = match.Checked()
    page_only = Passage(4, distinctive(SOURCE_P4), None)
    run = a_run("Layered twins separate the physical entity from its models.")
    match.check_run(run, a_lookup(page_only), checked)
    assert checked.spans == [] and checked.findings == []
    assert checked.unverifiable == [
        {
            "line": 3,
            "citekeys": [KEY],
            "words": run.words,
            "reason": f"{KEY}: no reading-ordered passages -- only page-level text",
        }
    ]
    assert checked.words_total == run.words


def test_a_citekey_the_ledger_lacks_carries_the_lookups_reason():
    checked = match.Checked()
    lookup = a_lookup(reason="not in the ledger -- run `python -m chitragupta.corpus sync`")
    match.check_run(a_run("Anything."), lookup, checked)
    assert checked.unverifiable[0]["reason"].startswith(f"{KEY}: not in the ledger")


def test_two_citekeys_pool_their_passages():
    checked = match.Checked()
    seen = {}

    def lookup(citekey):
        seen[citekey] = True
        return ([passage(4, SOURCE_P4)] if citekey == KEY else [passage(2, SOURCE_P7)]), None

    run = Run(
        3,
        ("Operators can start developing against the interface alone.",),
        (KEY, "smith_example_2024"),
        f"[@{KEY}; @smith_example_2024]",
        None,
    )
    match.check_run(run, lookup, checked)
    assert set(seen) == {KEY, "smith_example_2024"}
    assert checked.spans[0].pages == (2,)
    assert checked.spans[0].citekeys == (KEY, "smith_example_2024")


def test_an_empty_digest_has_fraction_zero():
    assert match.Checked().copied_fraction == 0.0


class TestPageNote:
    @pytest.mark.parametrize(
        ("cited", "pages", "expected"),
        [
            (None, [4], None),
            ((4, 5), [], None),
            ((4, 5), [5], None),
            ((4, 4), [7], "cited p. 4, found on p. 7"),
            ((4, 5), [7, 8], "cited p. 4-5, found on p. 7, 8"),
        ],
    )
    def test_notes_only_a_disagreement(self, cited, pages, expected):
        assert match.page_note(cited, pages) == expected
```

- [ ] **Step 2: Run, expect failure**

Run: `.venv-full/bin/python -m pytest tests/test_review_digest_match.py -q`
Expected: FAIL at import.

- [ ] **Step 3: Implement**

`chitragupta/review/_digest_match.py`:

```python
"""Is each run of a verbatim digest really in the source it cites, and
what is every sentence that is not? (#991)

**The run is the unit; the sentence is the diagnosis.** A run that
`_quotation_match.locate` finds whole is one copied span and raises
nothing. Only a run that is not found whole is split into sentences,
and only to show where it breaks: a sentence found on its own is still
copied; one whose distinctive words are mostly on one page is a
`copy-mismatch` naming the words that are not; anything else is the
drafter's own, `unquoted-text`, and additionally `unsupported-text`
when no citation covers it or the cited source does not support it
lexically -- the provenance aid's own `score_claim` under the same
`PROVENANCE_WEAK_SCORE` it bands on.

`MISMATCH_SHARE` is the one number here and it is not tuned: it is the
share `near_miss` already reports, read as "most of the sentence is on
that page". docs/CODE-STANDARDS.md's R3 bars optimising it, and the
honest statement is that no corpus has been measured against it yet.

A source with no reading-ordered passages cannot be checked. Its run is
`unverifiable`, counted in the total and nowhere else -- never `absent`
after a failed comparison, the same refusal `quotation.py` makes.

Stdlib only, interpreter tier 1.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from chitragupta import config
from chitragupta.passages import Passage, distinctive
from chitragupta.review import _quotation_match
from chitragupta.review._digest_runs import Run
from chitragupta.review.citation_provenance import score_claim

# Worst first: the order the report lists classes in, and the order a
# repair pass works them.
CLASSES = ("unsupported-text", "copy-mismatch", "unquoted-text")

# A sentence `locate` cannot find, at least this share of whose
# distinctive words sit on one page, is a copy that drifted rather than
# the drafter's own words.
MISMATCH_SHARE = 0.8

_NO_READING_ORDER = "no reading-ordered passages -- only page-level text"

Lookup = Callable[[str], tuple[list[Passage], str | None]]


@dataclass(frozen=True)
class Span:
    """Verified copied text: a whole run, or one sentence of a broken one."""

    line: int
    citekeys: tuple[str, ...]
    text: str
    tier: str
    pages: tuple[int, ...]
    cited: tuple[int, int] | None
    note: str | None


@dataclass(frozen=True)
class Finding:
    cls: str
    line: int
    text: str
    citekeys: tuple[str, ...]
    detail: dict = field(default_factory=dict)


@dataclass
class Checked:
    spans: list[Span] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    unverifiable: list[dict] = field(default_factory=list)
    words_total: int = 0

    @property
    def words_copied(self) -> int:
        return sum(len(span.text.split()) for span in self.spans)

    @property
    def copied_fraction(self) -> float:
        """The headline metric: verified copied words over all words.
        0.0 for a digest with no words, which is a number rather than a
        crash and reads as what it is."""
        return round(self.words_copied / self.words_total, 3) if self.words_total else 0.0


def page_note(cited: tuple[int, int] | None, pages: list[int] | tuple[int, ...]) -> str | None:
    """`cited p. A-B, found on p. X` when no found page is in the hint's
    range; None when there is no hint, no page, or agreement."""
    if cited is None or not pages:
        return None
    first, last = cited
    if any(first <= page <= last for page in pages):
        return None
    hint = f"p. {first}" if first == last else f"p. {first}-{last}"
    return f"cited {hint}, found on p. {', '.join(str(page) for page in pages)}"


def _span(run: Run, text: str, tier: str, pages: list[int]) -> Span:
    return Span(run.line, run.citekeys, text, tier, tuple(pages), run.pages, page_note(run.pages, pages))


def _own(run: Run, sentence: str, passages: list[Passage]) -> list[Finding]:
    """`unquoted-text`, plus `unsupported-text` when nothing cites the
    sentence or its cited sources do not lexically support it."""
    found = [Finding("unquoted-text", run.line, sentence, run.citekeys)]
    score, passage = score_claim(sentence, passages) if run.citekeys else (0.0, None)
    if score < config.PROVENANCE_WEAK_SCORE:
        detail = {"support_score": round(score, 3), "page": passage.page if passage else None}
        found.append(Finding("unsupported-text", run.line, sentence, run.citekeys, detail))
    return found


def _mismatch(run: Run, sentence: str, quotable: list[Passage]) -> Finding | None:
    """A `copy-mismatch` finding, or None when the sentence is not mostly
    on any one page."""
    share, page = _quotation_match.near_miss(sentence, quotable)
    if share < MISMATCH_SHARE:
        return None
    on_page: set[str] = set().union(*(p.words for p in quotable if p.page == page))
    detail = {"page": page, "share": round(share, 3), "missing": sorted(distinctive(sentence) - on_page)}
    return Finding("copy-mismatch", run.line, sentence, run.citekeys, detail)


def _sentence_level(run: Run, quotable: list[Passage], passages: list[Passage], checked: Checked) -> None:
    """The diagnosis for a run not found whole."""
    spans, findings = [], []
    for sentence in run.sentences:
        located = _quotation_match.locate(sentence, quotable)
        if located is not None:
            spans.append(_span(run, sentence, *located))
            continue
        mismatch = _mismatch(run, sentence, quotable)
        findings.extend([mismatch] if mismatch else _own(run, sentence, passages))
    if not findings and len(spans) > 1:
        # Every sentence is in the source, just not contiguously: one
        # copied span, with where it came from. Information, not a finding.
        pages = sorted({page for span in spans for page in span.pages})
        places = len({span.pages for span in spans})
        note = f"assembled from {places} places"
        spans = [Span(run.line, run.citekeys, run.text, "assembled", tuple(pages), run.pages, note)]
    checked.spans.extend(spans)
    checked.findings.extend(findings)


def _sources(run: Run, lookup: Lookup) -> tuple[list[Passage], list[Passage], list[str]]:
    """Every passage the run's citekeys reach, the quotable ones, and one
    reason per citekey that has none."""
    passages, quotable, reasons = [], [], []
    for citekey in run.citekeys:
        found, reason = lookup(citekey)
        readable = [p for p in found if p.quotable]
        passages.extend(found)
        quotable.extend(readable)
        if not readable:
            reasons.append(f"{citekey}: {reason or _NO_READING_ORDER}")
    return passages, quotable, reasons


def check_run(run: Run, lookup: Lookup, checked: Checked) -> None:
    """Verify one run and record the outcome on `checked`."""
    checked.words_total += run.words
    if not run.citekeys:
        for sentence in run.sentences:
            checked.findings.extend(_own(run, sentence, []))
        return
    passages, quotable, reasons = _sources(run, lookup)
    if not quotable:
        checked.unverifiable.append(
            {"line": run.line, "citekeys": list(run.citekeys), "words": run.words, "reason": "; ".join(reasons)}
        )
        return
    located = _quotation_match.locate(run.text, quotable)
    if located is not None:
        checked.spans.append(_span(run, run.text, *located))
        return
    _sentence_level(run, quotable, passages, checked)
```

- [ ] **Step 4: Run, expect pass; measure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest_match.py -q && python scripts/code_standards.py chitragupta/review/_digest_match.py
```

Expected: all pass, no finding. If
`test_the_drafters_own_supported_sentence_is_unquoted_only` reports
`copy-mismatch`, the paraphrase shares too many distinctive words; swap
more content words, not the constant. If
`test_an_unsupported_sentence_carries_both_classes` reports only
`unquoted-text`, lower nothing: the pelican sentence shares no
distinctive word with the source and must score 0.0.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/review/_digest_match.py tests/test_review_digest_match.py
git commit -m "Verify each run of a verbatim digest against its source"
```

---

### Task 4: `_digest_render.py`, items, Markdown and the JSON payload

**Files:**

- Create: `chitragupta/review/_digest_render.py`
- Test: `tests/test_review_digest.py` (new; this task starts it)

**Interfaces:**

- Consumes: `Checked`, `Span`, `Finding`, `CLASSES` from Task 3;
  `agenda._identity.item_id`, `section_anchor`; `dossier.sections`;
  `review.header`, `review.envelope`.
- Produces:

```python
def items(checked: Checked, draft_text: str) -> list[dict]
    # {"id", "class", "disposition": "surfaced", "section", "citekeys", "line", "summary", "detail"}
    # ordered by CLASSES, then line, then id
def payload(draft: Path, command: str, checked: Checked, rows: list[dict]) -> dict
    # envelope + copied_fraction, words_total, words_copied, counts, items, spans, unverifiable
def render_markdown(draft: Path, command: str, checked: Checked, rows: list[dict]) -> str
```

- [ ] **Step 1: Write the failing tests**

`tests/test_review_digest.py` (first part; Tasks 5, 6 and 8 append):

```python
"""chitragupta/review/verbatim_digest.py and its render/recheck halves:
the eleventh review aid, over a verbatim digest.

A digest is private study text written mostly in the sources' own words
(discussion #991). The aid reports the copied fraction, lists every
sentence that is not verified source text as a `[surfaced]` item in the
agenda's own line format, and under `--baseline` says whether a repair
pass left fewer of them. Advisory like the other ten: exit 0 whatever
it finds, no lock, no draft blocked.
"""

import json
from pathlib import Path

import pytest

from chitragupta import config, ledger, review
from chitragupta.review import __main__ as review_main
from chitragupta.review import _digest_match as match
from chitragupta.review import _digest_recheck as recheck
from chitragupta.review import _digest_render as render
from chitragupta.review import verbatim_digest
from chitragupta.review._digest_runs import Run
from tests.test_review_units import draft_at

KEY = "shao_analysis_2023"
SOURCE = (
    "Layered twins separate the physical entity from its models. "
    "Each layer exposes one interface to the next."
)


@pytest.fixture(autouse=True)
def _a_synced_ledger(isolated_config):
    """An empty, current ledger: the aid reads read-only (#843) and a
    missing one is refused, so every test has to say it synced."""
    ledger.connect().close()


def a_source(citekey: str, *records: tuple[int, str]) -> Path:
    """A rung-2 passage sidecar: reading-ordered text with a page each."""
    path = config.PARSED_DIR / f"{citekey}.passages.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([{"text": t, "page": p, "label": "text"} for p, t in records]),
        encoding="utf-8",
    )
    return path


def a_digest(body: str, name: str = "notes.digest.md") -> Path:
    draft = draft_at(name)
    draft.write_text(body, encoding="utf-8")
    return draft


DIGEST = (
    "# Layered twins\n\n"
    "## Layers\n\n"
    f"Layered twins separate the physical entity from its models. [@{KEY}, p. 4]\n"
    "My own bridge sentence about pelicans.\n"
    f"Each layer exposes one interface to the next. [@{KEY}, p. 4]\n"
    "And a closing thought of mine.\n"
)


def a_checked() -> match.Checked:
    checked = match.Checked()
    run = Run(5, ("Layered twins separate the physical entity from its models.",), (KEY,), f"[@{KEY}, p. 4]", (4, 4))
    checked.spans.append(match.Span(5, (KEY,), run.text, "exact", (4,), (4, 4), None))
    checked.findings.append(match.Finding("unquoted-text", 6, "My own bridge sentence about pelicans.", (KEY,)))
    checked.findings.append(
        match.Finding("unsupported-text", 6, "My own bridge sentence about pelicans.", (KEY,), {"support_score": 0.0, "page": None})
    )
    checked.findings.append(match.Finding("unquoted-text", 8, "And a closing thought of mine.", ()))
    checked.findings.append(match.Finding("unsupported-text", 8, "And a closing thought of mine.", (), {"support_score": 0.0, "page": None}))
    checked.words_total = 25
    return checked


class TestItems:
    def test_one_item_per_finding_worst_class_first_then_by_line(self):
        rows = render.items(a_checked(), DIGEST)
        assert [(r["class"], r["line"]) for r in rows] == [
            ("unsupported-text", 6),
            ("unsupported-text", 8),
            ("unquoted-text", 6),
            ("unquoted-text", 8),
        ]
        assert all(r["disposition"] == "surfaced" for r in rows)
        assert rows[0]["section"] == "Layers"
        assert rows[0]["citekeys"] == [KEY]
        assert rows[1]["citekeys"] == []

    def test_ids_are_twelve_hex_characters_and_stable_across_runs(self):
        first = [r["id"] for r in render.items(a_checked(), DIGEST)]
        second = [r["id"] for r in render.items(a_checked(), DIGEST)]
        assert first == second
        assert all(len(i) == 12 and int(i, 16) >= 0 for i in first)
        assert len(set(first)) == 4

    def test_a_copy_mismatch_summary_names_the_missing_words(self):
        checked = match.Checked()
        checked.findings.append(
            match.Finding("copy-mismatch", 5, "Layered twins separate the physical entity from its blueprints.", (KEY,), {"page": 4, "share": 0.9, "missing": ["blueprints"]})
        )
        (row,) = render.items(checked, DIGEST)
        assert "missing: blueprints" in row["summary"]
        assert "p. 4" in row["summary"]


class TestPayload:
    def test_carries_the_envelope_the_metric_and_the_counts(self):
        draft = a_digest(DIGEST)
        data = render.payload(draft, "cmd", a_checked(), render.items(a_checked(), DIGEST))
        assert data["aid"] == "digest" and data["draft"] == str(draft) and data["command"] == "cmd"
        assert data["notice"] == review.notice()
        assert data["words_total"] == 25 and data["words_copied"] == 9
        assert data["copied_fraction"] == 0.36
        assert data["counts"] == {"unsupported-text": 2, "copy-mismatch": 0, "unquoted-text": 2}
        assert data["spans"] == [
            {"line": 5, "citekeys": [KEY], "text": "Layered twins separate the physical entity from its models.", "tier": "exact", "pages": [4], "cited": [4, 4], "note": None}
        ]
        assert data["unverifiable"] == []
        assert len(data["items"]) == 4

    def test_is_json_serialisable(self):
        draft = a_digest(DIGEST)
        json.dumps(render.payload(draft, "cmd", a_checked(), render.items(a_checked(), DIGEST)))


class TestMarkdown:
    def test_opens_with_the_header_and_states_the_metric(self):
        draft = a_digest(DIGEST)
        checked = a_checked()
        text = render.render_markdown(draft, "cmd", checked, render.items(checked, DIGEST))
        assert text.startswith(f"# Verbatim digest: {draft}\n")
        assert review.BANNER in text
        assert "- Copied fraction: 0.36 (9 of 25 words)" in text
        assert "- unsupported-text: 2" in text

    def test_item_lines_use_the_agendas_format(self):
        checked = a_checked()
        rows = render.items(checked, DIGEST)
        text = render.render_markdown(a_digest(DIGEST), "cmd", checked, rows)
        assert f"- `{rows[0]['id']}` [surfaced] (Layers): {rows[0]['summary']}" in text

    def test_lists_copied_spans_and_unverifiable_runs(self):
        checked = a_checked()
        checked.unverifiable.append({"line": 9, "citekeys": [KEY], "words": 4, "reason": f"{KEY}: no reading-ordered passages -- only page-level text"})
        text = render.render_markdown(a_digest(DIGEST), "cmd", checked, render.items(checked, DIGEST))
        assert "## Copied spans" in text and f"line 5, `{KEY}`, p. 4, exact" in text
        assert "## Not checkable" in text and "line 9" in text

    def test_a_clean_digest_says_so(self):
        checked = match.Checked()
        text = render.render_markdown(a_digest(DIGEST), "cmd", checked, [])
        assert "No findings." in text
        assert "- Copied fraction: 0.0 (0 of 0 words)" in text

    def test_carries_no_date(self):
        import datetime

        text = render.render_markdown(a_digest(DIGEST), "cmd", match.Checked(), [])
        assert str(datetime.date.today().year) not in text.replace(review.version(), "")
```

- [ ] **Step 2: Run, expect failure**

Run: `.venv-full/bin/python -m pytest tests/test_review_digest.py -q`
Expected: FAIL at import (`_digest_recheck`, `_digest_render`,
`verbatim_digest` missing). Create empty placeholder modules only for
`_digest_recheck.py` and `verbatim_digest.py` for now (a module
docstring line each; Tasks 5 and 6 fill them) so the render tests can
run. Delete nothing later; they are overwritten.

- [ ] **Step 3: Implement**

`chitragupta/review/_digest_render.py`:

```python
"""How the verbatim digest aid prints and serialises what it found (#991).

The report is the digest's own worklist. Item lines use `agenda`'s
format -- a stable 12-character id, `[surfaced]`, the section anchor,
a one-line summary -- so a person who has read an agenda reads this
without learning a second shape, and so the ids survive a revision the
way agenda's do: `_identity.item_id` hashes the sentence, never its
line. Every item is `[surfaced]`: whether a source backs a sentence and
which passage should replace it are judgement calls, and nothing a
re-run can settle.

The payload is the findings as data, in `review.envelope`'s frame, and
it is what the next run's `--baseline` reads. No timestamp, for the
reason `review/__init__.py` gives.
"""

from pathlib import Path

from chitragupta import dossier, review
from chitragupta.review._digest_match import CLASSES, Checked, Finding
from chitragupta.review.agenda._identity import item_id, section_anchor

AID = "digest"

# How much of a sentence an item line shows. The payload carries the
# whole sentence in `detail.text`; the line is for scanning.
_EXCERPT = 90


def _excerpt(text: str) -> str:
    return text if len(text) <= _EXCERPT else text[: _EXCERPT - 3].rstrip() + "..."


def _summary(finding: Finding) -> str:
    quoted = f'"{_excerpt(finding.text)}"'
    if finding.cls == "copy-mismatch":
        missing = ", ".join(finding.detail["missing"]) or "(none)"
        return f"{quoted} -- nearly on p. {finding.detail['page']}; missing: {missing}"
    if finding.cls == "unsupported-text" and not finding.citekeys:
        return f"{quoted} -- no citation covers it"
    if finding.cls == "unsupported-text":
        return f"{quoted} -- lexical support {finding.detail['support_score']} in the cited source"
    return f"{quoted} -- not verified as copied"


def items(checked: Checked, draft_text: str) -> list[dict]:
    """One worklist row per finding, worst class first, then by line."""
    sections = dossier.sections(draft_text)
    rows = []
    for finding in checked.findings:
        section = section_anchor(sections, finding.line)
        citekey = finding.citekeys[0] if finding.citekeys else None
        rows.append(
            {
                "id": item_id(AID, finding.cls, section, citekey, finding.text),
                "class": finding.cls,
                "disposition": "surfaced",
                "section": section,
                "citekeys": list(finding.citekeys),
                "line": finding.line,
                "summary": _summary(finding),
                "detail": {"text": finding.text, **finding.detail},
            }
        )
    rows.sort(key=lambda row: (CLASSES.index(row["class"]), row["line"], row["id"]))
    return rows


def _counts(rows: list[dict]) -> dict[str, int]:
    return {cls: sum(1 for row in rows if row["class"] == cls) for cls in CLASSES}


def payload(draft: Path, command: str, checked: Checked, rows: list[dict]) -> dict:
    data = review.envelope(draft, AID, command)
    data.update(
        {
            "copied_fraction": checked.copied_fraction,
            "words_total": checked.words_total,
            "words_copied": checked.words_copied,
            "counts": _counts(rows),
            "items": rows,
            "spans": [
                {
                    "line": span.line,
                    "citekeys": list(span.citekeys),
                    "text": span.text,
                    "tier": span.tier,
                    "pages": list(span.pages),
                    "cited": list(span.cited) if span.cited else None,
                    "note": span.note,
                }
                for span in checked.spans
            ],
            "unverifiable": list(checked.unverifiable),
        }
    )
    return data


def _summary_lines(checked: Checked, rows: list[dict]) -> list[str]:
    lines = [
        "## Summary",
        "",
        f"- Copied fraction: {checked.copied_fraction} "
        f"({checked.words_copied} of {checked.words_total} words)",
        f"- Copied spans: {len(checked.spans)}",
        f"- Not checkable: {len(checked.unverifiable)} runs",
    ]
    lines += [f"- {cls}: {count}" for cls, count in _counts(rows).items()]
    return lines + [""]


def _findings_lines(rows: list[dict]) -> list[str]:
    lines = ["## Findings", ""]
    if not rows:
        return lines + ["No findings.", ""]
    for cls in CLASSES:
        rows_of = [row for row in rows if row["class"] == cls]
        if not rows_of:
            continue
        lines += [f"### {cls}", ""]
        for row in rows_of:
            where = f" ({row['section']})" if row["section"] else ""
            lines.append(f"- `{row['id']}` [surfaced]{where}: {row['summary']}")
        lines.append("")
    return lines


def _spans_lines(checked: Checked) -> list[str]:
    lines = ["## Copied spans", ""]
    for span in checked.spans:
        pages = ", ".join(str(page) for page in span.pages) or "?"
        keys = ", ".join(f"`{key}`" for key in span.citekeys)
        note = f" -- {span.note}" if span.note else ""
        lines.append(f'- line {span.line}, {keys}, p. {pages}, {span.tier}{note}: "{_excerpt(span.text)}"')
    if not checked.spans:
        lines.append("None.")
    lines.append("")
    if checked.unverifiable:
        lines += ["## Not checkable", ""]
        lines += [f"- line {run['line']}: {run['reason']} ({run['words']} words)" for run in checked.unverifiable]
        lines.append("")
    return lines


def render_markdown(draft: Path, command: str, checked: Checked, rows: list[dict]) -> str:
    lines = review.header(draft, AID, command)
    lines += [
        "Every item is **[surfaced]**: whether a source backs a sentence, and",
        "which passage should replace it, are judgement calls. The copied",
        "fraction and the per-class counts are what a repair pass drives.",
        "",
    ]
    lines += _summary_lines(checked, rows)
    lines += _findings_lines(rows)
    lines += _spans_lines(checked)
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Run, expect pass; measure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py -q -k "TestItems or TestPayload or TestMarkdown" && python scripts/code_standards.py chitragupta/review/_digest_render.py
```

Expected: all pass, no finding.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/review/_digest_render.py chitragupta/review/_digest_recheck.py chitragupta/review/verbatim_digest.py tests/test_review_digest.py
git commit -m "Render the verbatim digest report and its JSON payload"
```

---

### Task 5: `_digest_recheck.py`, `--baseline`

**Files:**

- Create: `chitragupta/review/_digest_recheck.py` (replacing the placeholder)
- Test: `tests/test_review_digest.py` (append)

**Interfaces:**

- Consumes: a `payload` dict from Task 4 (`items`, `counts`,
  `copied_fraction`).
- Produces:

```python
def load_baseline(path) -> dict                # ValueError when unusable
def compare(payload: dict, baseline: dict) -> dict
    # {"resolved": [item], "persisting": [item], "new": [item],
    #  "counts_before": {cls: n}, "counts_after": {cls: n},
    #  "copied_before": float, "copied_after": float,
    #  "fell": bool}   # every class count <= before, at least one strictly less, and no new item
def recheck_command(draft, baseline) -> str
def recheck_payload(draft, baseline, comparison) -> dict
def format_recheck(baseline, comparison) -> str
```

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_review_digest.py`:

```python
def a_payload(draft: Path, *findings: match.Finding, total: int = 20) -> dict:
    checked = match.Checked()
    checked.findings.extend(findings)
    checked.words_total = total
    return render.payload(draft, "cmd", checked, render.items(checked, DIGEST))


class TestLoadBaseline:
    def test_reads_a_digest_payload_back(self, tmp_path):
        data = a_payload(a_digest(DIGEST))
        path = tmp_path / "notes.digest.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert recheck.load_baseline(path)["aid"] == "digest"

    def test_an_unreadable_path_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="Cannot read the baseline"):
            recheck.load_baseline(tmp_path / "missing.json")

    def test_non_json_is_refused(self, tmp_path):
        path = tmp_path / "x.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="not valid JSON"):
            recheck.load_baseline(path)

    def test_another_aids_payload_is_refused(self, tmp_path):
        path = tmp_path / "notes.agenda.json"
        path.write_text(json.dumps({"aid": "agenda", "items": [], "command": "x"}), encoding="utf-8")
        with pytest.raises(ValueError, match="not a digest payload"):
            recheck.load_baseline(path)


class TestCompare:
    def test_resolved_persisting_new_by_id_and_the_counts(self):
        draft = a_digest(DIGEST)
        gone = match.Finding("unquoted-text", 6, "Gone sentence.", (KEY,))
        stays = match.Finding("unquoted-text", 8, "Stays sentence.", (KEY,))
        fresh = match.Finding("copy-mismatch", 9, "Fresh sentence.", (KEY,), {"page": 4, "share": 0.9, "missing": []})
        before = a_payload(draft, gone, stays)
        after = a_payload(draft, stays, fresh)
        result = recheck.compare(after, before)
        assert [i["detail"]["text"] for i in result["resolved"]] == ["Gone sentence."]
        assert [i["detail"]["text"] for i in result["persisting"]] == ["Stays sentence."]
        assert [i["detail"]["text"] for i in result["new"]] == ["Fresh sentence."]
        assert result["counts_before"]["unquoted-text"] == 2
        assert result["counts_after"] == {"unsupported-text": 0, "copy-mismatch": 1, "unquoted-text": 1}
        assert result["fell"] is False

    def test_fell_means_no_class_rose_one_fell_and_nothing_new(self):
        draft = a_digest(DIGEST)
        gone = match.Finding("unquoted-text", 6, "Gone sentence.", (KEY,))
        stays = match.Finding("unquoted-text", 8, "Stays sentence.", (KEY,))
        assert recheck.compare(a_payload(draft, stays), a_payload(draft, gone, stays))["fell"] is True
        assert recheck.compare(a_payload(draft, stays), a_payload(draft, stays))["fell"] is False

    def test_copied_fraction_travels(self):
        draft = a_digest(DIGEST)
        result = recheck.compare(a_payload(draft, total=10), a_payload(draft, total=20))
        assert (result["copied_before"], result["copied_after"]) == (0.0, 0.0)


class TestRecheckOutput:
    def test_command_names_the_baseline_and_json(self):
        assert recheck.recheck_command("content/drafts/t/n.digest.md", "b.json") == (
            "python -m chitragupta.review digest content/drafts/t/n.digest.md --baseline b.json --json"
        )

    def test_payload_and_text_say_the_same_thing(self):
        draft = a_digest(DIGEST)
        stays = match.Finding("unquoted-text", 8, "Stays sentence.", (KEY,))
        comparison = recheck.compare(a_payload(draft, stays), a_payload(draft, stays))
        data = recheck.recheck_payload(draft, "b.json", comparison)
        text = recheck.format_recheck("b.json", comparison)
        assert data["aid"] == "digest" and data["baseline"] == "b.json"
        assert data["fell"] is False and "fell: no" in text
        assert "baseline: b.json" in text
        assert "persisting: 1" in text and "resolved: 0" in text and "new: 0" in text
        assert "unquoted-text: 1 -> 1" in text
        assert "copied fraction: 0.0 -> 0.0" in text
```

- [ ] **Step 2: Run, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py -q -k "Baseline or Compare or RecheckOutput"
```

Expected: FAIL, attributes missing.

- [ ] **Step 3: Implement**

`chitragupta/review/_digest_recheck.py`:

```python
"""`review digest --baseline`: this run against a recorded one (#991).

"Minimise unsupported text" is a number a person watches fall, never a
threshold. This is the arithmetic: items matched by their stable `id`
into `resolved`/`persisting`/`new`, the per-class counts before and
after, the copied fraction before and after, and one boolean, `fell`,
true when no class rose, at least one fell, and nothing new appeared --
the four conditions the skill keeps a repair under. Nothing is
refreshed here: the aid recomputed everything before comparing, so
there is no stale report to guard against.

Mirrors `agenda/_recheck.py`'s payload keys where the two say the same
thing, because the skill reading this already reads that one.
"""

import json
import shlex
from pathlib import Path

from chitragupta import review
from chitragupta.review._digest_match import CLASSES


def load_baseline(path: str | Path) -> dict:
    """A previously filed `digest` payload, refused if it cannot serve.

    Two confident-wrong-answer failures are named: unreadable JSON, and
    another aid's payload (every aid's `.json` has a `command`, and the
    likeliest typo is the agenda's beside it).
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Cannot read the baseline {path}: {exc}") from None
    except json.JSONDecodeError:
        raise ValueError(
            f"{path} is not a digest payload -- it is not valid JSON. "
            "Write one with `review digest <draft>`, which files it as the report's .json sibling."
        ) from None
    if not isinstance(payload, dict) or payload.get("aid") != "digest" or "items" not in payload:
        raise ValueError(
            f"{path} is not a digest payload. Write one with `review digest <draft>`, "
            "which files it as the report's .json sibling."
        )
    return payload


def compare(payload: dict, baseline: dict) -> dict:
    new_items, old_items = payload["items"], baseline["items"]
    new_ids = {item["id"] for item in new_items}
    old_ids = {item["id"] for item in old_items}
    before = {cls: baseline["counts"].get(cls, 0) for cls in CLASSES}
    after = {cls: payload["counts"].get(cls, 0) for cls in CLASSES}
    appeared = [item for item in new_items if item["id"] not in old_ids]
    rose = any(after[cls] > before[cls] for cls in CLASSES)
    fell = any(after[cls] < before[cls] for cls in CLASSES)
    return {
        "resolved": [item for item in old_items if item["id"] not in new_ids],
        "persisting": [item for item in new_items if item["id"] in old_ids],
        "new": appeared,
        "counts_before": before,
        "counts_after": after,
        "copied_before": baseline.get("copied_fraction", 0.0),
        "copied_after": payload["copied_fraction"],
        "fell": fell and not rose and not appeared,
    }


def recheck_command(draft: str | Path, baseline: str | Path) -> str:
    parts = ["python", "-m", "chitragupta.review", "digest", str(draft)]
    return shlex.join([*parts, "--baseline", str(baseline), "--json"])


def recheck_payload(draft: Path, baseline: str | Path, comparison: dict) -> dict:
    data = review.envelope(draft, "digest", recheck_command(draft, baseline))
    data["baseline"] = str(baseline)
    data.update(comparison)
    return data


def format_recheck(baseline: str | Path, comparison: dict) -> str:
    lines = [f"baseline: {baseline}", ""]
    for group in ("resolved", "persisting", "new"):
        lines.append(f"{group}: {len(comparison[group])}")
        lines += [f"  - `{item['id']}` [{item['class']}] {item['summary']}" for item in comparison[group]]
    lines.append("")
    for cls in CLASSES:
        lines.append(f"{cls}: {comparison['counts_before'][cls]} -> {comparison['counts_after'][cls]}")
    lines.append(f"copied fraction: {comparison['copied_before']} -> {comparison['copied_after']}")
    lines.append(f"fell: {'yes' if comparison['fell'] else 'no'}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run, expect pass; measure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py -q && python scripts/code_standards.py chitragupta/review/_digest_recheck.py
```

Expected: all pass, no finding.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/review/_digest_recheck.py tests/test_review_digest.py
git commit -m "Compare a verbatim digest report against a baseline"
```

---

### Task 6: `verbatim_digest.py`, the CLI, and registration

This task also makes the forced split of `review/__init__.py` and
decides `agenda`'s exclusion. It is one task because none of it is
testable through the entry point until all of it exists.

**Files:**

- Create: `chitragupta/review/verbatim_digest.py` (replacing the placeholder)
- Create: `chitragupta/review/_paths.py`
- Modify: `chitragupta/review/__init__.py` (`AIDS`, imports, docstring)
- Modify: `chitragupta/review/_registry.py:26-38`
- Modify: `chitragupta/review/__main__.py` (docstring list, `DESCRIPTION`)
- Modify: `chitragupta/review/agenda/_sources.py:26-61`
- Modify: `tests/test_review_agenda.py:111`
- Test: `tests/test_review_digest.py` (append), `tests/test_review.py`
  (unchanged, must stay green through the split)

**Interfaces:**

- Consumes: everything above; `review.require_reviewable`,
  `review.write`, `review.write_json`, `_emit.formats`, `_emit.announce`,
  `ledger.reading`, `passages.source_passages`.
- Produces:

```python
INFIX = "digest"                                  # the `.digest` in `<name>.digest.md`
def report_target(draft: Path) -> Path            # sibling path with the infix stripped
def build_report(draft: Path) -> tuple[Checked, list[dict]]
def build_parser(parser=None) -> argparse.ArgumentParser   # draft, --formats, --json, --baseline
def main(argv=None) -> int
def run(args) -> int
```

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_review_digest.py`:

```python
class TestReportTarget:
    def test_strips_the_digest_infix_so_the_report_is_name_digest_md(self, isolated_config):
        draft = config.DRAFTS_DIR / "t" / "notes.digest.md"
        assert verbatim_digest.report_target(draft) == config.DRAFTS_DIR / "t" / "notes.md"
        assert review.report_path(verbatim_digest.report_target(draft), "digest") == (
            config.REVIEW_DIR / "t" / "notes.digest.md"
        )

    def test_leaves_any_other_name_alone(self, isolated_config):
        draft = config.DRAFTS_DIR / "t" / "survey.md"
        assert verbatim_digest.report_target(draft) == draft


class TestRegistration:
    def test_digest_is_an_aid_with_a_module_and_a_label(self):
        assert review.AIDS["digest"] == "Verbatim digest"
        from chitragupta.review import _registry

        assert _registry.AIDS["digest"][0] is verbatim_digest

    def test_agenda_does_not_read_it(self):
        from chitragupta.review.agenda import _sources

        assert "digest" not in _sources.AID_NAMES

    def test_the_moved_path_helpers_keep_their_names(self):
        from chitragupta.review import _paths

        assert review.require_reviewable is _paths.require_reviewable
        assert review.report_dir is _paths.report_dir


class TestRun:
    def test_files_md_and_json_and_prints_the_summary(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        assert review_main.main(["digest", str(draft), "--formats", "md"]) == 0
        out = capsys.readouterr().out
        md = config.REVIEW_DIR / "dt" / "notes.digest.md"
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        assert md.is_file() and js.is_file()
        assert str(md) in out and str(js) in out
        data = json.loads(js.read_text(encoding="utf-8"))
        assert data["command"] == f"python -m chitragupta.review digest {draft} --formats md"
        assert data["counts"]["unquoted-text"] == 2
        assert data["counts"]["unsupported-text"] == 2
        assert data["words_copied"] == 17
        assert data["copied_fraction"] == round(17 / data["words_total"], 3)
        assert "Copied fraction" in md.read_text(encoding="utf-8")

    def test_json_goes_to_stdout_and_the_summary_to_stderr(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        assert review_main.main(["digest", str(draft), "--json", "--formats", "md"]) == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out)["aid"] == "digest"
        assert "notes.digest.json" in captured.err

    def test_a_digest_with_no_prose_exits_zero(self, capsys):
        draft = a_digest("# Only a heading\n")
        assert review_main.main(["digest", str(draft), "--json", "--formats", "md"]) == 0
        assert json.loads(capsys.readouterr().out)["copied_fraction"] == 0.0

    def test_a_draft_outside_content_exits_one(self, tmp_path, capsys):
        outside = tmp_path / "notes.digest.md"
        outside.write_text("x\n", encoding="utf-8")
        assert review_main.main(["digest", str(outside)]) == 1
        assert "content" in capsys.readouterr().err

    def test_a_missing_draft_exits_one(self, capsys):
        assert review_main.main(["digest", str(config.DRAFTS_DIR / "nope.digest.md")]) == 1

    def test_a_bad_baseline_exits_two_before_reading_the_ledger(self, tmp_path, capsys, monkeypatch):
        draft = a_digest(DIGEST)
        bad = tmp_path / "notes.agenda.json"
        bad.write_text(json.dumps({"aid": "agenda", "items": []}), encoding="utf-8")
        monkeypatch.setattr(verbatim_digest, "build_report", lambda *_: pytest.fail("built a report"))
        assert review_main.main(["digest", str(draft), "--baseline", str(bad)]) == 2
        assert "not a digest payload" in capsys.readouterr().err

    def test_baseline_prints_the_comparison_and_refiles_the_report(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        review_main.main(["digest", str(draft), "--formats", "md"])
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        # The repair: delete the closing thought.
        draft.write_text(DIGEST.replace("And a closing thought of mine.\n", ""), encoding="utf-8")
        assert review_main.main(["digest", str(draft), "--baseline", str(js), "--formats", "md"]) == 0
        out = capsys.readouterr().out
        assert "resolved: 2" in out and "new: 0" in out and "fell: yes" in out
        assert json.loads(js.read_text(encoding="utf-8"))["counts"]["unquoted-text"] == 1

    def test_baseline_with_json_prints_the_comparison_payload(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        review_main.main(["digest", str(draft), "--formats", "md"])
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        capsys.readouterr()
        assert review_main.main(["digest", str(draft), "--baseline", str(js), "--json", "--formats", "md"]) == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["baseline"] == str(js) and data["fell"] is False
        assert data["command"].endswith("--json")
        assert "notes.digest.md" in captured.err

    def test_the_filed_command_is_the_bare_one_even_under_baseline(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        review_main.main(["digest", str(draft), "--formats", "md"])
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        review_main.main(["digest", str(draft), "--baseline", str(js), "--formats", "md"])
        assert "--baseline" not in json.loads(js.read_text(encoding="utf-8"))["command"]

    def test_passages_are_looked_up_once_per_citekey(self, monkeypatch):
        from chitragupta import passages as passages_mod

        calls = []
        real = passages_mod.source_passages

        def counting(con, citekey):
            calls.append(citekey)
            return real(con, citekey)

        monkeypatch.setattr(verbatim_digest.passages, "source_passages", counting)
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        verbatim_digest.build_report(draft)
        assert calls == [KEY]

    def test_the_standalone_parser_carries_the_same_defaults(self):
        """`tests/test_review_entrypoint.py` already pins that every aid
        declares its flags on the subparser and has no `__main__` block;
        this only covers `build_parser(None)`, the shape `main()` uses."""
        parser = verbatim_digest.build_parser()
        args = parser.parse_args(["x.md"])
        assert (args.formats, args.json, args.baseline) == ("md,tex,pdf", False, None)
```

- [ ] **Step 2: Run, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py -q -k "ReportTarget or Registration or TestRun"
```

Expected: FAIL.

- [ ] **Step 3: Split `review/__init__.py`**

Create `chitragupta/review/_paths.py` holding `require_reviewable` and
`report_dir`, moved verbatim with their docstrings and comments
(`review/__init__.py:143-200` today), with this module docstring:

```python
"""Where a review report may be read from and goes to (#991).

`require_reviewable` and `report_dir` lived in `review/__init__.py` from
the day the layer had one output contract. They moved here when the
eleventh aid's `AIDS` entry needed one more line in a module already at
docs/CODE-STANDARDS.md's 250-code-line ceiling, and this is the boundary
that module's own docstring draws: this half is *where* a report goes,
the other half is what it looks like. `report_path` stays there because
it needs `AIDS`. Both names are re-exported from `review` unchanged, so
no caller moved.
"""

from pathlib import Path

from chitragupta import config
from chitragupta.review import _book_paths
```

In `chitragupta/review/__init__.py`: delete the two functions, add
this import after the `_book_paths` one:

```python
from chitragupta.review._paths import report_dir, require_reviewable  # noqa: F401
```

Keep the `_book_paths` import only if something else there still uses
it; otherwise drop it. Then add to `AIDS`:

```python
    "union": "Citekey union",
    "digest": "Verbatim digest",
}
```

Update the docstring: "Ten commands make up the review layer" → "Eleven
commands ...", add `chitragupta/review/verbatim_digest.py` to the list,
add `content/review/<topic>/survey.digest.md` to the path block, "all
ten are interpreter tier 1" → "all eleven", "makes the ten obey" →
"the eleven", and in the JSON paragraph add `digest` to the list of aids
that emit one from the day they landed.

Run:

```bash
python scripts/code_standards.py chitragupta/review/__init__.py chitragupta/review/_paths.py
```

Both under 250.

- [ ] **Step 4: Register**

`chitragupta/review/_registry.py`: add `verbatim_digest` to the import
list and

```python
    "union": (citekey_union, "does the assembly still carry every unit's citekeys?"),
    "digest": (verbatim_digest, "how much of a verbatim digest is really the sources' own words?"),
}
```

`chitragupta/review/__main__.py`:

```python
DESCRIPTION = "The review layer: eleven read-only aids over a finished draft. No gate."
```

Then "Ten aids, read over a finished draft" → "Eleven aids", and add to the
usage list:

```text
    python -m chitragupta.review digest <draft>
        for a verbatim digest: which runs are really in the source they
        cite, every sentence that is not, and the copied fraction.
        --baseline compares against an earlier run.
```

and `.digest.md` to the suffix list in the "subcommand names" paragraph.

`chitragupta/review/agenda/_sources.py`:

```python
AID_NAMES = tuple(aid for aid in review.AIDS if aid not in ("agenda", "union", "digest"))
```

with this added to the comment above it, after the `union` paragraph:

```python
# `digest` is excluded because its classes mean nothing outside a
# verbatim digest (#991): wired in, every existing agenda would carry a
# "digest: read" line for a report no survey or chapter ever has, and
# `--baseline`'s refresh would run the digest aid over prose that is
# not a digest. The digest's report is its own worklist, worked by the
# `verbatim-digest-writer` skill, never by `agenda-reviser`.
```

`tests/test_review_agenda.py:111`:

```python
        assert set(_sources.AID_NAMES) == set(review.AIDS) - {"agenda", "union", "digest"}
```

and extend that test's docstring with one sentence: "`digest` is
excluded for the same kind of reason: its classes describe a verbatim
digest and nothing else (#991)."

- [ ] **Step 5: Implement the CLI**

`chitragupta/review/verbatim_digest.py`:

```python
"""Verbatim digest report: how much of a digest is really the sources'
own words, and what every other sentence is (#991).

    python -m chitragupta.review digest <draft>
        split the digest into citation-terminated runs, find each in
        the source it cites, and list every sentence that is not
        verified source text.

    python -m chitragupta.review digest <draft> --baseline <stem>.digest.json
        the same, then compare with an earlier run: resolved,
        persisting and new items, the per-class counts before and
        after, and whether the unsupported text fell.

The eleventh aid in `review.AIDS`, and the first over a genre of its
own: a digest is private study text written mostly in the cited papers'
own words, with no quotation marks and a citation closing each copied
run (docs/VERBATIM-DIGEST.md). `_digest_runs.py` reads the runs,
`_digest_match.py` verifies them, `_digest_render.py` prints and
serialises, `_digest_recheck.py` compares. This file is the CLI.

**Not a gate, and advisory like the other ten.** Every finding is
`[surfaced]`: a person decides whether to cite, replace or delete.
Exits 0 whatever it finds. The digest is never a drafting source for any
other genre; `review verbatim scan` already catches its wording if it
reaches one.

**Files its report unconditionally**, like `agenda` and for the same
reason: the `.json` is the next pass's `--baseline`. `--json` only
decides what prints to stdout.

**One rule for where the report goes.** `<name>.digest.md` files
`content/review/<topic>/<name>.digest.md`, which is what
`review.report_path` gives once the draft's own `.digest` infix is
stripped (`report_target`); any other name files under the ordinary
`<stem>.digest.md` rule. The header and the payload name the real path.

Stdlib only, interpreter tier 1. Reads the ledger read-only (#843).
"""

import argparse
import json
import shlex
import sys
from pathlib import Path

from chitragupta import config, ledger, passages, review
from chitragupta.review import _digest_match, _digest_recheck, _digest_render, _digest_runs, _emit

INFIX = "digest"


def report_target(draft: Path) -> Path:
    """`draft` with a trailing `.digest` stripped from its stem, so the
    report lands at `<name>.digest.md` rather than `<name>.digest.digest.md`."""
    suffix = f".{INFIX}{draft.suffix}"
    if draft.name.endswith(suffix):
        return draft.with_name(draft.name[: -len(suffix)] + draft.suffix)
    return draft


def build_report(draft: Path) -> tuple[_digest_match.Checked, list[dict]]:
    """Every run of `draft` checked, and the worklist rows for what failed.

    One ledger connection and one passage lookup per citekey for the
    whole run: a digest cites few papers many times.
    """
    text = draft.read_text(encoding="utf-8")
    checked = _digest_match.Checked()
    cache: dict[str, tuple[list, str | None]] = {}
    with ledger.reading() as con:

        def lookup(citekey: str):
            if citekey not in cache:
                cache[citekey] = passages.source_passages(con, citekey)
            return cache[citekey]

        for run in _digest_runs.runs(text):
            _digest_match.check_run(run, lookup, checked)
    return checked, _digest_render.items(checked, text)


def _command(draft: Path, args: argparse.Namespace) -> str:
    """The bare invocation, which is what the filed `.json` records even
    under `--baseline`: that file is the *next* run's baseline, so its
    envelope has to name a command that regenerates a report."""
    parts = ["python", "-m", "chitragupta.review", "digest", str(draft)]
    if args.formats != "md,tex,pdf":
        parts += ["--formats", args.formats]
    return shlex.join(parts)


def build_parser(parser=None) -> argparse.ArgumentParser:
    if parser is None:
        parser = argparse.ArgumentParser(
            description="How much of a verbatim digest is really the sources' own words.",
        )
    parser.add_argument("draft", help="The digest to check, under content/drafts/")
    parser.add_argument(
        "--formats",
        default="md,tex,pdf",
        help="Additional formats to render beside the Markdown report "
        "(default: md,tex,pdf). The .md and .json are always written.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the payload (or, with --baseline, the comparison) as JSON "
        "instead of the summary. The .json sibling is filed either way.",
    )
    parser.add_argument(
        "--baseline",
        help="Compare this run against a previously filed <name>.digest.json: "
        "resolved, persisting and new items, counts before and after, and "
        "whether unsupported text fell.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def _file(draft: Path, args: argparse.Namespace) -> tuple[dict, dict]:
    checked, rows = build_report(draft)
    command = _command(draft, args)
    target = report_target(draft)
    written = review.write(target, INFIX, _digest_render.render_markdown(draft, command, checked, rows), _emit.formats(args))
    payload = _digest_render.payload(draft, command, checked, rows)
    written["json"] = review.write_json(target, INFIX, payload)
    return payload, written


def run(args: argparse.Namespace) -> int:
    """The baseline is loaded before anything is computed: a bad one is a
    usage error (exit 2) and should cost nothing. The draft is checked
    first because a draft the layer will not read is exit 1, the same
    order `agenda` keeps."""
    try:
        draft = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1
    baseline = None
    if args.baseline:
        try:
            baseline = _digest_recheck.load_baseline(args.baseline)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
    payload, written = _file(draft, args)
    if baseline is None:
        _emit.announce(payload, written, as_json=args.json)
        return 0
    comparison = _digest_recheck.compare(payload, baseline)
    if args.json:
        print(json.dumps(_digest_recheck.recheck_payload(draft, args.baseline, comparison), indent=2))
        review.print_written(written, stream=sys.stderr)
    else:
        print(_digest_recheck.format_recheck(args.baseline, comparison))
        review.print_written(written)
    return 0
```

- [ ] **Step 6: Run the review suites, expect pass; measure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py tests/test_review.py tests/test_review_entrypoint.py tests/test_review_agenda.py tests/test_review_quotation.py -q
python scripts/code_standards.py chitragupta/review/verbatim_digest.py chitragupta/review/__init__.py chitragupta/review/_paths.py chitragupta/review/_registry.py
```

Expected: all pass, no finding. `test_review_entrypoint.py`'s
"every aid declares its own flags" and "no `__main__` block" cases now
cover `digest` by iterating `_registry.AIDS`. If `words_copied == 17`
fails, count the two copied sentences' words in `SOURCE` and fix the
expected number, not the matcher.

- [ ] **Step 7: Commit**

```bash
git add chitragupta/review/verbatim_digest.py chitragupta/review/_paths.py chitragupta/review/__init__.py chitragupta/review/_registry.py chitragupta/review/__main__.py chitragupta/review/agenda/_sources.py tests/test_review_digest.py tests/test_review_agenda.py
git commit -m "Add review digest, the verbatim digest aid, and keep it off the agenda"
```

---

### Task 7: the `digest` genre

**Files:**

- Modify: `chitragupta/dossier/__init__.py:39`
- Modify: `chitragupta/review/_units.py:40-70`
- Test: `tests/test_review_units.py`, `tests/test_review_uncited.py`
  (both pin the tables to `dossier.GENRES` and will go red at Step 2),
  `tests/test_dossier.py` (one new test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dossier.py`, in the class that covers `init`:

```python
    def test_digest_is_a_genre_init_records(self, isolated_config):
        draft = config.DRAFTS_DIR / "t" / "notes.digest.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("x\n", encoding="utf-8")
        assert "digest" in dossier.GENRES
        assert dossier.main(["init", str(draft), "--genre", "digest"]) == 0
        assert "- genre: digest" in (dossier.dossier_dir(draft) / "scope.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_dossier.py -k digest_is_a_genre -q
```

Expected: FAIL on `"digest" in dossier.GENRES`.

- [ ] **Step 3: Implement**

`chitragupta/dossier/__init__.py`:

```python
GENRES = ("survey", "thesis-chapter", "textbook-chapter", "tutorial", "deep-research", "digest")
```

and extend the comment above it: "`digest` (#991) is the sixth: a
verbatim digest, private study text in the sources' own words, with its
own review aid rather than a place on the agenda."

`chitragupta/review/_units.py`:

```python
UNITS = {
    "survey": "paragraph",
    "thesis-chapter": "paragraph",
    "deep-research": "paragraph",
    "textbook-chapter": "section",
    "tutorial": "document",
    # A digest fuses nothing: every run is one source's own words, so
    # the multi-source rule has no paragraph to bind at (#991).
    "digest": "document",
}
```

```python
UNCITED_PROSE = {
    ...
    "tutorial": "ordinary",
    # A digest's connecting sentences carry no citation by design; the
    # `digest` aid is what judges them, sentence by sentence (#991).
    "digest": "ordinary",
}
```

- [ ] **Step 4: Run, expect pass**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_dossier.py tests/test_review_units.py tests/test_review_uncited.py tests/test_review_synthesis.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/dossier/__init__.py chitragupta/review/_units.py tests/test_dossier.py
git commit -m "Register digest as the sixth dossier genre"
```

---

### Task 8: the ignore rule

**Files:**

- Modify: `.gitignore`, after the line re-including the example topic
  under `content/drafts/` and before the `.evidence` carve-out
- Test: `tests/test_review_digest.py` (append)

- [ ] **Step 1: Write the failing test**

```python
class TestNeverTracked:
    """A digest is mostly source wording, so like the evidence sidecar it
    is ignored even under the one topic whose drafts are tracked. Asked
    of git itself, against the infix the aid actually uses."""

    REPO_ROOT = Path(__file__).resolve().parent.parent
    TOPIC = "content/drafts/digital-twins-for-software-engineers"

    def _ignored(self, relative: str) -> bool:
        import subprocess

        return subprocess.run(["git", "-C", str(self.REPO_ROOT), "check-ignore", "-q", relative], check=False).returncode == 0

    def test_a_digest_under_the_tracked_topic_is_ignored(self):
        assert self._ignored(f"{self.TOPIC}/notes.{verbatim_digest.INFIX}.md")

    def test_a_draft_under_the_tracked_topic_is_still_visible(self):
        assert not self._ignored(f"{self.TOPIC}/survey.md")
```

- [ ] **Step 2: Run, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py -k NeverTracked -q
```

Expected: the first case FAILS (not ignored).

- [ ] **Step 3: Implement**

Insert into `.gitignore` directly after
`!content/rendered/digital-twins-for-software-engineers/`:

```gitignore
# ...and a verbatim digest (chitragupta/review/verbatim_digest.py) is
# never tracked either, in the example topic or anywhere else: it is
# private study text copied from the sources a corpus holds, which is
# the same reason the evidence sidecar below is ignored. The `.digest`
# infix is `verbatim_digest.INFIX`, and tests/test_review_digest.py asks
# git whether the path the aid actually names is ignored, so renaming the
# convention fails a test instead of quietly publishing a digest.
content/drafts/**/*.digest.md
```

- [ ] **Step 4: Run, expect pass**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py -k NeverTracked tests/test_gitignore_covers_content.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add .gitignore tests/test_review_digest.py
git commit -m "Never track a verbatim digest, even under the example topic"
```

---

### Task 9: the `verbatim-digest-writer` skill, three copies

**Files:**

- Create: `.claude/skills/verbatim-digest-writer/SKILL.md`
- Create: `.agents/skills/verbatim-digest-writer/SKILL.md` (same text, same `name:`)
- Create: `.opencode/skills/verbatim-digest-writer-opencode/SKILL.md`
  (same text; `name:` and the `#` heading carry `-opencode`, and so does
  every other skill it names: `draft-reviser-opencode`,
  `corpus-reviser-opencode`, `survey-writer-opencode`)
- Modify: `.opencode/opencode.json`: add `"verbatim-digest-writer": "deny"`
  in alphabetical position, after `tutorial-writer`
- Modify: `tests/test_skill_frontmatter.py:38` (`== 33  # eleven skills, three harnesses`)
- Modify: `tests/test_skill_verbatim_scan_step.py:144`: `_HELPERS` gains
  `"verbatim-digest-writer"`, with its comment; and
  `test_genre_doc_still_speaks_for_every_skill_that_exists`: `count == 11`,
  the string `"What all eleven have in common"`, and the two message
  literals that say "all ten"
- Modify: `tests/test_skill_style_check_step.py:53`: `_HELPERS` gains
  `"verbatim-digest-writer"`; and the "What all ten have in common"
  literal at line 121
- Modify: `tests/test_skill_pregate_feedback_step.py:75-81`: add
  `"verbatim-digest-writer"` to `_EXCLUDED_SKILLS`; "The five skills that
  must never carry this step" → "The six"
- Modify: `tests/test_features_doc.py` and
  `tests/test_architecture_review_layer.py`: `_NUMBER_WORDS` gains
  `11: "Eleven"` in both; Task 10 makes the docs match

Why each exclusion, as a comment beside it: *a digest is verbatim by
design -- the scan would flag every run, the prose check would ask the
drafter to restyle a source's wording, and the critique loop reads a
`claim:`/`quote:` packet the digest never drafts from (#991). Its own
aid, `review digest`, is the step that replaces all three.*

- [ ] **Step 1: Write the failing test**

Append to `tests/test_skill_frontmatter.py` after the count test:

```python
def test_the_digest_skill_exists_on_every_harness():
    assert {p.parent.name for p in SKILL_FILES} >= {
        "verbatim-digest-writer",
        "verbatim-digest-writer-opencode",
    }
```

and update the count to 33.

- [ ] **Step 2: Run, expect failure**

Run: `.venv-full/bin/python -m pytest tests/test_skill_frontmatter.py -q`
Expected: FAIL (30 files, skill missing).

- [ ] **Step 3: Write the skill**

`.claude/skills/verbatim-digest-writer/SKILL.md`:

````markdown
---
name: verbatim-digest-writer
description: Builds a verbatim digest -- a private study summary of a topic written mostly in the source papers' own words, copied exactly from parsed PDFs in the corpus, with a citation closing each copied run and no quotation marks -- then runs `python -m chitragupta.review digest` on it and works the report down. Every citekey comes from content/ledger.sqlite via chitragupta.retrieval, never invented. Triggers when the user asks for a digest, study notes, a reading summary or an extract "in the papers' own words" on a topic. The digest is never a deliverable and never a source for a survey, chapter or any other draft; to summarise in your own words use survey-writer. Must run `python -m chitragupta.draft gate` and `review digest` before presenting, and refuses (telling the user to run `python -m chitragupta.corpus sync`) if the ledger is empty.
tags: [digest, study-notes, verbatim, citation]
---

# verbatim-digest-writer

A verbatim digest is private study text: most of it is copied exactly
from parsed PDFs in the corpus, each copied run ends with a citation,
there are no quotation marks, and a few short sentences of your own
connect the runs. It is read by one person to learn a topic. It is not a
deliverable, and **it is never a source for drafting anything else**:
its wording is the corpus's own, and `python -m chitragupta.review
verbatim scan` will flag it the moment it reaches a survey or a chapter.

Three goals, in this order (`docs/VERBATIM-DIGEST.md`):

1. **Maximise copied text.** The copied fraction the report prints
   should be as high as you can make it.
2. **Surface unsupported text.** Every sentence that is not verified
   source text is listed for the person to judge.
3. **Minimise unsupported text.** Each repair pass leaves fewer such
   sentences than the one before, and `--baseline` makes that a number.

Paths in this skill are from the project root, not from this skill's
own folder.

## Shared corpus layer (read, don't regenerate)

- `content/ledger.sqlite` -- per-citekey status, populated by `sync`
- `content/parsed/<citekey>.txt` -- the extracted PDF text **you copy
  from**. Copy from this file, or from `content/parsed/<citekey>.passages.json`
  when it exists, never from memory and never from a snippet you
  tidied: the aid matches what you wrote against this text, and a
  faithful copy of a bad parse is still a match
- `python -m chitragupta.draft retrieve search "<q>" --k 15 --log <draft>`
  finds candidates; `... evidence "<q>" --citekey <key> --log <draft>`
  reads more of one document

**Read-only means read-only: never run `python -m chitragupta.corpus sync`,
and never run `python -m chitragupta.enrich` or any `chitragupta/enrich/*`
build stage.** Both take the pipeline's write lock and are the user's to run.

**If the ledger is empty, stop.** Check before anything else:

```bash
python -m chitragupta.corpus ledger
```

If it reports no items, or none with status `parsed`, say so plainly and
stop. Tell the user to run `.venv-full/bin/python -m chitragupta.corpus sync`
and come back. Do not draft around it, do not sync, do not cite.

## Collection scoping (#195)

Before any retrieval:

```bash
python -m chitragupta.corpus ledger --collections
```

If it reports none, record `- collection: (whole corpus)` in `scope.md`'s
header and skip this section. Otherwise read
`.claude/skills-common/references/collection-scoping.md` now and follow
it for the whole run.

## When to invoke

- "Give me a digest of what the corpus says about X."
- "Study notes on X, in the papers' own words."
- "Pull the key passages on X together."

Not for a summary in your own words (`survey-writer`), not for changing
a digest that exists (`draft-reviser`, which reads the dossier), and not
for anything that will be submitted or published.

## The format

Plain prose plus a closing citation. No markup, no quotation marks:

```markdown
Sentence one. Sentence two. Sentence three. [@key, p. 4-5]
A connecting sentence of your own.
Another copied sentence. [@other, p. 12]
```

**A citation covers every sentence back to the previous citation, or to
the start of the paragraph.** So:

- Put the citation at the end of the last copied sentence, on the same
  line or the next, before any sentence of your own.
- Copy from one paper per run. Two papers under one citation leaves the
  second paper's text unmatched.
- Give the page as `p. N` or `pp. N-M`. It is a hint: the aid reports
  the page it actually found the text on.
- Keep your own sentences short, few, and between runs, never inside
  one.
- Pandoc-style citations only (`[@citekey, p. 4]`, `[@a; @b]`).

## Process

0. **Name the reader and the scope, and open the dossier.** Settle with
   the user what the digest covers and what it leaves out, and where it
   goes. A digest is `content/drafts/<topic>/<name>.digest.md`: the
   `.digest.md` ending is what keeps it out of git even under a tracked
   topic, and what `review digest` files its report beside as
   `content/review/<topic>/<name>.digest.md`. Then:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<topic>/<name>.digest.md --genre digest
   ```

   Fill in `scope.md`'s **Reader**, **Covers** and **Does not cover**
   now. The reader is the user, studying.

1. **Retrieve per sub-theme, over-fetching.** Decide three to six
   sub-themes with the user. For each, run
   `python -m chitragupta.draft retrieve search "<query>" --k 15 --log <draft>`,
   then read the candidates' parsed text. Record every candidate you
   read in `evidence.md` as the dossier contract asks (`relevance:` and
   `claim:` per block; see `docs/DOSSIER.md`), and every candidate you
   turn down in `rejected.md` with why.

2. **Pick passages worth copying.** For each sub-theme choose the
   passages -- a sentence to a paragraph each -- that say the thing
   best. Prefer a whole paragraph to three sentences from three places:
   a run found whole is one clean span; one assembled from several
   places is reported as such.

3. **Copy exactly.** Open `content/parsed/<citekey>.txt` and copy the
   passage character for character, including the parse's own noise.
   Do not fix hyphenation, ligatures, a dropped word or a reference
   marker; do not reorder; do not shorten. If the parse is too broken to
   read, pick another passage or another paper. Close the run with its
   citation and page.

4. **Connect sparingly.** Where two runs need a bridge, write one short
   sentence of your own between them. Every such sentence will be
   listed as `unquoted-text`; one that no source lexically supports is
   also `unsupported-text`. Fewer is better, and none is best.

5. **Never write a citekey you did not get from a retrieval result.**
   `python -m chitragupta.draft gate` is the only exit, and a hook runs it
   on every write under `content/drafts/`. A `FAIL` names the key; fix
   or remove it. Never guess a key, never rewrite one.

6. **Map sections to citekeys.** Save the digest, then:

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<topic>/<name>.digest.md --citekeys --write
   ```

7. **Gate.**

   ```bash
   python -m chitragupta.draft gate content/drafts/<topic>/<name>.digest.md
   ```

   Re-run until it reports `OK`. Never show a digest that has not passed.

8. **Build the References section** from exactly the gated citekeys:

   ```bash
   python -m chitragupta.draft references content/drafts/<topic>/<name>.digest.md
   ```

9. **Run the digest report.**

   ```bash
   python -m chitragupta.review digest content/drafts/<topic>/<name>.digest.md --formats md
   ```

   It files `content/review/<topic>/<name>.digest.md` and `.json` and
   prints where. Read the report: the copied fraction, the per-class
   counts, and every item. It is a review aid: it advises and never
   blocks.

   This skill does not run `python -m chitragupta.draft style` or
   `python -m chitragupta.review verbatim scan` on a digest, and does
   not critique it against the evidence packet: a digest is verbatim by
   design, so the scan would flag every run and the prose check would
   ask you to restyle a source's words. `review digest` is the step
   that replaces them here.

10. **Work the report, only if the user asked for a pass.** Say what
    the report found and ask. If they want it repaired, take the items
    one at a time, worst class first, exactly as the report orders them:

    - `copy-mismatch`: open the source at the page the item names and
      restore the exact wording.
    - `unquoted-text`: replace the sentence with a copied passage that
      does the same job, or delete it.
    - `unsupported-text`: cite it correctly if a source says it, replace
      it with that source's words, or delete it.

    After each repair:

    ```bash
    python -m chitragupta.draft gate content/drafts/<topic>/<name>.digest.md
    python -m chitragupta.review digest content/drafts/<topic>/<name>.digest.md --baseline content/review/<topic>/<name>.digest.json --formats md
    ```

    Keep the repair only if all four hold: the gate passes, the item is
    in `resolved`, no class count rose, and `new` is empty -- the
    comparison prints `fell: yes` exactly when the last three do. If any
    fails, revert the edit and move on. Log every attempt, kept or
    reverted, in the dossier's `revisions.md`: the date, the item id,
    the class, what you did, and the counts before and after. Stop when
    the user says so, when no item is left, or after three passes whose
    counts did not fall.

11. **Record any steering** the user gave in chat in the dossier's
    `steering.md`, dated.

12. **Stamp the draft fingerprint, then present.**

    ```bash
    python -m chitragupta.draft dossier stamp content/drafts/<topic>/<name>.digest.md
    ```

    Present the digest's path, the copied fraction, the per-class counts,
    the runs the aid could not check and why, and where the dossier and
    the report are. Say that the digest is private study text and never
    a source for another draft, that it is gitignored, that a change to
    it goes through `draft-reviser`, and that another pass over the
    report is this skill's step 10, on request.

## Sources

The copying discipline here is the mirror of `docs/WRITING-STANDARDS.md`'s
§9 (verbatim wording has one home, and it is never the draft): a digest
is that home made explicit, with every run attributed. `SOUL.md`'s rule
against passing off a source's wording is kept by the citation that
closes every run and by the rule that a digest is never a drafting source.
````

Copy the file to `.agents/skills/verbatim-digest-writer/SKILL.md`
unchanged, and to `.opencode/skills/verbatim-digest-writer-opencode/SKILL.md`
with the `name:`, the `#` heading and the three skill names suffixed
`-opencode`.

- [ ] **Step 4: Run every skill scan**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_skill_frontmatter.py tests/test_skill_harness_copies.py tests/test_skill_references.py tests/test_skill_verbatim_scan_step.py tests/test_skill_style_check_step.py tests/test_skill_pregate_feedback_step.py tests/test_skill_acronym_step.py tests/test_skill_table_step.py tests/test_skill_figure_step.py tests/test_command_depth_scan.py tests/test_opencode_plugin.py -q
```

Expected: every file passes once the exclusion sets and counts above
are edited. `test_genre_doc_still_speaks_for_every_skill_that_exists`
and the style scan's "What all ten have in common" literal stay red
until Task 10 edits `docs/GENRE.md`; do Task 10's GENRE.md edit now if
you want this step green in isolation.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/verbatim-digest-writer .agents/skills/verbatim-digest-writer .opencode/skills/verbatim-digest-writer-opencode .opencode/opencode.json tests/test_skill_frontmatter.py tests/test_skill_verbatim_scan_step.py tests/test_skill_style_check_step.py tests/test_skill_pregate_feedback_step.py tests/test_features_doc.py tests/test_architecture_review_layer.py
git commit -m "Add the verbatim-digest-writer skill on every harness"
```

---

### Task 10: documentation and the count sweep

Step 4 of the shipping cycle, done as its own task because an eleventh
aid and a sixth genre move a count in many files outside the diff.
Three searches, in this order, and the exact edits each one found when
this plan was written against `8b588b5`. Re-run the greps: `main` may
have moved.

**Files:** every path in the table under File structure marked for
Task 10.

- [ ] **Step 1: Write `docs/VERBATIM-DIGEST.md`**

Sections, each a few paragraphs, in this repository's voice (emoji
headings, no em-dashes, tables for the fixed facts):

```markdown
# 📋 The verbatim digest

What it is (private study text in the sources' own words; never a
deliverable; never a drafting source), the three goals, and the audience.

## 🧭 Table of contents

## ✍ Writing one: `verbatim-digest-writer`
The format block and the attribution rule, copied from the skill.
Where it lives (`<name>.digest.md`) and why it is never tracked.

## 🔍 Reading the report: `review digest`
The headline metric. A table of the three classes:

| Class | Means | Repair |
| --- | --- | --- |
| `unsupported-text` | your own sentence, and no citation covers it or the cited source does not lexically support it | cite it, replace it, or delete it |
| `copy-mismatch` | nearly on one page of the source; the item names the missing words | restore the source wording |
| `unquoted-text` | your own sentence, lexically supported | replace with a copied passage, or delete |

All three are `[surfaced]`, and why (judgement calls). The copied-span
list, the "assembled from N places" note, the page note, and
"Not checkable" (a source without reading order).

## 🔁 The repair loop and `--baseline`
The four conditions a repair is kept under, `fell`, the pass bound.

## 🚧 What it does not do
Coarse attribution (a sentence of your own inside a run before its
citation), two papers under one citation, half-copied sentences, parse
noise, lexical support as weak evidence. The `agenda` does not read it
and `agenda-reviser` never touches it, and why.

## ⚖ The rule it lives under
`SOUL.md`'s rule against passing off wording, and how a digest keeps it.
```

Write the full prose; the headings above are the outline, not the text.
Add to `mkdocs.yml` under `Writing:`, after the figure-drawer line:
`- "Study notes in the sources' words: verbatim-digest-writer": docs/VERBATIM-DIGEST.md`.

- [ ] **Step 2: The docs the diff already edits**

- `docs/REVIEW.md`: heading `## 🧩 The eleven aids`; line 4 "ten aids"
  → "eleven aids"; add a `**review digest**` paragraph after
  `review union`'s: *for a verbatim digest, which runs are really in the
  source they cite, the copied fraction, and every sentence that is not
  verified source text, as a worklist of its own; it never reaches the
  agenda. [VERBATIM-DIGEST.md](VERBATIM-DIGEST.md).* In the output
  contract block add `content/review/<topic>/survey.digest.md (+ .tex/.pdf, .json)`
  with a sentence that a digest named `notes.digest.md` files
  `notes.digest.md`, the infix stripped rather than doubled. Add
  `digest` to "`review provenance` and `review agenda` write by default"
  → "`review provenance`, `review agenda` and `review digest` write by
  default". Qualify the sample-project sentence: "except `figure`'s ...
  and `digest`'s, since a digest is never tracked". Line 282 "Nine of
  the ten aids are" → "Ten of the eleven aids are".
- `docs/CLI.md`: ToC entry `[chitragupta review digest]` in alphabetical
  position; a `### 📋` heading naming `chitragupta review digest`, in the shape
  of the `quotation` one: what it answers, the classes table, the flag
  table (`<draft>`, `--formats`, `--json`, `--baseline`), the examples,
  and `**--json**` fields (`copied_fraction`, `words_total`,
  `words_copied`, `counts`, `items` with `id`/`class`/`disposition`/
  `section`/`citekeys`/`line`/`summary`/`detail`, `spans`,
  `unverifiable`; under `--baseline`, `resolved`/`persisting`/`new`,
  `counts_before`/`counts_after`, `copied_before`/`copied_after`, `fell`).
  Tier table line 164 "all ten aids" → "all eleven aids". Line 2208
  "All ten review aids now emit one" → "All eleven".
- `docs/GENRE.md`: picking table row *| someone studying privately, who
  wants the papers' own words | verbatim digest | `verbatim-digest-writer` |*;
  at-a-glance row for `verbatim-digest-writer` (output
  `content/drafts/<topic>/<name>.digest.md`, citation density "every
  copied run", no subagents, cost "one run, plus `review digest`");
  "The five drafting genres" → "The six drafting genres" (heading, ToC,
  line 107 "All five drafting skills"), with a `### 📋 verbatim-digest-writer`
  subsection after `deep-research`'s: what it writes, who reads it, that
  it skips the prose check, the verbatim scan and the critique loop and
  runs `review digest` instead, and that it is never a drafting source;
  "What all ten have in common" → "What all eleven have in common"
  (heading, ToC, line 429 "of the ten `SKILL.md` files"), and in that
  section one sentence naming the digest's three exemptions; "Two of
  the ten are not drafting skills" → "Two of the eleven".
- `docs/FEATURES.md`: `### 🤖 Eleven skills` ("Five write a new draft"
  → "Six write a new draft"), a table row for `verbatim-digest-writer`;
  `## 🔍 Review layer: eleven advisory aids`, a table row for
  `review digest`; "Seven of the ten answer questions of judgement" →
  "Eight of the eleven"; line 327 "Four of the five genres emit" →
  "Four of the six".
- `AGENTS.md`: lines 44-47 list the six genre skills; line 227 "Four of
  the five genres emit one" → "Four of the six genres emit one;
  `tutorial-writer` and `verbatim-digest-writer` do not"; line 281 "ten
  aids" → "eleven aids"; in the skill paragraph near line 202 add a
  router sentence: *A **verbatim digest** (`verbatim-digest-writer`) is
  private study text in the sources' own words, checked by
  `python -m chitragupta.review digest`; it is never a source for any
  other draft, and `draft-reviser` is still the way to change one.*

- [ ] **Step 3: Everywhere else the counts moved**

Run, and fix every hit the way the examples show:

```bash
grep -rn -i 'ten aids\|ten commands\|ten read-only\|all ten\|the ten\|nine of the ten\|seven of the ten\|ten review\|five genre\|five drafting\|of the five\|ten skills\|ten `SKILL' --include=*.md --include=*.py --include=*.toml --include=*.example --include=*.mmd . | grep -v node_modules | grep -v '^./site' | grep -v '^./plans/'
```

Known sites at `8b588b5` and the edit:

| File | Edit |
| --- | --- |
| `README.md:272` | "all ten review-layer commands" → "all eleven" |
| `README.md:373` | "Which of the ten skills" → "eleven"; add a table row for `docs/VERBATIM-DIGEST.md` after `FIGURE-DRAWER.md`'s |
| `DEVELOPER.md:223,318,321,370` | ten → eleven; add `verbatim_digest.py` where the review files are listed |
| `docs/ARCHITECTURE.md` Layer 4 (`344`, `376`, `397`) | "Ten aids behind one command" → "Eleven aids"; "Seven of the ten aids" → "Eight of the eleven"; after the `union` paragraph: "`digest` is the eleventh, and the first over a genre of its own ... [REVIEW.md]". `tests/test_architecture_review_layer.py` fails on any surviving "ten aids" in that section |
| `docs/ARCHITECTURE.md:75`, `docs/DIAGRAMS.md:309`, `docs/diagrams/00-main-workflow.mmd:57` | "five genre skills" → "six genre skills", add `· verbatim-digest-writer` to the label. Then re-render: `python scripts/render_diagrams.py 00-main-workflow --puppeteer-config /tmp/pp.json` with `{"args": ["--no-sandbox"]}` in that file; the recipe for `mmdc` 11 in a container is in `docs/DIAGRAMS.md`. Commit the `.mmd`, the `.svg` and `docs/diagrams/svg/sources.json` together; `tests/test_diagrams_in_sync.py` fails otherwise |
| `docs/ARCHITECTURE.md:653`, `docs/CLI.md:164`, `docs/CONFIG.md:144` | "all ten aids" / "all ten of" → eleven |
| `config.toml.example:41`, `docs/examples/sample-project/config.toml:41`, `docs/examples/codex/config.toml:41`, `docs/examples/opencode/config.toml:41` | "all ten of chitragupta.review's" → "all eleven" (four copies, keep them identical) |
| `docs/GLOSSARY.md:35,74` | "one of the five drafting skills (...)" → six, naming the digest; "one of the ten read-only reports" → eleven |
| `docs/DOSSIER.md:331,345,350,379,497` | "Four of the five drafting skills" → "Four of the six"; the sidecar table gains a `verbatim-digest-writer` row answering **no**, because every run is already the source's own words with its citation and a sidecar would repeat the digest; "five" → "six" at 379 and 497 |
| `docs/WRITING-PROCESS.md:58,68,84` | "four of the five genres" → "four of the six"; "Which of the five genres" → six |
| `docs/AUTO-IMPROVEMENT.md:11,562` | leave: both record what was true when the JSON contract landed. Add after line 562 one sentence: "`digest` (#991) emits one too, and is the one aid the agenda deliberately does not read." |
| `docs/PERFORMANCE.md:23,537` | "the ten review aids" → eleven; "nine of the ten aids" → "ten of the eleven aids; `digest` reads a digest, not a draft, and is not timed here" |
| `bench/bench_review_cost.py:1` | docstring: "over all ten aids" → "over the ten aids a draft review runs; `digest` (#991) reads a digest and is not timed here" |
| `chitragupta/review/_claims.py:164` | "all five genres as they stand" → "all six" |
| `chitragupta/review/synthesis.py:162` | "three of the five genres" → "four of the six" (`tutorial`, `textbook-chapter` and now `digest` measure at a unit where uncited prose is ordinary: check the sentence's actual claim before editing it) |
| `chitragupta/review/_book_paths.py:59` | "the other nine aids" → "the other ten" |
| `chitragupta/review/citekey_union.py:46` | "One of the ten commands" → eleven |
| `chitragupta/review/agenda/*.py` | **do not touch** the "eight aids" the agenda reads: that number did not move, and bumping it is the mistake DEVELOPER-AGENTS.md records |
| `docs/DIAGRAMS.md:11,739` | "five genre skills" → six where the sentence is about the set |

- [ ] **Step 4: What the docs already decided**

Grep for the claims the change touches, not the files:

```bash
grep -rn -i 'never a source\|passing off\|own words\|quotation marks' SOUL.md docs/WRITING-STANDARDS.md docs/PLAGIARISM.md AGENTS.md
```

Read each hit against the digest. The expected result: nothing
contradicts it, because every copied run is cited and the digest is
never a drafting source. If `docs/WRITING-STANDARDS.md` §9 says verbatim
wording "has one legitimate home, and it is not the draft", add a
sentence there: a verbatim digest is the exception that states its
nature in its name, and `docs/VERBATIM-DIGEST.md` carries its rule.
`docs/PLAGIARISM.md`'s "See also" gains a link to VERBATIM-DIGEST.md.

- [ ] **Step 5: Run the doc pins**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_architecture_review_layer.py tests/test_features_doc.py tests/test_docs_pins.py tests/test_diagrams_in_sync.py tests/test_skill_verbatim_scan_step.py tests/test_skill_style_check_step.py tests/test_packaging_command_table.py tests/test_cli_help_is_short.py -q && npx markdownlint-cli2 "docs/**/*.md" "*.md" ".claude/**/*.md" ".agents/**/*.md" ".opencode/**/*.md"
```

Expected: all pass, lint clean. (`bash scripts/check_local.sh` in
Task 11 runs the same lint CI does; this is the quick loop.)

- [ ] **Step 6: Commit**

```bash
git add -A docs AGENTS.md README.md DEVELOPER.md mkdocs.yml config.toml.example bench/bench_review_cost.py chitragupta/review/_claims.py chitragupta/review/synthesis.py chitragupta/review/_book_paths.py chitragupta/review/citekey_union.py
git commit -m "Document the verbatim digest and move every count it changed"
```

---

### Task 11: version, full checks, PR

- [ ] **Step 1: Bump the version**

`pyproject.toml`: `version = "6.139.0"`. MINOR: a new module and a new
subcommand, nothing existing changes shape.

- [ ] **Step 2: Full suite with coverage**

Run: `.venv-full/bin/python -m pytest --cov --cov-report=term-missing -q`
Expected: 0 failed, 100% line and branch. Any `Missing` line under a
`_digest_*` or `verbatim_digest` module gets a test in the file that
owns it (Tasks 2-6), not a `pragma`. The likely gaps: `_excerpt`'s
long-text branch (add a 120-character sentence to `TestItems`),
`_mismatch` with an empty `missing` list (a sentence whose distinctive
words are all on the page but whose flattened stream is not: pin with a
reordered sentence), `_spans_lines` with no spans and no unverifiable
runs (already `test_a_clean_digest_says_so`), and `_command` with the
default formats (add a run without `--formats`, which will try to
render `tex`/`pdf` and skip them with a warning on a host without
pandoc).

- [ ] **Step 3: CI's lint job**

Run: `bash scripts/check_local.sh`
Expected: exit 0. It runs the version-bump check, pylint under 3.13,
both ruff checks, shellcheck, actionlint, markdownlint, the node tests
and Vale.

- [ ] **Step 4: Smoke test against a real corpus**

On a host with a synced ledger (the committed sample project under
`docs/examples/sample-project/` has five CC0 papers and their `.bib`):

```bash
cd docs/examples/sample-project
python -m chitragupta.corpus sync
# write a six-line digest by hand from content/parsed/<one of its citekeys>.txt
python -m chitragupta.draft gate content/drafts/dt-overview/notes.digest.md
python -m chitragupta.review digest content/drafts/dt-overview/notes.digest.md --formats md
# delete one sentence of your own, then:
python -m chitragupta.review digest content/drafts/dt-overview/notes.digest.md --baseline content/review/dt-overview/notes.digest.json --formats md
git status --short   # the digest must not appear
```

Record the copied fraction and the `fell:` line in the PR's test plan.
Do not commit the digest or its report.

- [ ] **Step 5: OpenCodeReview**

Run the OpenCodeReview plugin over the branch (`/open-code-review:review`)
and act on what it finds; if the host has no LLM endpoint, run the
`pr-review-toolkit:code-reviewer` agent instead and say which ran in
the test plan.

- [ ] **Step 6: Open the PR**

Title: `Add the verbatim digest: a sixth genre and the review digest aid`.
Body from `.github/pull_request_template.md`, `## Description` naming
discussion #991, `## Commit message` fence:

```text
- Add `python -m chitragupta.review digest`, the eleventh review aid:
  splits a verbatim digest into citation-terminated runs, verifies
  each against the cited source with the quotation matcher, and lists
  every sentence that is not verified source text as a `[surfaced]`
  item in three classes, with the copied fraction as the headline.
- Add `--baseline` to it, comparing a run against an earlier `.json`
  by item id, with per-class counts before and after.
- Add `digest` to `dossier.GENRES` and to the genre-to-unit tables.
- Add the `verbatim-digest-writer` skill on all three harnesses, and
  deny its bare name in `.opencode/opencode.json`.
- Keep `review digest` off the agenda: `agenda/_sources.AID_NAMES`
  excludes it, so existing agendas are byte-identical.
- Move `require_reviewable` and `report_dir` to `review/_paths.py`,
  re-exported unchanged, to keep `review/__init__.py` under C2.
- Expose `_claims.claim_blocks`, the per-block half of
  `claim_sentences`, for the digest parser.
- Ignore `content/drafts/**/*.digest.md`, pinned by a test that asks
  git about the path the aid names.
- Add docs/VERBATIM-DIGEST.md and move every aid, genre and skill
  count the change made false.
- Bump the version to 6.139.0.
```

Check it with `python scripts/merge_pr.py --check` before opening. Then
the rest of the cycle: green CI, one Copilot round, re-check `main`,
`python scripts/merge_pr.py <N>`, tag, release asset.

## 🔎 Self-review against #991

| Discussion item | Where it lands |
| --- | --- |
| Skill `verbatim-digest-writer`: refuses on an empty ledger, keeps a dossier, writes the digest, runs `draft gate` and `review digest` before presenting | Task 9, steps 0, 7, 9 |
| Genre entry `digest` in the dossier's registry and `docs/GENRE.md` | Task 7; Task 10 step 2 |
| Review aid `digest` in `chitragupta/review/verbatim_digest.py` plus its renderer | Tasks 2-6 |
| Registration: one key each in `review.AIDS` and `review/_registry.AIDS`, drift check keeps them wired | Task 6 steps 3-4 (the existing `RuntimeError` in `_registry.py` is the drift check) |
| Ignore rule plus a test asking git | Task 8 |
| Docs: `docs/VERBATIM-DIGEST.md`, rows in REVIEW.md, GENRE.md, CLI.md, a router line in AGENTS.md | Task 10 steps 1-2 |
| Data flow ledger → dossier → `<name>.digest.md` → gate + `review digest` → `content/review/<topic>/<name>.digest.{md,json}` | Task 6 `report_target`; Task 9 steps 0-9 |
| Plain text plus closing citation; attribution rule | Task 2 `_segments`, `runs` |
| Whole-run match first, "assembled from N places" as information | Task 3 `check_run`, `_sentence_level` |
| Sentence-level fallback: `copy-mismatch` with differing words, `unquoted-text` | Task 3 `_mismatch`, `_own` |
| `unsupported-text` on top, via lexical provenance | Task 3 `_own` with `score_claim` |
| Page as a hint; actual page reported | Task 3 `page_note`; Task 2 `cited_pages` |
| Headline copied fraction; classes worst first; all `[surfaced]`; agenda-format item lines with 12-character ids | Task 4 |
| `--baseline` with per-class counts and copied fraction | Task 5 |
| `agenda` and `agenda-reviser` untouched; no "digest: not run" line | Task 6 step 4 (`AID_NAMES`), Task 10 "do not touch" row |
| Repair loop, four keep-conditions, only when asked | Task 9 step 10; `fell` in Task 5 |
| Every check exits 0; no gate | Task 6 `run`; global constraints |
| Open questions 1-4 | Decisions table |
| Cons: coarse attribution, parse quality, half-copied sentences, lexical support, surface area, SOUL.md tension | Decisions table; docs/VERBATIM-DIGEST.md "What it does not do" and "The rule it lives under" (Task 10 step 1) |
| Pros: existing `verbatim scan` catches leakage | Skill's opening paragraph; AGENTS.md router line |

Type consistency checked: `Run.pages`/`Span.cited` are `(first, last)`
tuples; `Span.pages` is a tuple of found pages, serialised as a list;
`items` rows carry `class`, never `cls`; `compare` reads `counts` and
`copied_fraction` from the payload `payload()` writes; `report_target`
is called with the resolved draft `require_reviewable` returned.
