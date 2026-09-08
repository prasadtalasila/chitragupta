# Detecting and removing a de-cited citekey the dossier still records (#701)

Status: **done.** Written 2026-09-08 against `main` at 6.99.0.
Sub-defects 1, 3 and 4 landed in PR #754 (6.101.0), sub-defect 2 in
PR #755 (6.102.0).

**What changed on the way**, since a plan that no longer matches what
shipped is worse than no plan:

- **The prune primitive's file I/O.** The plan chose line-span
  deletion over substring matching, which was right. What it missed is
  that `Path.read_text(encoding=..., newline="")` -- the obvious way to
  preserve line endings -- takes `newline` only from Python 3.13, while
  `write_text` has taken it since 3.10. The local venv is 3.13 and CI's
  test legs are 3.12, so it passed every local check and `TypeError`d
  on both legs. Shipped via `path.open()` on both halves.
- **Preserving line endings needed its own fix, separate from the span
  decision.** Spans made the *deletion* exact, but the first
  implementation still read with universal newlines, so pruning one
  block from a CRLF dossier rewrote the whole file to LF. The unit test
  missed it by joining raw lines itself instead of reading the file
  back; a smoke test's `od` caught it.
- **`_verdict` grew a `recorded` set.** The plan's four refusals were
  right, but inferring "not recorded" from a missing `evidence.md` span
  reported a cited, `sections.md`-only citekey as unrecorded.
- **Three more doc surfaces than the plan found.** `docs/PACKAGING.md`'s
  command table, its stated leaf-command count (56 -> 57) and
  `tests/test_packaging_command_table.py`'s own constant are all
  machine-checked, and the plan's grep for the agenda class name found
  none of them -- the count sentence contains no subcommand name.
  `docs/FEATURES.md` and `docs/CLI.md`'s per-subcommand table needed
  sweeping too, plus three claims PR #754 falsified in
  `agenda/__init__.py`, `docs/REVIEW.md` and the agenda-reviser skill.
- **`_parse_evidence` needed a statement shed.** The plan measured the
  prototype at 24/25; the real version came in at 25/25 until three
  dict initialisers became one tuple assignment.
- **The item summary suffixed `.md` once after joining**, so a
  two-surface finding read "evidence, sections.md". Caught in the
  delegate-review pass, along with a docstring that claimed to reuse
  `_citekeys.CITED_FILES` and did not reference it.

**Written for** whoever implements #701, filed as the detail behind
Issue #700 ("Remove citations that are no longer in the draft text").
Four sub-defects, all confirmed against the code:

1. Only `evidence.md` is differenced against what the draft currently
   cites (`_draft_fingerprint.Staleness.orphaned_evidence`,
   `_draft_fingerprint.py:171`) -- a `sections.md` row keeping a stale
   citekey is undetected. Latent today (0 occurrences measured over 21
   real dossiers), and `dossier sections --citekeys --write` already
   regenerates `sections.md` wholesale, so this half self-heals; `evidence.md`
   has no such regeneration.
2. No removal primitive exists. `dossier --help` lists
   `init, status, mark-revision, stamp, sections, outline, brief,
   set-language, acronyms-suggest, check-evidence, list, export, restore`
   -- nothing prunes.
3. The review agenda has no finding class for "recorded but no longer
   cited". `agenda-reviser`'s own unattended repair for `missing-citekey`
   (de-citing the sentence) manufactures exactly this state, and nothing
   downstream sees it.
4. The four fingerprint findings (including `orphaned_evidence`) only
   compute once `Staleness.changed` is true, which needs a prior
   `dossier stamp` baseline. An unstamped dossier -- every dossier
   written before 2026-08-30, when stamping landed -- reports nothing.

**Assumed:** the issue's own framing constraint holds and is not
relitigated here -- `evidence_blocks - cited` cannot distinguish "the
user cut this citation" from "a candidate was transcribed and never
cited", so nothing may be deleted unattended. The fix is detection
everywhere the state can be recorded, plus a confirmable primitive, not
an automatic prune.

