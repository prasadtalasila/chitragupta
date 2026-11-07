# 1172: a review digest is a survey written in the sources' words

Status: **plan.** Written 2026-11-06 for issue #1172.

**Written for** whoever changes `review-digest` or `review digest`
next. **Assumed:** [docs/VERBATIM-DIGEST.md](../docs/VERBATIM-DIGEST.md)
as it stood after #991, and survey-writer's process.
**Not covered here:** the matcher's normalisations
(`plans/c3-quotation-integrity.md`).

## What went wrong

The first real digest, `simulation-techniques-and-simulators` (10,625
words), scored 0.879 copied and 0.121 unsupported and was unreadable:
248 runs of about forty words in thirty subsections, a running example
explained through asides about a different system, equations missing
from the runs that explained them, parse noise kept on purpose, and
connecting sentences that narrated the sources. Each defect traces to
the skill or the report, not to the drafter:

| Defect | Cause |
| --- | --- |
| A collage, not an argument | Goal 1 was "maximise copied text"; nothing asked for a framing, a comparison or a gap |
| `Supposeweareaskedtobuildavirtual`, `37 . 5 ◦ C`, `𝑇 ℎ`, `[2]` | Step 6: copy "character for character, including the parse's own noise" |
| "where 𝑇 ℎ is the temperature..." with no equation | Nothing said the sidecar's `formula` passages exist or must come along |
| "Fig. 5.13", "Eq. (5.1)", runs opening on "These" | Nothing reported them |
| One paper after another per paragraph | `_units.py` measured a digest at the document |

## Decisions (user, 2026-11-06)

1. **Goals reordered**: a self-sufficient survey; then as much body as
   possible in the sources' words; then surface and minimise
   unsupported text.
2. **The survey's shape and paragraph unit**: scope, framing, theme
   sections, comparison table, visible disagreement, gap analysis; each
   body paragraph braids runs from two or more papers.
3. **`[see @key]`** closes a sentence in the drafter's own words; it is
   checked for lexical support, never for copying.
4. **`<!-- own: why -->`** on the line above a paragraph declares it the
   drafter's; table rows are own by construction (cells are the
   drafter's phrases, support-checked against the row's citekey).
5. **Equations typeset in a math environment**: the house mapped form,
   `<!-- math -->` fence plus `math.md`, taken from the `formula`
   passage.

## Design

**Typography needs no code.** `_quotation_match.flatten` reduces both
sides to `[a-z0-9]` after NFKD and `strip_markers` drops `[n]` from the
source. Checked: run-together words, `37.5 °C`, `T_h` for `𝑇 ℎ`, a
restored hyphen and a dropped `[2]` all still match; a dropped word
fails, as it should; `\Delta` adds letters and fails, so a copied run
keeps the Greek letter itself. A bracketed editorial substitution
(`[The equation above] is an instance...`) matches at the `elided`
tier, which gives the drafter a clean way out of a cross-reference.

**Report.**

- `_digest_runs.Run` gains `own`, `follows` (the previous run's keys in
  the block, None at the block's start) and `after_math` (the block
  follows a `<!-- math -->` fence, `$$` or `\]`). `shown_figures` reads
  `Figure N of [@key]` from the digest's captions.
- `_digest_match` checks an own run with `score_claim` against all its
  sources' passages, page-level included: weak is `unsupported-text`,
  anything else is own text. An uncited sentence in an own block is own
  text. The four shares partition the digest: copied, own, flagged,
  not checkable.
- New `_digest_dangling.py`, class `dangling-reference`, listed and
  counted but in no fraction: cross-reference to a numbered item not
  shown, leftover `[n]` marker, copied run opening on an anaphor with
  nothing before it from the same source (exempt directly after a
  displayed equation). Measured on the sample digest: 43
  cross-references, 43 markers, 4 openers, all genuine. The opener test
  reads only copied runs and only their first word, which is why it is
  low-recall: most of the sample's dangling openers sat behind a bridge
  sentence in the same run.
- `_digest_model.py` takes the records out of `_digest_match.py`
  (C2, 250 lines), re-exported where callers found them.
- `_units.UNITS["digest"]` becomes `paragraph`.

**Found on the way.** `_claims.claim_blocks` dropped a whole paragraph
whose first line was `<!-- single-source: why -->` written directly
above it, so `uncited`, `support` and `digest` never saw it. Only the
two declaration markers are peeled now; a `<!-- figure: -->` marker
above its caption still takes the caption out, as #411 intends.

**Skill.** Survey skeleton in step 6; copying, equations, figures and
dangling rules moved to `.claude/skills-common/references/digest-copying.md`
so `SKILL.md` shrinks (17,902 to about 16,700 bytes; cap 19,000 to
17,000). Step 10 becomes a read as someone who has opened none of the
papers; `review synthesis` joins step 14.

## Not done

- No re-run of the sample digest in this PR: it is per-host data in the
  user's drafts project and waits for the shipped skill.
- `$$` display math is still read as prose by every aid; the skill uses
  the fenced form, which is blanked.
