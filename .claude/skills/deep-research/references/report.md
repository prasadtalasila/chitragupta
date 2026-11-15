# deep-research -- Reference (exact protocol, adapted)

The orchestrating run's reference for the deep-research skill's phases.
What a dispatched agent does (an interviewer, a section writer, a
reviewer) is in that agent's own file under `.claude/agents/`, which a
run without subagents reads and follows itself. Paths here are from the
project root. Adapted from
[hadufer/claude-storm](https://github.com/hadufer/claude-storm) (MIT
License), which itself encodes the Stanford STORM algorithm
(`github.com/stanford-oval/storm`, NAACL 2024 / arXiv:2402.14207) fused with
Nav Toor's 4-prompt adaptation. The adaptation for this project: **closed,
citekey-grounded corpus instead of the live web** -- see the opening of
SKILL.md, under `# deep-research`, for what every claim must resolve to.

---

## 1. Defaults (mirrored from claude-storm/STORM)

| Parameter | Value | Note |
| --- | --- | --- |
| Generated perspectives | 5 + Basic fact writer | adapt names to the topic; drop one if it genuinely doesn't fit an academic corpus |
| Interview rounds / persona | 2 / **3** / 4 (quick/standard/deep) | |
| Search queries / question | up to 3 | reformulations, not parallel identical calls |
| Candidates retrieved / query | 15 (`retrieval search`) | 500-char snippets -- enough to judge, not just a title |
| Results kept / query | ~top 3 after relevance filtering | filter like the survey writer's step 2, not raw top-k |
| Concurrency cap | ~8-10 subagents in flight at once | batch the rest sequentially |
| Lead/summary length | <=4 paragraphs | |

Module order: **Perspective discovery -> Multi-perspective interviews ->
Contradiction map -> Outline -> Cited writing -> Polish/synthesis -> Peer
review**. STORM's own paper reports multi-perspective articles ~25% more
organized and ~10% broader in coverage than single-prompt baselines --
that's the gain the perspective fan-out buys, and why this skill exists
alongside the faster single-pass survey writer.

---

## 2. The personas (Phase 1)

Read this when the dossier has no `outline.md`, or one that fails its
check: an outline's own section headings name the angles instead.