**Not covered here:** #699 (a distinct `references.py` bug, explicitly
out of scope in #701's own body); pruning `sections.md` (self-heals,
see decision 3); anything about `rejected.md` (never a target, see
decision 3). `dossier status`'s report stays evidence-only and
stamp-gated -- sub-defects 1(a) and 4 are closed at the review-agenda
surface only (decision 1's scoping), not by changing `Staleness` or
`status_lines`.

## Why this needs a plan rather than a roadmap row

Three things here are genuinely underdetermined, and an implementer
inventing an answer to any of them would produce a contract a later
reviewer can't tell from an accident:

- **Where the new agenda class reads its data from.** `Drift`
  (`chitragupta/dossier/_drift.py`) answers "has the *corpus* moved
  under this dossier?" -- a different question from "does the *draft
  text* still cite what the dossier records?", which is what
  `Staleness` (`_draft_fingerprint.py`) already answers, gated on a
  stamp. Reusing `DriftSource` would silently conflate the two; gating
  the new class on a stamp would inherit sub-defect 4 into the fix
  meant to close it.
- **Whether the new class is unattended.** The issue's own framing
  constraint (above) answers this, but it has to be written down once,
  in the one place (`_items.py`) rather than re-derived per caller.
- **How much a prune command touches.** Modelled too closely on
  `dossier sections --citekeys --write` (a full deterministic
  regeneration), a prune command would try to regenerate `evidence.md`
  from the draft -- which is impossible, since `evidence.md` holds
  hand-authored `relevance:`/`claim:`/`quote:` prose no stage can
  reconstruct. It has to be a surgical, targeted block delete instead,
  scoped to `evidence.md` alone.

## The decisions

### 1. A new, stamp-independent computation: `recorded_but_uncited`

Add `recorded_but_uncited(draft: Path) -> dict[str, list[str]]` to
`chitragupta/dossier/_draft_fingerprint.py` (180 code lines today, 70
lines of headroom under the 250-line C2 cap). It reads the draft's
currently-cited citekeys the same way `staleness()` already does
(`citation_gate.extract_citekeys(text, latex=...)`), unions the keys
`evidence_blocks(dossier)` and `citekeys_by_section(dossier)` (both
already imported here) record, and returns citekey -> sorted surfaces
(`"evidence"`, `"sections"`) among those two for every key not in the
cited set. Deliberately computed unconditionally -- no `Staleness`,
no `changed` gate, no stamp requirement -- which is what fixes
sub-defect 4 for the review layer: an agenda now reports this even on
a dossier that has never been stamped.

`dossier status`'s own fingerprint block (`status_lines`,
`_draft_fingerprint.py:182`) is **not** changed. It keeps reporting
`orphaned_evidence` only when `changed`, exactly as today, so
`TestDraftStaleness`/`TestStatusLines` in `tests/test_dossier.py` need
no changes. The review-agenda path (decision 2) is the surface that
gets the always-on report; `dossier status` stays the narrower,
stamp-gated one it already documents itself as.

### 2. A new agenda class, `recorded-but-uncited`, surfaced only

In `chitragupta/review/agenda/_items.py` (94 code lines today, 156
headroom -- `_items_findings.py` is at 246/250 and cannot take new
code):

- Insert `"recorded-but-uncited"` into `CLASSES` (`_items.py:15`)
  **directly after `"missing-citekey"`**, not at the end. `CLASSES` is
  the report's own ordering (`_render._summary_lines`,
  `_order.sort_key`), so position is visibility, not bookkeeping.
  Appending it after `"candidate"` would bury it beneath 7--155
  `candidate` items on a real draft (the range measured in
  `plans/f3-agenda-reviser.md`) -- reproducing, in a new form, exactly
  the invisibility this issue was filed about. It belongs beside
  `missing-citekey` because it is that class's mirror image: both are
  disagreements between the draft's citations and the dossier's record,
  one in each direction.
- Add `recorded_but_uncited_items(data: dict[str, list[str]]) ->
  list[Item]`, one `Item` per citekey, `unattended=False` (per the
  framing constraint), `section=None`, `line=None`,
  `id=item_id("drift", "recorded-but-uncited", None, citekey, citekey)`,
  a summary naming the citekey and its recorded surfaces, and
  `detail={"surfaces": surfaces}` -- the same shape
  `missing_citekey_items`/`candidate_items` already use.
