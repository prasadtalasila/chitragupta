# Several `quote:` lines per evidence block (#1174)

Status: **design approved in conversation and signed off with changes
(see "Sign-off changes"); being built.** Written 2026-11-21.

**Written for:** whoever implements #1174.

**Assumed:** the issue text, and `chitragupta/dossier/_evidence_check.py`,
`chitragupta/evidence_appendix.py`, `chitragupta/review/quotation.py`,
`chitragupta/review/_quotation_render.py`,
`chitragupta/review/agenda/_items_findings.py`, `docs/DOSSIER.md` and the
skills as of `9862c8cb0`.

**Not covered here:** a check that every quotation in a draft's body has a
matching `quote:` in its dossier, and continuation lines glued onto a
`quote:` value (see "Out of scope").

## Intent

An `evidence.md` block records one verbatim passage per source. A second
`quote:` line is silently dropped: `fields()` keeps the first value of
each field. In #1172's dogfood run, 129 of 160 `quote:` lines were never
read, and nothing warned. A survey that quotes one paper twice can record
only one of the two quotations, so the other is never checked by
`review quotation` and never printed in the evidence sidecar.

After this change a block may carry any number of `quote:` lines. Each one
is checked, printed and reported on its own.

A second, smaller failure from the same run is fixed alongside: a quote
written as `"..." (p. N)` reads as `absent`. Testing against the real
source shows the quotation marks are harmless (the matcher flattens to
`[a-z0-9]`), and the trailing page locator alone causes the miss. Measured
on 2026-11-21 against a 12-word definitional sentence from a real source
in the owner's corpus, found exactly on its page when written bare:

| The same `quote:` written as | Verdict |
| --- | --- |
| bare | found |
| in straight quotation marks | found |
| in curly quotation marks | found |
| bare, then `(p. 24)` | absent |
| bare, then `(p.24)` | absent |

## Goals, non-goals, anti-goals

- **Goals.**
  - Every `quote:` line in a block is read, checked by `review quotation`,
    printed by the evidence sidecar and compared by `check-evidence`.
  - A trailing page locator and surrounding quotation marks no longer
    cause a false `absent`.
  - A repeated single-valued field (`claim:`, `relevance:`, `support:`)
    is warned about instead of dropped silently.
- **Non-goals.**
  - Several `claim:` lines per block. One block still has one claim.
  - A page number field. The page is still derived by locating the quote.
  - Changing the digest's check of its copied runs. `review digest` still
    checks each run where it stands.
- **Anti-goals.** Any of these makes the change a failure even if it works:
  - Loosening "a `quote:` is captured only when a quotation is intended".
    The bar applies to each quote; it is not lowered.
  - An existing `misquoted` finding id changes for a quote whose text did
    not change.
  - `misquoted` becomes unattended, acceptable, or counted in
    `objective_class_count`.
  - Any aid rewrites `evidence.md`.

## Decisions

Each decision lists the options weighed and which one was chosen.

### 1. Format: repeat the `quote:` line (chosen)

```markdown
## `sample_dt_sync_2023`

relevance: ...
claim: ...
quote: <first verbatim passage>
quote: <second verbatim passage>
```

Rejected:

- **A `quotes:` bulleted list.** The bulleted shape has no end marker, so
  the last value runs on into the next field. That is the failure the
  owner's DT-book dossier already hit.
- **One block per quote.** `check-evidence` already warns "N blocks under
  one citekey", and only the first block is ever read.