Always include the generalist, the **Basic fact writer**. STORM's own
persona discovery works by surveying related reference material and
inventing personas that match recurring structure in it --
operationalized here as: run 1-2 broad retrieval calls on the topic
itself (not the sub-questions yet) and skim what actually comes back --
titles, sub-fields, recurring angles -- before finalizing the persona
list. For `standard`/`deep` depth, derive 1-2 **corpus-specific**
personas from what is actually there (skip this for `quick`). Then map
the remaining slots onto these five lenses, **adapted and renamed to fit
the topic** (drop one that genuinely doesn't apply):

1. **The Practitioner** -- what does applying this in practice surface that
   the papers gloss over?
2. **The Academic** -- what does the retrieved literature actually claim,
   and where do sources in this corpus disagree with each other?
3. **The Skeptic** -- the strongest limitation the corpus itself admits to
   (or a gap it fails to address).
4. **The Adoption/Incentives analyst** -- who would use this and why; what
   incentives shape the work (adapt or drop if inapplicable).
5. **The Historian** -- what earlier approaches does this build on or react
   against.

---

## 3. Why this skill does not scope to a collection

Read this when a user asks for a collection-scoped report, or wonders
why this genre alone offers no scoping.

Every other genre offers to scope retrieval to one curated Zotero
collection and threads `--collection` through its searches. This one
does not, and neither do its agents. That is a decision, not an
oversight.

The reason is what this skill is for. Its whole method is to attack a
question from several perspectives at once, each interviewer chasing a
different framing, and then to map where those framings *disagree*. A
curated shelf is one person's answer to "what is this topic about",
already filtered by the judgement being interrogated. Scoping to it
would narrow every perspective to the same pre-agreed subset and quietly
delete the contradictions this skill exists to surface -- the report would
look consistent because it had been prevented from seeing anything that
would make it otherwise.

There is measured reason to expect that, not just principle. A 19-item
shelf surfaced ten papers a whole-corpus search never returned, and the
whole-corpus search surfaced far more that the shelf did not hold
(`bench/RESULTS.md`, 2026-08-19): the two are different rankings, not
subsets. For a single-thesis genre, picking one is a reasonable trade.
For a genre whose output is a contradiction map, taking the narrower one
by default is the wrong half.

---

## 4. Why no citation-globalization algorithm is needed here

claude-storm's `reference.md` §4 de-duplicates and globally renumbers
citations because raw web URLs from independent parallel searches need it
(different subagents might fetch the same URL, or none at all, with no
shared numbering). This project doesn't have that problem: a citekey is
already a single, stable, project-wide identifier -- the same paper always
has the same citekey from every subagent's `search()` call, straight from
`content/ledger.sqlite`. Just use citekeys directly everywhere (interview
packets, contradiction map, synthesis, peer review, final references) and
skip local-to-global renumbering entirely.

---

## 5. Final report template (Phase 7b)

```markdown
# <Topic> -- Deep Research Report

> Multi-perspective, corpus-grounded research. Method adapted from
> hadufer/claude-storm (MIT) / Stanford OVAL STORM (Shao et al., NAACL 2024).
> Depth: <quick|standard|deep> - Perspectives: <n> - Citekeys: <N> - Date: <date>

## Summary
<=4 cited paragraphs -- the standalone lead.>

## Synthesis Briefing
**Executive summary:** <one paragraph.>

**Key findings (ranked by reliability):**
1. **<finding>** -- Reliability <x>/10. Supported by <perspectives>;
   challenged by <perspectives>. [@citekey]
2. ...

**Hidden connection:** <...>

**Actionable insight (for <role>):** <...>

**Frontier question:** <...>

## <Article body -- outline sections with inline [@citekey] citations>
### ...

## Contradiction Map
- **Conflicts:** <perspective A claims ... [@key] vs perspective B claims ... [@key]>
- **Strongest / weakest evidence:** <...>
- **Resolving question:** <...>
- **Universal agreement:** <...>
- **Blind spot:** <...>

## Peer Review & Reliability Scorecard
<For `standard`/`deep`: the reconciled result of the 4-role panel in §7,
not any single reviewer's raw output.>

| Finding | Confidence (1-10) | Why |
|---|---|---|
| ... | ... | ... |

- **Panel verdicts:** domain-accuracy: <verdict> - methodology-rigor:
  <verdict> - clarity-completeness: <verdict> - devils-advocate: <verdict>
- **Concerns addressed** (met the concession threshold): <what changed and why>
- **Concerns logged, not addressed** (below threshold): <what, and why left as-is>
- **Weakest link:** <claim + what would verify it>
- **Bias check:** <which perspective's sources dominated>
- **Missing perspective:** <6th angle>
- **Overall grade:** <grade> -- <what to fix>

<For `quick`: the single inline self-critique §7 ends on instead --
confidence scores, weakest link, bias check, missing perspective, overall
grade, no panel verdicts row.>

## References
<Leave this heading bare -- `python -m chitragupta.draft references` (SKILL.md Phase 7d)
fills it in automatically from exactly the citekeys cited above, as
numbered IEEE entries ("[1] J. Doe and R. Roe, "A Paper," *IEEE Trans.
Testing*, vol. 3, pp. 1-9, 2024. `doe_paper_2024`"), pulled from
content/ledger.sqlite. Don't hand-assemble this list, and don't
hand-number the inline `[@citekey]` markers above to match it -- pandoc
assigns those numbers when the draft is rendered.>
```

Save as `content/drafts/deep-research-<kebab-topic>.md` (canonical format),
then render `.tex`/`.pdf` from it — see SKILL.md Phase 7(d) for the exact
commands and the warn-and-continue behavior on a rendering failure.

**A deep-research report emits the evidence sidecar, and has the
strongest claim to it of the five genres:** showing its work *is* the
product here. A report that reconciles several perspectives and names
where the corpus disagrees with itself is read by someone who wants to
check a contradiction against what each source actually said, and the
sidecar is where they do that.

---

## 6. Honesty rules

- Grounded by default; a claim with no surviving evidence doesn't get made.
- Surface real disagreement among corpus sources rather than smoothing it over.
- The peer-review section must be genuinely critical -- it's the fix for
  STORM's documented lack of self-critique, and it's the same reason this
  project's `citation_gate.py` exists: a soft "please cite your sources"
  instruction is not the same guarantee as an explicit, adversarial check.

---

## 7. Peer-review panel protocol (Phase 7a, `standard`/`deep` depth)

**Idea credited to
[Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills)'s
Stage-3 peer review** (an Editor-in-Chief plus several independent
reviewers and a Devil's Advocate). **Nothing below is that project's text**
-- it's CC-BY-NC 4.0, and what follows is this project's own design,
written from scratch, borrowing only the idea of an independent multi-
reviewer panel with a dedicated adversarial role. See the README's
Acknowledgements section.

**Why a panel instead of one self-critique pass:** one voice reviewing its
own draft shares its own blind spots -- the exact failure mode STORM's
single self-critique step doesn't fix, just narrows. Four independent
reviewers, each with a different, narrow mandate, and none seeing the
others' notes before writing their own, surface more than a single pass
asked to "review this critically."

**The four roles** -- `domain-accuracy`, `methodology-rigor`,
`clarity-completeness` and `devils-advocate` -- are dispatched as
parallel `peer-reviewer` subagents. What each role checks, and the
packet each returns, is in `.claude/agents/peer-reviewer.md`.

**The concession threshold** (this project's own rule -- academic-research-skills'
actual "concession-threshold protocol" internals weren't reused, since this
project doesn't have visibility into them and wrote this independently):

- Any **high**-severity concern from *any* single reviewer must be
  addressed -- revise the claim, or state the concern openly in the
  scorecard as unresolved. Never silently dropped.
- Any concern (medium or high) raised **independently by 2+ reviewers**
  must also be addressed -- agreement across differently-focused reviewers
  who didn't see each other's notes is a stronger signal than any one
  reviewer's opinion.
- **low**-severity or single-reviewer **medium** concerns are logged in the
  scorecard but don't block presenting the draft.

**Reconciliation:** the orchestrating skill (this file's SKILL.md) acts as
the reconciling editor itself -- no separate "EIC" subagent. It reads all
four verdicts (`ready`/`needs revision`/`reject`), applies the threshold
above, revises what the threshold requires, and writes the final
Peer-Review & Reliability Scorecard section from the reconciled result, not
from any single reviewer's raw output.

**At `quick` depth there is no panel.** Critique the draft inline,
once, with no subagent: a confidence score (1-10) per key finding, with
its justification; the weakest link, and what would verify it; a bias
check (did one perspective's sources dominate?); a missing sixth
perspective; and an overall grade. That is the scorecard §5's template
describes for `quick`, with no panel-verdicts row.

---

## 8. Why the closing checks matter more here

Read this when the user asks why the prose check or the verbatim scan
runs on this report, or what either is for in this genre.

**The prose check** is the first time anything reads the whole report
at once: a dozen subagents wrote sections independently, so a defect
marker in one and en-US spelling in another are exactly what no writer
was placed to notice.

**The verbatim scan** is earned more here than in most genres for the
same reason: no single context ever saw the whole report, and the
synthesis prose stitching the sections together cites nothing at all.

---

## 9. What bears on this genre from the writing standards' sources

Read this when asked where this genre's writing rules come from.

The prose standards this skill inherits are not original to this
project. Full citations, licences and a per-principle attribution table
are in `docs/WRITING-STANDARDS.md`'s "Sources and attribution"; all three
works are openly licensed (CC-BY or CC-BY-SA) and require credit. What
bears on *this* genre specifically:

- **Google, *Technical Writing Courses* (CC-BY 4.0)** -- using the same term
  for the same concept throughout is the direct ancestor of the Phase 4
  glossary. In a single-author document that rule is a style preference; in
  a pipeline dispatching parallel section writers it is the difference
  between one report and four stitched together, which is why it is
  enforced structurally at outline time rather than left to Phase 6 polish.
- **Last, *Technical Writing Essentials* (CC-BY 4.0)** -- the introduction
  checklist -- scope ("what will and will not be covered") plus the reader's
  assumed background -- behind Phase 6's scope statement.
- **Procida, *Diátaxis* (CC-BY-SA 4.0)** -- the genre-separation principle.
  A multi-perspective research report is not a Diátaxis quadrant, and none
  of the tutorial/how-to structural rules apply; what transfers is the
  requirement that the report know which single job it is doing.