- Wire it into `all_items()` as the new last line, reading
  `sources.recorded_but_uncited.data`.

In `chitragupta/review/agenda/_sources.py` (Sources' third input,
alongside `aids` and `style`/`drift`): add a
`RecordedButUncitedSource` dataclass (`available: bool = False`,
`data: dict[str, list[str]] = field(default_factory=dict)`), a
`_read_recorded_but_uncited(draft)` mirroring `_read_drift`'s own
"no dossier -> absent, never raise" shape (catches
`dossier.DossierError`, checks `directory.is_dir()`, then calls
`_draft_fingerprint.recorded_but_uncited(draft)`), a new `Sources`
field, and one more line in `collect()`.

`_order.severity_rank` needs no code change -- an unmatched class
already falls through to `return 0`, which is the right rank for a
class with no severity notion (like `missing-citekey`/`candidate`) --
but its docstring's enumeration of no-severity classes should name the
new one too, since that list is meant to be exhaustive.

`_render.py` **does** need a change, and it is the easy one to miss.
Its per-class rendering is generic -- `_summary_lines` iterates
`CLASSES` and the body uses `item.cls` as the heading text, so a new
class renders correctly with no table to update. But `_source_notes`
appends a hand-written note per *source*, including `style` and
`drift` individually, and `docs/AUTO-IMPROVEMENT.md`'s "Reads:"
contract is that every source is named in the header even when absent.
A new source with no note there means the header silently
under-reports what the run read. Add one note, mirroring `drift`'s
three-state shape: read / no dossier for this draft.

`Agenda.objective_class_count` (`__init__.py:65`) needs no change:
it sums `item.unattended`, and this class is never `True`.

`_dedup.merge` needs no change either, checked against its actual
rules rather than assumed: `_suppress_missing_citekey_duplicates` only
folds an `unsupported-claim` into a same-citekey `missing-citekey`, and
`_cross_link_shared_lines` only cross-links items sharing a `line`,
which every `recorded-but-uncited` item has as `None`. So a
`candidate` item and a `recorded-but-uncited` item for the same
citekey -- a real, if unusual, state -- survive as two distinct items,
which is correct: they report two different facts about the same key.

### 3. A new CLI primitive, `dossier prune`, `evidence.md`-only, dry-run by default

New module `chitragupta/dossier/_prune.py` (there is no room left in
`_sections.py`, at 243/250, or `_citekeys.py`'s writers -- there are
none -- so this is a new file, the same "one file per command" pattern
`_evidence_check.py`/`_draft_fingerprint.py` already follow):

```python
def prune_evidence(
    draft: Path, citekeys: "set[str] | None", apply: bool
) -> dict[str, str]:
    target = dossier_dir(draft)
    orphaned = recorded_but_uncited(draft)
    spans = evidence_block_spans(target)      # see below -- NOT evidence_blocks()
    duplicates = duplicate_evidence_keys(target)
    wanted = citekeys if citekeys is not None else set(orphaned)
    path = target / EVIDENCE_MD
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.is_file() else []
    report: dict[str, str] = {}
    doomed: list[tuple[int, int]] = []
    for key in sorted(wanted):
        prunable, message = _verdict(key, orphaned, spans, duplicates)
        report[key] = ("removed" if apply else "would remove") if prunable else message
        if prunable:
            doomed.append(spans[key])
    if apply and doomed:
        keep = [line for i, line in enumerate(lines) if not _within(i, doomed)]
        path.write_text("".join(keep), encoding="utf-8")
    return report
```

**Deletion is by line span, not by substring match.** This is the one
mechanism in the plan that changed after being probed, and the probe
is worth recording because the obvious implementation is silently
broken. `evidence_blocks()` returns a *reconstructed* block --
`"\n".join(body).rstrip() + "\n"` (`_citekeys.py:278`) -- so it is not
in general a substring of the file it came from. Measured over five
realistic `evidence.md` shapes:

