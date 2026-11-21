# 🗺 The auto-improvement loop: what is built

Status: **implemented.**

`python -m chitragupta.review agenda <draft>` is a command, and the
`agenda-reviser` skill consumes it. All eleven review aids emit JSON
([CLI.md](CLI.md)). This document states *what* is built and *what it
must satisfy*. The one step not built, a gating decision, is declined;
see [Build order](#-build-order).

Every "why" is in
[AUTO-IMPROVEMENT-RATIONALE.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/AUTO-IMPROVEMENT-RATIONALE.md):
why the aid sits in the review layer, why most item classes may not be
acted on, why the loop stops instead of running overnight, and the one
documented rule it cannot satisfy without the user's approval.

**Written for** someone implementing it. It assumes
[ARCHITECTURE.md](ARCHITECTURE.md) for the four layers and
[DRAFT-ITERATION.md](DRAFT-ITERATION.md) for the dossier and the drift
sweep. **Not covered here:** the prose and house-style half
([HOUSE-STYLE.md](HOUSE-STYLE.md)). Corpus growth is out of scope:
nothing below fetches a paper, writes `bibliography.bib`, or writes the
ledger.

## 🏗 The shape

- The **deterministic half** is a further review aid: it reads eight
  other aids' findings plus the dossier's drift report and emits one
  ranked, deduplicated worklist.
- The **generative half** is a skill: it consumes that worklist, repairs
  what may be repaired unattended, re-verifies each repair, and hands the
  rest to the human.
- The **human closes the loop**: they accept the diff, and no code path
  runs the skill automatically.

## ▶ 1. `--json` on every review aid

`chitragupta/review/__init__.py` owns one output contract for the
layer, with a JSON sibling beside the Markdown, at
`content/review/<topic>/<stem>.<aid>.json`. The JSON is a second
serialisation of the same findings, never a second computation; the
Markdown stays authoritative. It carries no timestamp, so two runs over
an unchanged draft and corpus produce byte-identical JSON.

The plumbing is `review.envelope()`, which carries provenance and the
not-a-verdict notice as data, and `review.write_json()`. `provenance`,
`agenda` and `digest` write by default, and the rest only under
`--write`, so the `agenda` can find an aid's JSON missing; step 2
accounts for that.

## ▶ 2. The `agenda` aid

`python -m chitragupta.review agenda <draft>` is a key in `review.AIDS`.
Deterministic, stdlib-only, no LLM, tier 1, takes no lock, exits 0
whatever it finds.

**Reads:**

- the eight aids' `.json` for this draft, each optional, and skipped
  with a note when absent;
- `chitragupta.dossier.drift(dossier_dir)`, for missing citekeys;
- `recorded_but_uncited(draft)`, for the citekeys the dossier still
  records and the draft no longer cites, deliberately read without a
  `dossier stamp` baseline;
- the draft's own headings (`dossier.sections()`), so every item carries
  a section anchor;
- `<stem>.accepted.json`, the items a person has already considered and
  accepted (section 5); optional, and it raises no class of its own.

**Writes:** `<stem>.agenda.md` and `<stem>.agenda.json` under
`content/review/<topic>/`, via the layer's existing `write()`. Under
`--accept`, also `<stem>.accepted.json` in the same directory.

**Merges** one finding that two aids report into one item. **Every
finding carries a stable identity**, `(aid, class, section anchor,
citekey, hash of the matched span)` or equivalent, so "this finding is
gone" and cross-aid dedup are decidable across runs. **Order:** class
order as [AGENDA.md](AGENDA.md#-the-classes) lists it, then the verbatim
scan's severity bucket, then position in the draft.

### 🏷 Item classes

[AGENDA.md](AGENDA.md#-the-classes) owns the class table and
[AGENDA.md](AGENDA.md#-unattended-versus-surfaced) which classes are
unattended. The reasons behind the dispositions that are not obvious:

- **`recorded-but-uncited`, surfaced.** It cannot tell a citation the
  user deleted from evidence transcribed and never cited, which want
  opposite repairs, so deleting recorded evidence unattended could lose
  real work. The repair is `dossier prune`, which a person confirms.
- **`verbatim-run`: long runs, runs marked `names`, and every
  `embedding`-tier finding are surfaced.** Severity ignores the tier, and
  acting on an embedding alignment would authorise an edit on the
  evidence of a similarity score; `verbatim recheck` will not even count
  that tier.
- **`prose`, unattended unless a finding carries `repair: "review"`**
  (`WideCodeLine`, `AcronymCase`, and a dialect finding whose dialect
  came from the host-wide `config.toml` or whose match starts with a
  capital letter).
- **`misquoted`, surfaced.** Binary, but the defect is in `evidence.md`
  and `agenda-reviser` edits drafts, so there is no unattended repair.
- **`claim-support`** is `support`'s own class, ranked worst-first and
  never thresholded, because a cutoff would claim a precision the corpus
  does not support ([REVIEW.md](REVIEW.md)).

Two classes are deliberately absent: `uncited-source` (from `coverage`)
and `candidate` (from drift). Declining to cite a surfaced paper is
usually correct, and as standing items they would be volume a person
triages every cycle. `coverage` and `dossier status` still report them
when asked.

## ▶ 3. The `agenda-reviser` skill

A skill, not a `chitragupta/` module, named for its input like the two
revisers it joins. Per item:

1. Dispatch the existing `draft-reviser` discipline: read `scope.md` and
   `steering.md` first, edit inside the named section with `Edit`, never a
   whole-file `Write`.
2. Re-run `python -m chitragupta.draft gate` **and** the aid that raised
   the finding. Accept only if both come back clean.
3. Re-run every other aid and compare by finding identity (R4). If the
   repaired item is not `resolved`, or any objective-class finding is
   `new`, revert the edit and escalate the item.
4. Log the attempt in `revisions.md`, outcome included, refusals
   included.

**Termination:** at most two attempts per item. Passes continue only
while `objective_class_count` strictly falls, and stop at the agenda's
`pass_bound` (3). The loop never adds a claim, and on the unattended
classes only removes or rewords existing ones.

## ▶ 4. Acceptance and rollback

- **Before the pass:** one `python -m chitragupta.draft dossier export <slug>`.
- **Within the pass:** the skill holds each section's pre-edit text and
  re-applies it when an item fails, leaving earlier accepted items
  intact.

A failed attempt is logged in `revisions.md` and **never** in
`rejected.md`. The human is presented with a diff plus the
`revisions.md` entries, and accepts.

## ▶ 5. Considered and accepted

This "accept" takes *a finding as it stands*: "I have read this, and I
am leaving the draft as it is."

```bash
python -m chitragupta.review agenda <draft> --accept <item id>
```

Without it, a surfaced item a person has decided about returns on every
run, and `rejected.md` records turned-down candidates, not considered
findings.

**Keyed on the identity the item already has**, R2's `item_id` in
`chitragupta/review/agenda/_identity.py`. Suppressing by citekey or
section alone was rejected: it would hide a new defect in an accepted
section. **Reopening is free**: the id hashes the span, so editing the
accepted text raises a new id and the item returns. **The agenda still
recomputes from the aids**; acceptance is a filter on a fresh list, and
a durable queue with mutable item state was rejected.

**Three classes may be accepted:** `claim-support`, `uncited-claim` and
`unsupported-claim`. Every other class is refused in code, with exit
code 2. **`misquoted` is deliberately excluded**, for three reasons,
any one sufficient:

1. It is surfaced for a write-set reason, not a judgement one.
2. `chitragupta/review/_quotation_match.py`'s residual `absent` findings
   mix correct quotes the matcher cannot verify with fabricated ones,
   and R3 bars a continuous `near_miss_score` from telling them apart.
3. Its identity is keyed on the quote in `evidence.md`, so a re-parse or
   replaced PDF can make it newly true with the id unchanged, leaving a
   real fabrication suppressed.

[AUTO-IMPROVEMENT-RATIONALE.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/AUTO-IMPROVEMENT-RATIONALE.md#-why-misquoted-may-not-be-accepted)
has the measurement and what would reopen it.

**The record is auditable.** `<stem>.accepted.json` holds one row per
accepted item, and the report lists each under `## Accepted`, marked
`suppressed` or `not raised by this run`. Under `--baseline`, accepted
items are reported as `accepted`, never `resolved`. The record lives
under `content/review/`, so `dossier export` bundles it; an unreadable
record suppresses nothing. Bulk acceptance of a class is not built,
since it would silence findings nobody read.

**Stale-span refusal runs before acceptance.** `build_agenda` refuses
first and suppresses second, because an item no longer about any text
has not reached the question of what a person decided. The other order
would mark a record `suppressed` for an item this run never raised. The
two are disjoint today (only `verbatim-run` and `prose` carry a span,
and neither is acceptable), but that is a coincidence, so a test asserts
it.

## 🎯 The requirements

Twelve obligations, each phrased so a reviewer can tell whether it has been
met.
[AUTO-IMPROVEMENT-RATIONALE.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/AUTO-IMPROVEMENT-RATIONALE.md#-mapping-the-method-onto-this-pipeline)
says where each comes from.

| | Requirement |
| --- | --- |
| **R1** | The skill's write-set is exactly the draft and `revisions.md`, plus one narrow exception: after a person answers "quotation" to a long verbatim run, the `quote:` line recording that run in `evidence.md`. That line adds a check (`review quotation`) and silences none. It may *execute* an aid, the gate and `style_check`; it may not edit them, nor the boilerplate allowlist, `rejected.md`, `scope.md`, or anything under the corpus layer. |
| **R2** | Every finding carries an identity stable across runs. |
| **R3** | An unattended item's check is **binary**. No continuous score is ever the thing being optimised. |
| **R4** | After each accepted edit, every aid re-runs and the result is compared by R2's finding identity rather than by a total: the repaired item appears in `resolved`, and no objective-class finding appears in `new`. A count that holds level because one objective finding was swapped for another is a failed edit, not a neutral one. Otherwise the edit reverts. |
| **R5** | Reverting one item leaves every earlier accepted item intact. |
| **R6** | Every attempt is logged with its outcome, refusals included, and no machine outcome is ever written to `rejected.md`. |
| **R7** | Two attempts per item; passes continue only while the objective-class count strictly falls, up to `pass_bound`; then hand back. |
| **R8** | Where a deletion and a rewrite both pass, the smaller diff wins. |
| **R9** | The agenda taken before the pass is the recorded baseline, and the closing report is stated against it. |
| **R10** | The aid is registered in both `review.AIDS` and `review._registry.AIDS`, with its help line in `chitragupta/command_help.py`; the skill's `description` names its triggers; and both appear in AGENTS.md's layer bullets, CLI.md, the README tables and `mkdocs.yml`. |
| **R11** | No hook, no scheduled job and no other skill invokes the `agenda-reviser` skill. Its only trigger is a person asking. |
| **R12** | An item whose draft text has changed since the aid found it is **dropped and reported, never repaired**. No merge, no similarity-based relocation, no best-effort application. The finding is re-derived on the next run against the current text. |

## 👥 Who calls it, and when

**The aid: anyone, at any time.** The bare
`python -m chitragupta.review agenda <draft>` is free, deterministic,
read-only and exits 0. Its `--baseline` mode re-runs the eight aids
first (`chitragupta/review/agenda/_refresh.py`), so that mode alone is
neither free nor read-only.

**The skill: only a person, on a draft they consider finished.** Its
`SKILL.md` description names three occasions: before rendering or
submitting; after a `sync` moved the corpus and `dossier status --all`
named the draft; on returning to a draft after weeks away. **Nothing
else may call it** (R11): no hook, scheduled job, genre skill or
`draft-reviser`
([why](https://github.com/prasadtalasila/chitragupta/blob/main/docs/AUTO-IMPROVEMENT-RATIONALE.md#-why-only-a-person-may-start-it)).

**A stale input is reported, not merged.** An aid report older than the
draft (by file mtime, since reports carry no timestamp) is named as
stale in the header.

**A stale *span* is refused, not relocated** (R12). If the author
revises a passage after the aid ran, a repair would target text that no
longer exists. `build_agenda` drops any item whose span is gone and
reports it under `## Refused as stale` (`stale_spans` in the `.json`);
it is not counted and is re-derived on the next run. Three alternatives
are refused:

- **Merging the two edits**, as `llm_wiki` does: the human's edit wins
  by default, and refusal gets that for free.
- **Re-locating the span by similarity**, which would authorise an edit
  on a similarity score. A test keeps any fuzzy matcher out of
  `chitragupta/review/agenda/`.
- **Locking the draft**: a person editing their own draft is the point.

Only exact draft spans are checked (`verbatim`'s `draft_text` and
`style_check`'s Vale match), and in practice only `verbatim-run` is
refused, since `prose` is recomputed each build. Dossier-derived classes
are never refused on this basis.

## 🪝 How the loop is reached

Nothing here is discovered by scanning the filesystem, and a piece that
is built but not registered is dead code.

| Piece | How it is found | Consequence of omitting it |
| --- | --- | --- |
| The `agenda` aid | a key in `review.AIDS` (`chitragupta/review/__init__.py`) **and** in `review._registry.AIDS`, whose help line `chitragupta/command_help.py` holds | `chitragupta/review/_registry.py` raises `RuntimeError` if the two dicts disagree, so a half-registered aid fails loudly at import instead of writing a report nothing can find |
| The `agenda-reviser` skill | its `SKILL.md` frontmatter `name` and `description` | This is the *only* trigger mechanism. A skill whose description does not match how a user phrases the request is never invoked, however correct its body |
| Both, for an agent working on a draft | [AGENTS.md](https://github.com/prasadtalasila/chitragupta/blob/main/AGENTS.md)'s layer bullets, which enumerate the aids (Layer 4) and the skills (Layer 2) | An agent following AGENTS.md would not know either exists |
| Both, for a human | [CLI.md](CLI.md) for the command and its flags; [GENRE.md](GENRE.md) for which reviser handles what; README's review-aid block | Undiscoverable outside the source |
| The docs themselves | `mkdocs.yml` nav and the README documentation tables | Invisible in the site nav. Not a build failure: `nav.omitted_files` is INFO-level, and `mkdocs build --strict` still passes |

The first two rows are functional requirements, not administrative ones.
[SOUL.md](../SOUL.md) is deliberately absent from the list
([why](https://github.com/prasadtalasila/chitragupta/blob/main/docs/AUTO-IMPROVEMENT-RATIONALE.md#-why-only-a-person-may-start-it)).

## ⚡ The cost ladder

Do the free thing first, and pay only for what it could not decide
([LADDERS.md](LADDERS.md)'s shape).

1. **Detection and rejection, at zero tokens.** Every aid, `style_check`
   and the gate are stdlib, deterministic and modelless. This rung runs
   to exhaustion before rung 2 begins.
2. **A single-shot edit** where the fix is local and the re-check binary:
   a dialect slip, a defect marker, an acronym. The finding already names
   the span. The span bounds the edit, not its consequences: a repair
   that changes a quantity, an enumeration or a name is re-read against
   the passages that refer to it before it is accepted, and an item
   another passage refers to is rung 3 work.
3. **A dispatched reviser**, only for items needing the surrounding
   argument in context. The expensive rung, and the short list.

Model tiering is the fourth rung; applying the settled policy to any new
mechanical stage is a question for the build, not a blocker.

## 🗄 What accumulates across drafts

Instrumentation that would outlive any one draft. None of it is built or
read today.

- **Which retrieval queries paid**: `retrieval.md`, `evidence.md` and
  `rejected.md` across drafts.
- **Which item classes the human accepts**: a labelled record of the
  loop's reliability, the reports any gating threshold would need.
- **Where the tokens went**: `dossier status`'s per-revision retrieval
  cost, the measurement
  [TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md)
  currently estimates.

The house-style counterpart is in [HOUSE-STYLE.md](HOUSE-STYLE.md).

## 🗺 Build order

Built: the amendment that lets a driver invoke a review aid (which may
still never block a draft), `--json` on every aid, severity buckets and
the per-host allowlist, `agenda`, `agenda-reviser`, and `style_check.py`.
The gating decision is declined
([REQUIREMENTS.md §5.1](https://github.com/prasadtalasila/chitragupta/blob/main/docs/REQUIREMENTS.md#-51-current-position)).

## 🚧 B5 is a separate mechanism, not a widening of this one

The five genre skills' pre-gate self-feedback step (B5, in
[GENRE.md](GENRE.md)) also critiques a draft against a deterministic
count, but R11 does not cover it:

- It runs **inside** a genre skill, on the draft that skill is
  producing; R11 governs who may start a *reviser*.
- It is a sibling mechanism, not part of this track's build order.
- It calls `verbatim scan`/`recheck`, `draft style` and `dossier status`
  directly, and never `review agenda`.
- Its termination condition is the **declared query list** in
  `outline.md`: "every declared query ran and none came back empty" is
  reported as a binary (R3), never a bound on editing or a condition of
  presenting. A three-repair cap bounds the editing.

## 🚫 What this does not change

- **No new gate.** `chitragupta.draft gate` remains the only one; the
  gating decision is declined ([Build order](#-build-order)).
- **No corpus growth.** The loop never fetches, never writes the ledger,
  and never proposes a paper that is not already in it.
- **No new layer.** Four layers, one new aid in the fourth, one new skill
  in the second.
- **No new entry point.** `python -m chitragupta.review agenda <draft>` is
  one verb under an existing front door, at depth 1.
- **The review layer still never blocks.** `agenda` exits 0 with a full
  worklist, exactly as the other ten aids do with findings.