Order is file order. Identical `quote:` lines in one block count once
(builder's call, recorded here).

### 2. Wrapped quotes: normalise silently (chosen: option B)

The parser strips, repeating until nothing changes:

- a trailing page locator: `(p. 24)`, `(p.24)`, `(pp. 12-13)`,
  `(pp. 12–13)`, `(page 24)`, and the same in square brackets;
- surrounding quotation marks, when the value both starts and ends with a
  matching pair: `"..."`, `“...”`.

This happens once, in the parser. Every consumer sees the normalised
text: the checker, the sidecar, `finding_id` and the agenda's `item_id`.
So a later clean-up of the dossier line does not change any id.

Rejected:

- **Warn only (A).** No silent change, but every wrapped quote stays
  `absent` until someone edits it.
- **Warn and normalise (C).** The warning would ask for a fix the code has
  already made, which trains people to ignore warnings.

Known costs of B, accepted: a page someone wrote by hand is discarded
without being compared to the located page; a source sentence that itself
ends in `(p. N)` would be checked without it. On the owner's dossiers,
0 existing quotes end in a page locator, so no current finding changes.

### 3. Drafting stage

The evidence-recording wording changes from "a `quote:` line" to "one
`quote:` line per passage you intend to quote", in each skill that
records evidence. The rule that each quote is written bare, on one line,
with no page, is stated once in `genre-steps.md` §5 and `docs/DOSSIER.md`.
The parser forgives a page and marks (decision 2), but the skills still
ask for the bare form.

Critique (step 10 and `critique.md`) does not change: it already reads
every `quote:` and never touches one.

### 4. The draft and the evidence sidecar

The draft body does not change shape. A survey, thesis or textbook chapter
can now back a second attributed quotation from one source.

The sidecar keeps one heading per source and prints one blockquote per
quote, in file order:

```markdown
### <attribution> `sample_dt_sync_2023`

> "<first verbatim passage>"

> "<second verbatim passage>"
```

### 5. Review aids

- **`review quotation`** checks each quote separately. `finding_id` stays
  keyed on (citekey, quote text), so a quote checked today keeps its id.
  The header reports `Quotes checked: N` (quotes, not sources). A
  confirmed line is printed per quote.
- **`dossier check-evidence`** compares the claim against each quote and
  warns on any that crosses the threshold, naming which quote ("quote 2").
  It also warns on a repeated single-valued field:

  ```text
  [warn] sample_dt_sync_2023: 2 claim: lines -- only the first is read. Merge them.
  ```

- **`review digest`, `verbatim scan`, `claim-support`:** no change. They
  read the draft, not the dossier.

### 6. Agenda and agenda-reviser report

One `misquoted` item per absent quote. `item_id` is unchanged (it already
hashes the quote text). The summary names which quote, so two quotes that
share their first 80 characters do not render as identical lines:

```text
- `<id>` [surfaced]: `[@sample_dt_sync_2023]`'s quote 2 of 2 was not found in its source: <second verbatim passage>
```

`misquoted` stays surfaced and not acceptable. `objective_class_count`,
`pass_bound` and the R4 stop rule do not move. `agenda-reviser` lists more
items and still never edits `evidence.md`.

### 7. The digest records the passages it leans on most (chosen: option 2)

`review-digest` step 2 changes from "one `quote:`" to "a `quote:` for each
passage you lean on most", not one per copied run. `review digest` remains
the check for every other run. Rejected: recording every copied run, which
would duplicate the digest body in `evidence.md` and check every run twice.

## Changes, by file

**Parser:** `chitragupta/dossier/_evidence_check.py`

- `quotes(block) -> list[str]`: every `quote:` value, normalised
  (decision 2), de-duplicated, in file order.
- `fields(block)` keeps returning the first value of each single-valued
  field. Whether its `quote` key stays (as the first normalised quote) or
  goes is the builder's call; every quote consumer must move to `quotes()`.
- `repeated_fields(block) -> dict[str, int]` for the new warning.
- `reworded_claims` returns per-quote results; `_cmd_check_evidence`
  prints the quote's position and the repeated-field warning.

**Sidecar:** `chitragupta/evidence_appendix.py`

- `quoted_spans` returns `dict[str, list[str]]`. `build` prints one
  blockquote per quote. `_blockquote` also strips curly marks; this is
  redundant once the parser normalises, and is kept only if a test needs it.

**Quotation aid:** `chitragupta/review/quotation.py` and
`_quotation_render.py`

- One `Checked` per quote, carrying its position and its block's quote
  count. The finding dict gains `index` and `of`; `id` is unchanged.

**Agenda:** `chitragupta/review/agenda/_items_findings.py`

- `misquoted_items` writes "quote N of M" into the summary when M > 1.
  `item_id` arguments are unchanged.

**Docs:** `docs/DOSSIER.md` (A2 contract: several `quote:` lines, one line
each, page and marks forgiven), `docs/VERBATIM-DIGEST.md` (lines that say
"one `quote:`" or "main passage"), and any `docs/CLI.md` text that
describes the sidecar or `review quotation` output. Leave out pages that
are not in the mkdocs site and the five `WRITE-A-*` guides.

**Skills**, in all three copies (`.claude/`, `.agents/`, `.opencode/`;
`tests/test_skill_harness_copies.py` enforces that they agree):

- `.claude/skills-common/references/genre-steps.md` §5
- `review-digest` step 2
- `survey-writer`, `thesis-chapter-writer` and `textbook-chapter-writer`,
  at their evidence-recording step
- `deep-research`, where Phase 2 and Phase 5 transcribe packets
- `draft-reviser` and `corpus-reviser`, where they read `quote:`

**Sample project:** give one block in
`docs/examples/sample-project/content/dossiers/` a second `quote:`, so the
shipped example exercises the feature. The passage must be real: take it
from the sample corpus and confirm it with
`_quotation_match.locate()` before writing it. `regenerate.sh` rebuilds
only the uncommitted substrate (ledger, parses); the committed report to
refresh is that draft's quotation report (see "Shipping").

**Tests**, by file:

- `tests/test_dossier.py`: `quotes()` returns several in order and
  de-duplicated; normalisation covers each locator form and both kinds of
  quotation marks; a quote that merely contains `(p. 3)` mid-span is left
  alone; `repeated_fields`; per-quote reword warning.
- `tests/test_evidence_appendix.py`: several blockquotes under one heading.
- `tests/test_review_quotation.py`: each quote checked; the first quote's
  `finding_id` equals its value before this change; a `(p. N)`-suffixed
  quote that used to be absent is now found.
- Agenda tests: "quote N of M" summary; ids unchanged.

## Migration

None needed. Measured on the owner's dossiers on 2026-11-21:

- 0 blocks hold more than one `quote:`.
- 0 quotes end in a page locator.
- 11 quotes are wrapped in straight quotation marks
  (`survey/digital-twin-architectures`, `thesis-chapter/dt-ecosystem`).
  Stripping the marks changes their `quotes[].id` in the quotation
  report's JSON. All 11 were `found` in the last filed reports, so no
  `misquoted` item id changes, and nothing in `chitragupta/` reads
  `quotes[].id`.

## Shipping

- **Version:** MINOR (new backward-compatible behaviour), in the same PR.
- **One PR** carries the code, docs and skill wording. It is opened and
  taken to green CI; it is not merged in this session.
- **Bench:** not run in this PR. The standing rule is to bench a skill
  edit before merging, so the PR says the skill wording still owes a
  Claude Code bench (3 runs before, 3 after) before it merges.
- **Sample project:** after adding the second `quote:`, re-run only that
  draft's `review quotation --write` and commit its real output. Its
  agenda report changes only if a quote is absent, so it is re-run only
  in that case. The draft body is not changed.

## Out of scope (separate issues to offer)

1. **Glued continuation lines.** A line under `quote:` that is not a known
   field (`used in: ...`) is read as part of the quote and fails it.
   Decision 2 does not cover this.
2. **Unbacked quotations in the draft.** A quotation in a draft's body with
   no matching `quote:` in its dossier is checked by nothing:
   `verbatim scan` exempts it as `quoted` because it has marks and a
   citation. This change makes backing every quotation possible; it does
   not require it.

## Sign-off changes

A second reviewer signed the design off with these changes. Where one
conflicts with a section above, this section wins.

1. **Id stability, restated.** Anti-goal 2 holds for a quote whose
   *normalised* text is unchanged. A quote that is wrapped in marks or ends
   in a locator today is re-keyed once by decision 2: on the next
   `agenda --baseline` its old item reads as `resolved` and a new one as
   `new` (surfaced, so `objective_new` stays 0). The release notes say so,
   and a test pins the one-time re-key.
2. **Quotation-mark rule.** Strip a surrounding pair only when the value
   opens with `"` or `“`, closes with `"` or `”`, and the interior holds
   no further double quotation mark of any kind. So
   `“Twin” is used loosely, as is “shadow”` is left alone. A trailing full
   stop after a locator (`(p. 24).`) goes with the locator. A trailing
   `[p. 24]` was already tolerated as an end-elision; stripping it moves
   its tier from `elided` to `exact`, and the tests expect that.
3. **Position on every line.** `quotes[]` in the JSON gains `index` and
   `of`. The confirmed, not-checkable and absent lines all say
   "quote N of M" when M > 1. `docs/CLI.md`'s key list is updated.
4. **Old reports still read.** `misquoted_items` uses `.get` for
   `index`/`of` and falls back to today's summary for a report filed
   before the upgrade.
5. **C2 headroom.** `agenda/_items_findings.py` is 3 lines under its cap:
   the summary wording goes in a helper outside it. The normalisation
   regexes live in `_evidence_check.py`.
6. **Skill byte caps** (`tests/test_skill_size.py`). Reword net-zero
   where possible; where not, raise the cap with a reason row. Keep the
   field name `quote:` inline in each step. `draft-reviser` and
   `corpus-reviser` mention `quote:` only for legacy `support:` blocks,
   so they are not changed.
7. **More files.** `AGENTS.md` (the digest's "main passage" sentence),
   `docs/DOSSIER.md` (three possible fields, the digest sentence, the
   self-check paragraph), `docs/CLI.md` (sidecar, `check-evidence` row,
   quotation report and keys), `docs/REVIEW.md`, `docs/FEATURES.md`,
   `docs/VERBATIM-DIGEST.md`,
   `.claude/skills-common/references/render-and-references.md`,
   `survey-writer/references/survey.md`,
   `textbook-chapter-writer/references/textbook.md`, `genre-steps.md`'s
   "two kinds of warning" (now three), and stale docstrings in
   `review/quotation.py`, `evidence_appendix.py`, `_evidence_check.py`
   and `_quotation_match.py`.
8. **No sample-project quote is added.** Adding a `quote:` to a finished
   example breaks "never add a `quote:` after the fact", and the sample
   corpus has no reading-ordered passages to confirm one. Tests carry the
   feature. The sample's committed quotation reports change shape
   (`index`/`of`), so they are regenerated by re-running
   `review quotation --write` in the sample project, never hand-edited.
9. **Real citekeys only** in docs and tests: `sample_*` keys and existing
   fixture keys.
10. **Pinned behaviours.** `quoted_spans` omits a citekey whose list is
    empty. `check-evidence` does not print its clean line when a
    repeated-field warning fired. `build_report` fetches a source's
    passages once per citekey, not once per quote.

Left open, for a later issue: whether a reviser may add a second `quote:`
when a person asks for a new quotation from an already-kept source.

## Added after review: two follow-ups the owner settled

Raised while the PR was open, decided by the owner on 2026-11-21, and
built into the same PR.

1. **A value ends at the next field-shaped line.** A `quote:` (or any
   field) value used to run on to the next `relevance:`/`claim:`/`quote:`/
   `support:` line, so a `- used in: Section 2` note under a quote was
   checked, and printed in the sidecar, as part of it. A value now also
   ends at a later line that starts at the left margin, bare or
   bulleted with a dash, with up to three lowercase words and a colon. An indented
   continuation and a capitalised wrapped line still continue it. The
   cost: an unindented wrapped line starting `as follows:` is read as a
   field. Measured on the owner's dossiers: 249 claims change, 248 at a
   `used in:` line and 1 at a stray `- citekey:` line; no quote changes.
2. **A reviser may add a `quote:` when a person asks for that
   quotation**, in chat or by answering "quotation" to a long verbatim
   run. It is copied from the source passage just read, kept only if
   `review quotation` finds it (or reports it not checkable, said out
   loud), and logged in `revisions.md`. Never on the reviser's own
   judgement, never to populate the sidecar. The rule is stated once, in
   `genre-steps.md` §5; `draft-reviser` and `agenda-reviser` point at it.
   For `agenda-reviser` this amends `docs/AUTO-IMPROVEMENT.md`'s R1 with a
   narrow exception: the one `quote:` line a person's "quotation" answer
   asks for. R1 exists so a loop cannot silence its own detector; this
   line adds a check and silences none.

**It does not close the gap between a draft's quotations and the
dossier.** Follow-up 2 (a quotation in the draft body with no matching
`quote:`, or worded differently from it, is checked by nothing) needs a
check that pairs each cited quotation in the draft with a `quote:` of the
same source. Decision 2 here makes backing a requested quotation possible;
it does not detect one that was never backed.