| Shape | `block in text` |
| --- | --- |
| LF, block mid-file | holds |
| LF, blank-line run between blocks | holds |
| No trailing newline at EOF | **fails for the last block** |
| Trailing whitespace on the final line | **fails for the last block** |
| CRLF line endings | **fails for every block** |

A substring-matching prune therefore reports "no matching block found"
and does nothing -- on a *correct* input, and reading as "that key
isn't here" when it is. CRLF is not hypothetical: `.gitattributes`
normalises this repository's own sources, but `content/dossiers/` is
user data, hand-edited on whatever machine the user has.

So `_prune.py` deletes by line index instead, via a new
`evidence_block_spans(dossier) -> dict[str, tuple[int, int]]` in
`_citekeys.py`. `splitlines(keepends=True)` plus a join means whatever
line endings the file had survive the edit untouched, which a rebuild
from `"\n".join` would silently rewrite.

**Where that helper goes is a ratchet decision, so it is measured
here rather than left to the implementer.** `_citekeys.py` is at
214/250 code lines and its `_parse_evidence` at 21/25 statements --
the statement cap is the binding one. Both candidate shapes were
prototyped and counted with `scripts/code_standards.py`:

| Shape | `_parse_evidence` | File | Cost |
| --- | --- | --- | --- |
| (a) record spans inside `_parse_evidence`, return a third element | **24/25** | ~220/250 | one statement of headroom left |
| (b) a standalone span walker beside it | 21/25 (untouched) | 234/250 | two walkers over one file |

**Take (a).** `_citekeys.py`'s own comments assert that `evidence.md`
has exactly one parser, and a second walker applying the same
heading rule is the kind of duplication a reviewer here rejects -- correctly,
since the two would drift. It also turns out to cost no ripple:
`evidence_blocks` and `duplicate_evidence_keys` read
`_parse_evidence(dossier)[0]` and `[1]`, so appending a third element
is backward-compatible at both existing call sites.

The one-statement headroom is a real constraint on the
implementation, not a footnote: at 24/25, `_parse_evidence` may not
also gain a guard, a log line or an extra local. If the span
recording needs even one statement more than the prototype, switch to
(b) rather than splitting the module -- (b) is the escape hatch, and
it costs 14 lines of file headroom instead of a forced split.

**Residue rule, so "the exact remaining bytes" is a writable
assertion:** deleting a span removes the heading line through the last
line before the next `##`-prefixed heading -- which includes the blank
line that separated them. Nothing is re-normalised: no blank-line
collapsing, no trailing-newline fixup, no reflow. Removing the first
block leaves the file starting at what followed it; removing the last
leaves the file ending where the previous block ended. That rule is
what the test asserts against, byte for byte.

**`_verdict` returns `(prunable: bool, message: str)`, and control
flow reads the bool.** Never the message: branching on human-readable
output means rewording a string silently breaks the deletion path with
no test failing, which is precisely the "a guard is tested against the
exact shape it was blind to" hazard `DEVELOPER-AGENTS.md` names. The
message is presentation only, and `prunable` is the contract.

**Four distinct refusals, not one**, because a command whose whole
design rests on a human confirming it has to say *why* it declined:

| State | Verdict |
| --- | --- |
| still cited in the draft | `"still cited -- not an orphan"` |
| orphaned, but only in `sections.md` | `"recorded only in sections.md -- run dossier sections --citekeys --write"` |
| not recorded in this dossier at all | `"not recorded in this dossier"` |
| more than one `evidence.md` block | `"2 blocks for this key -- resolve the duplicate by hand first"` |
| a single orphaned `evidence.md` block | `"would remove"` / `"removed"` |

The duplicate case is a **refusal, not a partial prune**. Deleting one
of two blocks would leave the key still recorded and still uncited
while reporting success -- the orphan survives, and the next
`recorded_but_uncited` run still names it. `duplicate_evidence_keys()`
already computes exactly this, so refusing costs one lookup;
`evidence_blocks()`'s own first-block-wins keying is what makes the
naive version wrong.

