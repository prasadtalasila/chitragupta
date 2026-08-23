# A2: split `support:` into `claim:` and `quote:`

Status: **plan, unbuilt.** Written 2026-08-20. Implements
[docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s A2, which is the
spine of that document's Theme A.

**Written for** whoever builds it. **Assumed:**
[docs/DRAFT-ITERATION.md](../docs/DRAFT-ITERATION.md) for the dossier,
and the roadmap's diagnosis section for why this exists at all.
**Not covered here:** why claim-first drafting reduces verbatim reuse --
that argument is the roadmap's, and this plan does not restate it.

## The problem in one line

`evidence.md`'s `support:` line holds, in practice, a 600-character raw
window of the source; the drafter then writes prose with that window in
context.

## The contract

One `## \`citekey\`` block gains two fields in place of `support:`:

```markdown
## `talasila_realising_2024`

relevance: why this source bears on the sub-theme
claim: what the source establishes, in the drafter's own words
quote: > an optional verbatim span, marked quotable-only
```

- **`claim:`** is **the only field a drafting step may write prose
  from.** Required. Written by whoever judged the evidence, at the
  moment they judged it -- which is before any sentence of the draft
  exists, and that ordering is the whole mechanism.
- **`quote:`** is optional, verbatim, and usable in a draft **only**
  inside quotation marks with an attribution. Absent by default: a
  quote is a deliberate act, not the residue of retrieval.
- **`relevance:`** is unchanged.

`support:` is **read but never written** after this lands -- see
migration.

## Decisions this plan settles

**Why not keep `support:` and add `claim:`?** Because the failure is
that the drafter reads source wording; leaving a field that holds source
wording, next to a field that does not, preserves it. One field for
"what it says", one for "its exact words", and a rule about which may be
drafted from.

**Why is `quote:` optional rather than always captured?** A captured
quote is a quote in the drafter's context, which is the thing being
removed. Capture one when a quotation is actually intended.

**Migration.** Existing dossiers keep `support:` and are **not**
rewritten. `evidence_blocks()` already returns a block verbatim and does
not own its shape, so old and new coexist by construction. A reviser
meeting a `support:`-only block treats it as `quote:` -- the
conservative reading, since that is what it usually is. Do not write a
migration script: dossiers are per-draft, gitignored, and rewriting a
record of a human judgement to fit a new schema is exactly the kind of
silent rewrite this project refuses elsewhere.

**The self-check, and what it may not become.** At dossier-write time,
compare `claim:` against its own `quote:` with
`chitragupta/overlap_skipgram.py` and warn when the claim is the quote
with words moved. **Advisory, printed, never blocking**, and -- per the
roadmap's R3 constraint -- the similarity number is *reported, never
optimised*. It must not become an acceptance criterion for an
unattended edit. If that is wanted later, it needs a binary form and a
separate argument.

## Files

| File | Change |
| --- | --- |
| `.claude/skills/survey-writer/SKILL.md` | step 2: `support:` becomes `claim:`/`quote:` |
| `.claude/skills/tutorial-writer/SKILL.md` | same |
| `.claude/skills/thesis-chapter-writer/SKILL.md` | name the fields where it writes `evidence.md` |
| `.claude/skills/textbook-chapter-writer/SKILL.md` | same, noting its `evidence.md` is often empty |
| `.claude/skills/deep-research/SKILL.md` | **already records claims** -- align wording, add `quote:` |
| `.claude/skills/{draft,corpus}-reviser/SKILL.md` | read both shapes; never rewrite an old block |
| `chitragupta/dossier/_citekeys.py` | the self-check helper; `evidence_blocks()` itself is unchanged |
| `docs/DRAFT-ITERATION.md` | the field contract, and it owns it |
| `docs/TOKENS.md` | its measurement method names the 600-character window; note what changed |

## Tests

Failing first, per the TDD rule:

1. A block with `claim:` and `quote:` round-trips through
   `evidence_blocks()` unchanged.
2. A legacy `support:`-only block still round-trips -- the
   coexistence guarantee.
3. The self-check fires on a `claim:` that is its `quote:` reworded, and
   stays silent on a genuine restatement.
4. The self-check returns a warning, never a non-zero exit.

## Done when

`deep-research`'s existing claim-shaped practice is what every genre
does; a fresh run of `survey-writer` produces an `evidence.md` with no
raw retrieval window in it; and the roadmap's baseline table is re-run
and reported.