**The dry run writes nothing, and that is structural.** `path.write_text`
is the only write in the module and it is guarded by `apply`; the
verdict strings differ only in tense. The mutation itself is computed
identically either way, deliberately -- that is what makes the dry run
a faithful preview rather than a second code path that can drift from
the real one. The fragility is that the guarantee now rests on there
being exactly one write site, so the test asserts the *file's bytes and
mtime are unchanged* after a dry run over a dossier with real orphans,
rather than merely asserting the printed output looks right.

`_cmd_prune(args)` resolves `Path(args.draft)`, builds
`citekeys = set(args.citekey) if args.citekey else None`, calls
`prune_evidence`, catches `DossierError` the same way `_cli.py:main`'s
own dispatcher does, and prints one line per requested key plus a
trailing `Dry run -- pass --apply to write.` when `apply` is false.

**Exit codes**, stated because a skill will branch on them: `0` when
every requested key was pruned or would be, **and** `0` when there was
nothing to prune at all (an empty worklist is a clean state, not a
failure); `1` when any requested `--citekey` was refused, so a script
naming a key that is still cited hears about it. A `DossierError`
keeps `_cli.py`'s existing `1`.

**Scope, explicitly:** this command only ever touches `evidence.md`.
It does not attempt to prune a `sections.md` row -- that surface
already has a working regeneration primitive
(`dossier sections --citekeys --write`, which derives the whole table
fresh from the draft and so drops a stale row for free), and the issue
itself measured 0 real occurrences of that half. It never reads or
writes `rejected.md` -- `recorded_but_uncited` never looks at it, so
there is nothing for `wanted`/`orphaned` to ever include from that
file, which is what keeps the "a rejected paper is not a prune
target" invariant (`_citekeys.py:77-85`) true by construction rather
than by a runtime check.

Wire `_add_prune_parser`/`_cmd_prune` into `_cli.py` (190/250, 60
headroom) the same way every other subcommand is: `draft` positional,
`--citekey` (`action="append"`, repeatable, default None meaning
"every orphan"), `--apply` (`action="store_true"`, default False).

### 4. Docs: add the new class, and reconcile the stale count language

Three places already enumerate the 9 (soon 10) agenda classes and one
already states a stale count for the *staleness* classes (a different,
adjacent enumeration this fix also touches by association):

- `docs/AUTO-IMPROVEMENT.md`'s item-class table (`AUTO-IMPROVEMENT.md:124-134`)
  gets a new row: `recorded-but-uncited | dossier fingerprint | the
  reverse of missing-citekey -- recorded but no longer cited | no --
  surfaced`, and its "Reads:" bullet list (`:99-106`) gains a line for
  the new source.
- `.claude/skills/agenda-reviser/SKILL.md`'s unattended-status table
  (lines ~71-78) gets one row, `recorded-but-uncited | surfaced only`.
- `.claude/skills/draft-reviser/SKILL.md`'s removal-offer passage
  (~lines 183-203) changes "remove the block, or note that the
  citation belongs back in the draft" to name `dossier prune` as the
  primitive to offer instead of a hand `Edit`, and says to log the run
  in `revisions.md` (the command does not -- see the test-driven order
  below) -- and its guardrails
  section's existing sentence about `agenda-reviser` never silencing an
  orphaned block by re-stamping stays, unchanged, since it is still
  true and still the right caution.
- `docs/DOSSIER.md` (~line 495-544) and `_draft_fingerprint.py`'s own
  module docstring (line 2, "four staleness classes") currently
  disagree with each other ("five" vs "four") about an unrelated,
  pre-existing count -- of the *`Staleness`* fields, not the new class.
  Reconcile that stray inconsistency in the same PR since both files
  are already being touched for the new class, rather than leaving it
  for someone else to trip over next.

## Files

- `chitragupta/dossier/_draft_fingerprint.py`: add `recorded_but_uncited()`.
- `chitragupta/dossier/_citekeys.py`: add `evidence_block_spans()`,
  recording in `_parse_evidence`'s existing pass the line spans it
  currently discards.
- `chitragupta/dossier/_prune.py` (new): `prune_evidence()`,
  `_verdict()`, `_within()`, `_cmd_prune()`.
- `chitragupta/dossier/_cli.py`: wire the `prune` subcommand.
- `chitragupta/review/agenda/_sources.py`: `RecordedButUncitedSource`,
  `_read_recorded_but_uncited()`, new `Sources` field, `collect()`.
- `chitragupta/review/agenda/_items.py`: `CLASSES` entry (after
  `missing-citekey`), `recorded_but_uncited_items()`, `all_items()`.
- `chitragupta/review/agenda/_render.py`: one `_source_notes` entry for
  the new source.
- `chitragupta/review/agenda/_order.py`: docstring only (no code change).
- `tests/test_dossier.py`: `recorded_but_uncited()` (unstamped dossier,
  evidence-only orphan, sections-only orphan, both, none);
  `evidence_block_spans()` against the five shapes in decision 3's
  table, **including CRLF and no-trailing-newline** -- those are the
  cases that broke the first design, so they are the ones a regression
  would reappear in; `prune_evidence()` and the `prune` CLI: dry run
  leaves the file's bytes *and* mtime unchanged, `--apply` removes the
  exact span and nothing else (asserted byte for byte, per the residue
  rule), each of the four refusal verdicts, a duplicate-block key is
  refused rather than half-pruned, `rejected.md` is never read or
  written, and the two branches a 100%-coverage run will otherwise
  miss: no `evidence.md` at all, and `--apply` with an empty worklist.
- `tests/test_review_agenda.py`: a new `TestRecordedButUncitedItems`
  class (mirroring `TestCandidateItems`), plus additions to
  `TestAllItems` and `TestSort` (class-order tiebreak). Confirmed by
  grep: no test in this file asserts `CLASSES`'s length or an exact
  class count, and `agenda-reviser/SKILL.md`'s frontmatter only names
  the *unattended* classes (`verbatim-run` short, `prose`,
  `missing-citekey`) rather than enumerating all nine -- so this is the
  full list of test-side touch points, not a hedge.
- `docs/AUTO-IMPROVEMENT.md`, `docs/DOSSIER.md`,
  `.claude/skills/agenda-reviser/SKILL.md`,
  `.claude/skills/draft-reviser/SKILL.md`.
- `docs/CLI.md`, in **three** places, found by grepping the class name
  rather than by guessing which docs discuss the agenda: the
  no-dossier sentence at `:1165` ("`missing-citekey` and `candidate`
  are simply absent from it") gains the new class, since it is
  dossier-derived and absent for the same reason; the surfaced-class
  enumeration at `:1171-1174` gains it too; and the `dossier`
  subcommand section (~`:1033-1056`) gains a `prune` entry beside
  `stamp`/`sections`/`check-evidence`.
- **Not** `docs/REVIEW.md`, `docs/GENRE.md` or
  `docs/AUTO-IMPROVEMENT-RATIONALE.md`, checked and ruled out: each
  names `missing-citekey` only while listing the *unattended* classes
  or discussing that one class's own rationale, and this class is
  surfaced, so none of the three has a list it belongs in.
- No test change is forced by the doc surface, also checked rather
  than assumed: nothing ties the agenda's `CLASSES` to a doc or a
  diagram, `test_features_doc.py` iterates `draft` *verbs* (of which
  `dossier` already is one) rather than `dossier` subcommands, and
  `test_command_depth_scan.py` is satisfied because
  `python -m chitragupta.draft dossier prune` is the same one-level
  entry-point shape `dossier stamp` already has.
- `pyproject.toml`: a minor bump -- a new command and a new agenda
  class are both additive features, not a patch. Read `origin/main`'s
  version at PR time rather than taking a number from this plan;
  `main` moves during a PR here, and two branches picking the same
  version merge with no conflict and lose the bump silently.

## Test-driven order

Per `DEVELOPER-AGENTS.md`'s standing rule, each piece lands as a failing
test first:

1. `recorded_but_uncited()` against a hand-built dossier fixture with
   an unstamped `scope.md` -- must report a citekey whose `evidence.md`
   block survives a hand-deleted citation, proving sub-defect 4 is
   closed for this path before anything reads it.
2. The new agenda class end-to-end: a draft + dossier fixture with one
   orphaned citekey produces exactly one `recorded-but-uncited` item,
   `unattended=False`, and `Agenda.objective_class_count` is unaffected.
3. `evidence_block_spans()` against a CRLF fixture first -- it is the
   case that falsified the substring design, so it is the one test that
   has to be red before the span helper exists. The other four shapes
   follow.
4. `prune_evidence()`: dry run changes nothing on disk (bytes and
   mtime); `--apply` removes only the targeted span, verified against
   the file's exact remaining bytes, not just "not in output"; each of
   the four refusal verdicts distinctly, the duplicate-block refusal
   included.
5. Docs/skill updates, checked by hand (no test detects prose drift
   here beyond `tests/test_technical_debt_scan.py`'s narrower scope,
   which this change does not touch).

**`revisions.md`: the command does not write it; the skill does.**
`_prune.py` is a primitive, and having it append to a revision log
would make a second module own a file `draft-reviser` already owns --
so a bare `dossier prune --apply` leaves no revision entry, exactly as
`dossier sections --citekeys --write` does not. What covers the audit
trail is the skill: `draft-reviser` logs every edit it makes, and a
prune it offered and ran is such an edit, so its passage (decision 4)
says to log it by name. The issue's sub-defect 2 complaint --
`revisions.md` being "the only trace" -- is answered by the command
being re-runnable and diffable at all, not by moving the log.

Run the full local check suite (`DEVELOPER-AGENTS.md`'s "Before
claiming a task complete") before opening the PR: `pytest --cov
--cov-report=term-missing` at 100%, all four linters at zero, the
OpenCodeReview `delegate-review` pass, and `check_version_bump.py`
before merge.

## How this splits into PRs

**Two PRs, in this order -- and each branched from `main`, never
stacked.** A PR based on another branch runs *zero* checks here
(`ci.yml` filters on `base=main`), so a stack would look green while
being untested.

| PR | Closes | Files | Depends on |
| --- | --- | --- | --- |
| 1. Detection + agenda class | sub-defects 1, 3, 4 | `_draft_fingerprint.py`, `_sources.py`, `_items.py`, `_render.py`, `_order.py`, `test_review_agenda.py`, `test_dossier.py`, `AUTO-IMPROVEMENT.md`, `CLI.md` (2 of 3 spots), `agenda-reviser/SKILL.md` | -- |
| 2. The `prune` primitive | sub-defect 2 | `_citekeys.py`, `_prune.py`, `_cli.py`, `test_dossier.py`, `DOSSIER.md`, `CLI.md` (the subcommand entry), `draft-reviser/SKILL.md` | PR 1's `recorded_but_uncited()` |

**One PR would also be defensible** and is within this repository's
demonstrated envelope -- #743 landed a comparable feature (new module,
new flag, app changes, docs) as 23 files and ~1,369 insertions, and
this whole plan is ~15 files. The split is recommended for two
specific reasons rather than on general "small PRs" grounds:

- **PR 1 is independently valuable and PR 2 is where the risk is.**
  Detection closes three of the four sub-defects and regresses
  nothing: the agenda starts reporting the state, and `draft-reviser`
  keeps offering the hand edit it offers today. Meanwhile every hard
  part of this change -- the 24/25 statement squeeze in
  `_parse_evidence`, the byte-exact residue assertions, the five
  line-ending shapes -- sits in PR 2. Bundling them lets the risky
  half hold the valuable half hostage.
- **The dependency runs one way only.** `prune_evidence` calls
  `recorded_but_uncited()`; nothing in PR 1 needs the command. So the
  sequence is forced, which also means PR 2 must re-read `main`'s
  version after PR 1 merges rather than picking a number up front.

What must **not** be split out of PR 1: the `_render.py` source note
and the `CLI.md` no-dossier sentence. Both describe the source PR 1
adds, and a release where the header omits a source it read is a
documentation defect shipped on purpose.
