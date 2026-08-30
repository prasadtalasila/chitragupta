# 📖 C3: quotation integrity -- verify each quoted span is really in the source

Status: **shipped**, by
[PR #416](https://github.com/prasadtalasila/chitragupta/pull/416),
merged 2026-08-26. Written 2026-08-25 for
[#383](https://github.com/prasadtalasila/chitragupta/issues/383). What
changed from this plan on the way is recorded below rather than edited
out.

**Written for** the person building C3 --
[docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s "Theme C:
verify faithful use", item C3, and build-order item 6. It closes the
third bullet of [docs/REQUIREMENTS.md](../docs/REQUIREMENTS.md) §1.2,
*"quoted spans must appear verbatim in the source at the cited
location"*.

**Assumed built, because both are:** A2's `claim:`/`quote:` contract
(#306, [plans/a2-claim-quote-split.md](a2-claim-quote-split.md),
specified in [docs/DOSSIER.md](../docs/DOSSIER.md)), and A4's evidence
sidecar (#313, [plans/a4-evidence-appendix.md](a4-evidence-appendix.md),
`chitragupta/evidence_appendix.py`).

**Not covered here:** claim support (C2, continuous, a different
question), the `agenda` itself
([docs/AUTO-IMPROVEMENT.md](../docs/AUTO-IMPROVEMENT.md), unbuilt -- this
plan only registers a class in its table), and finding the source a
misattributed quote *actually* came from (see "Deliberately out of
scope").

## 🔧 What changed on the way

Built in **#416** (6.27.0), against this plan. Three things landed
differently, corrected here rather than left to disagree with the code:

- **NFKD, not NFKC.** Both expand a ligature, but NFKC leaves a
  precomposed `é` precomposed and the `[a-z0-9]` filter then *deletes*
  it: `café` flattens to `caf`, `Müller` to `mller`. NFKD decomposes
  first, the combining mark is dropped as non-alphanumeric, and the base
  letter survives. Deleting a letter is a corruption the two sides only
  sometimes share, and it would false-absent any quotation carrying a
  European name. The tables below say NFKD.
- **The sliver threshold is 8, not 12.** The measurement's flat region
  (6 to 15) gave no reason to prefer the middle, and a test then showed
  one: `"operators [who] can start developing"` leaves a 9-character
  first fragment, which 12 discards, leaving a single fragment, which is
  not an elision at all -- so a correct quotation reports absent. Given
  a flat response, take its low end. The corpus could not see this
  because it happened to contain no such span.
- **The two-PR split below is wrong, and the whole sweep shipped in one
  PR.** It is not optional prose hygiene:
  `tests/test_architecture_review_layer.py`, `test_features_doc.py`,
  `test_packaging_command_table.py` and `test_diagrams_in_sync.py`
  machine-check that every aid in `review.AIDS` reaches REVIEW.md,
  FEATURES.md, PACKAGING.md and all four Mermaid diagrams *including
  their rendered SVGs*. Registering the aid without the sweep leaves the
  suite red, so there was never a first PR to review on its own. This
  repository enforces R10 considerably better than either #383 or this
  plan knew.

One thing the build added that this plan did not specify: **every exact
tier is tried before any elided one**, rather than exact-then-elided
within each window size. Exact is the stronger claim and should not lose
to a wider window. The ladder section below already described that
order; the first implementation did not have it, and an OpenCodeReview
pass over the branch caught the mismatch.

## 🎯 The question, and the one this does not ask

A `quote:` is verbatim by contract. It reaches a rendered sidecar in
quotation marks, under an attribution. Nothing checks that the span is
in the source it is attributed to.

A quotation attributed to a paper that does not contain it is the same
failure class as a fabricated citekey -- a plausible artefact with
nothing real behind it -- and it is the one part of that class
`chitragupta/citation_gate.py` cannot see, because the citekey is real.

**There is no cited page, and this plan does not add one.** The roadmap
entry reads *"verify each quoted span appears verbatim in the cited
source at the cited page"*. The shipped contract gives a block three
fields -- `relevance:`, `claim:`, `quote:` -- and no page, and
`evidence_appendix.py` reads `quote:` and only `quote:`. So there is
nothing to verify a page against.

Of the two answers #383 sets out, this plan takes **(a) locate and
report**: find the span in the source's own passages, and report the
page it was found on. Rejected: **(b) add a `page:` field**. It is more
precise, and it changes a contract that shipped four weeks ago to ask a
human to record something (a) derives. The finding that matters is
*"this span appears nowhere in the source it is attributed to"*, and (a)
produces it. A wrong page number is a bookkeeping error; this is not.

## 🏷 Name

`quotation`. The key in both `review.AIDS` (title **"Quotation
integrity"**) and `review/__main__.AIDS`, so the report files as
`content/review/<topic>/<stem>.quotation.md` and the command is
`python -m chitragupta.review quotation <draft>`.

It matches the register of the six keys already there -- `provenance`,
`verbatim`, `coverage`, `synthesis`, `figure`, `uncited` -- and the
wording of both the roadmap entry ("quotation and page integrity") and
§1.2 ("Quotation integrity"). The judgement register belongs to the
gate: `audit`, `verdict`, `reckoning` and `ruling` are barred by R10's
naming rule, and `triage` separately by
[docs/REJECTION.md](../docs/REJECTION.md).

`quotes` was the other candidate and reads slightly better as a
subcommand; `quotation` was preferred because `<stem>.quotation.md`
names the property being checked rather than the objects counted, which
is what every other suffix in that directory does.

## 📥 What is checked: exactly what the sidecar publishes

The universe is `evidence_appendix.quoted_spans(draft_text, dossier)`
-- reused, not reimplemented. That one call already inherits three
decisions this aid would otherwise have to restate and could drift on:

1. **Only citekeys the draft actually cites**, via
   `references.used_citekeys()`. A dossier block for a source the draft
   dropped is not a finding about the draft.
2. **`quote:` and only `quote:`.** A legacy `support:`-only block holds
   a raw 600-character retrieval window (`retrieval.EVIDENCE_CHARS`),
   which nobody ever chose as a quotation.
   [docs/DOSSIER.md](../docs/DOSSIER.md)'s table is explicit that a
   module which *prints* such a block reads it as nothing at all, and
   the reasoning carries here unchanged: checking one as though someone
   had chosen it manufactures a finding about a decision nobody made.
3. **One quote per block.** `_evidence_check.fields()` is first-wins,
   and that is the contract, not an oversight: DOSSIER.md says a block
   carries *"three possible fields"*, singular. Record this in the
   module docstring so the next reader does not "fix" it into a silent
   behaviour change.

So the aid's claim is exact and worth stating in the report's own prose:
**it checks precisely the spans the sidecar would publish.** A quote it
passes is one a reader will meet in a PDF.

**A pre-A2 dossier therefore checks nothing and exits 0** -- no
`quote:` anywhere, empty universe, no findings. Same shape as the
sidecar declining to render, and correct for the same reason.

**Today that is every dossier this project has**, and the plan says so
rather than letting it be discovered after the build. All 22 live
`evidence.md` files and all 15 in `content/backup/chitragupta-6.20.7/`
carry zero `quote:` fields -- zero `claim:`, `relevance:` or `support:`
either. So on merge, `review quotation` reports "nothing to check" on
every real draft in the repository.

That is not an argument against building it, and it is worth being
precise about why. A2 shipped the contract four weeks ago; `quote:` is
optional and absent by default, because a captured quote is a quote in
the drafter's context and the contract exists to remove those. Nothing
has yet chosen to capture one. The aid is the thing that makes the first
one safe to publish, so building it before the first `quote:` exists is
the right order, not a premature one. What it does mean is that the
found and absent paths are exercised only by tests -- see the fixture
rule below, which is why this plan measured the matcher against real
source text before proposing it.

### The rejected import direction

`evidence_appendix.py` itself reads `evidence_blocks`/`fields` out of
`chitragupta.dossier` directly. This aid could do the same and avoid a
review-layer-to-drafting-layer import.

Rejected. That import costs nothing this aid does not already pay --
it needs `ledger` for `passages.source_passages(con, ...)` and
`dossier` for the dossier path regardless -- and it would create a
second home for the `support:`-is-not-a-quote rule. Two modules
deciding separately what counts as a published quote is exactly how the
aid comes to check a set the sidecar does not print, at which point
"this checks what gets published" stops being true without anything
failing.

## 📊 The measurement this plan rests on

Every claim in the next two sections is measured, not asserted. The
method, so it can be reproduced or disputed:

**No dossier anywhere uses the A2 contract.** Across all 22 live
`evidence.md` files and all 15 in `content/backup/chitragupta-6.20.7/`,
there are **zero** `relevance:`/`claim:`/`quote:`/`support:` field lines.
Every real dossier is hand-written prose -- `## Sec. 3.5 -- the four
published decompositions`, then bullets naming citekeys with quotations
inline in double quotation marks. So there was no real `quote:` to test
against, and one had to be built.

**The corpus of spans.** 189 quoted spans were extracted from the 14
backup `evidence.md` files that carry any, each attributed to the
citekey named nearest before it in its own bullet -- 87 distinct
citekeys. These are real human quotations from real papers, which is the
property that matters; the *attribution* is a heuristic, so the absent
rate below is an upper bound and not C3's expected false-positive rate.

**The sources.** All 189 resolved to rung 1 or 2 --
`content/docling/` holds 498 passage sidecars, `content/parsed/` 497,
against 501 papers. `unverifiable` fired **0 times**. It is the right
safety valve and it is not the common case; do not let a reader infer
otherwise from how much space it gets below.

| Tier | Spans confirmed | Share |
| --- | --- | --- |
| Exact, one passage | 124 | 65.6% |
| Exact, adjacent pair | 0 | 0.0% |
| Elision-aware, one passage | 31 | 16.4% |
| Elision-aware, adjacent pair | 1 | 0.5% |
| **Confirmed in the cited source** | **156** | **82.5%** |
| `absent` | 33 | 17.5% |

**Reproducing it**, because a plan whose central table cannot be
rebuilt is the same failure as one that no longer matches what shipped.
The measurement was made with a throwaway script; rebuild it in three
steps rather than trusting the numbers:

1. **Extract.** For each `evidence.md` under
   `content/backup/chitragupta-6.20.7/content/dossiers/`, join hard
   wraps within each bullet or paragraph, find citekeys as
   `` `([a-z][a-z0-9_.-]*_[a-z0-9-]+_\d{4}[a-z0-9-]*)` ``, find spans as
   `["“]([^"“”]{20,600})["”]`, and attribute each span to the citekey
   matching nearest before it in the same block. Yields 189 spans over
   87 citekeys from 14 files.
2. **Load sources.** `content/docling/<citekey>.passages.json`, else
   `content/parsed/<citekey>.passages.json`, else `<citekey>.txt` split
   on form feeds -- `passages.source_passages`'s own ladder.
3. **Run the ladder** below, with `REFMARK = re.compile(r"\[[\d\s,;–—-]+\]")`
   applied to each passage before `flatten`, and
   `ELISION = re.compile(r"\s*(?:\[[^\]]*\]|\.\.\.|…)\s*")` splitting each
   quote.

The extraction rule is the only judgement in it, and it is deliberately
crude: it over-collects scare-quoted phrases, which is why the residual
breakdown below separates them out rather than counting them as
findings.

And the residual 33, since a number that size is the one a reader will
want broken down: 11 are under eight words -- scare-quoted phrases of
the book's own (`"explain it to a sponsor"`), which a `quote:` field
would never hold; 8 carry an elision too fragmented to align; 14 are
eight words or more and unelided, which is the class C3 exists for.

## 🔤 The matcher: one normalised character stream, four tiers

Both sides are flattened to a pure `[a-z0-9]` character stream:

```python
def flatten(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", text).lower())
```

Then `haystack.find(needle)`. Every caveat #383 names is handled by
construction rather than by a list of special cases:

| Caveat | Why it vanishes |
| --- | --- |
| Hyphenation at a line break (`environ-\nment`) | The hyphen and newline are not `[a-z0-9]` |
| Soft hyphen `U+00AD` | Same |
| Ligatures (`ﬁ`, `ﬄ`) | NFKD expands them to `fi`/`ffl` before the filter |
| An accented letter (`café`, `Müller`) | NFKD decomposes it, the combining mark is dropped, the base letter survives |
| Collapsed or doubled whitespace | Not `[a-z0-9]` |
| Quotation-mark variants (`"` vs `“`, `'` vs `’`) | Not `[a-z0-9]` |
| A quote value written with its own surrounding quotes | Same, so the `_blockquote` de-quoting dance is unnecessary here |

Deliberately **not** the existing `norm()`/`_norm()`
(`[a-z0-9]+` findall, in `verbatim_check/_corpus.py` and
`overlap_index.py`). Those produce a *word list*, and a word list splits
`environ-\nment` into `["environ", "ment"]` where the quote has
`["environment"]` -- the exact false "not found" #383 warns about. Run
over the 189 spans, the word list finds **115 of the 124** the character
stream does on the exact tier: **9 false `absent` findings more than the
character stream**, 7.3% of that tier's true positives. Additive with
the two effects below, not a total -- the word list loses those nine
*and* everything the reference-marker and elision tiers recover.

No dehyphenation heuristic is needed if word boundaries are never
formed; attempting one would have to distinguish a line-break hyphen
from `state-of-the-art`, which is a judgement call this check should not
be making.

### Two normalisations #383 does not name, and they matter more

The issue lists hyphenation, ligatures, whitespace and quotation marks.
Measured, those are the *small* effect. Two others dominate, and a
matcher without them reports 70 findings where the correct answer is 33.

**Inline reference markers, stripped from the source.** Academic PDFs
carry `[30]` mid-sentence, and a human quoting the sentence correctly
drops it. Flattened, the marker becomes a bare `30` wedged inside the
span. `frasheri_advanced_2024` is the clean case: the dossier quotes
*"...in different circumstances and hypotheses."* and the passage reads
*"...in different circumstances and hypotheses [30]. Should unwanted
behaviours..."* -- one inserted digit pair, and an otherwise perfect
verbatim quotation reads as fabricated. So the source side has
`re.sub(r"\[[\d\s,;–—-]+\]", " ", text)` applied before `flatten`.
Purely numeric bracketed groups only: stripping `(Smith 2020)` would
need author-year parsing and could eat quoted content. **+5 spans.**

**Elisions and editorial insertions, on the quote side.** A quotation is
routinely elided (`"PE refers to the physical entity ... VE represents
the virtual entity"`) or edited (`"with low budget [who] can start
developing"`). Neither is contiguous in the source, and neither is a
defect. So a quote is split on `...`, `…` and any `[...]` group, and the
fragments must appear **in order** within one passage. That is still
binary and still deterministic: ordered subsequence matching, not fuzzy
matching, and no similarity score anywhere in it. **+32 spans, 47% of
what the exact tier alone called absent.**

It does carry one number -- fragments under 12 flattened characters are
dropped as slivers -- and that is the only value in the matcher not
forced by something else, so its provenance is on the record rather than
left for a reviewer to ask about.

**It is not tuned.** Across the 103 fragments the 189 spans produce, the
confirmed total is 156/189 at every threshold from 6 to 15, and falls
only at 20. The one thing it *must* exclude is the empty string a
leading or trailing elision produces: 10 of the 11 sub-12 fragments are
length zero, and the eleventh is length 5. So 12 sits in the middle of a
flat region, and the honest description is "any small positive value".
If a later corpus makes that response non-flat, it is the signal to
revisit it. R3 bars a continuous *score* from being the thing optimised;
nothing here is optimised, and the parameter is reported with its
sensitivity -- the discipline `_evidence_check.overlap_score`'s
docstring already applies to its own `_NGRAM`.

Both are the same kind of move as the character stream itself: name the
thing that is legitimately not verbatim, remove it from both sides, and
keep the comparison exact.

### The tier ladder, and one tier that earned its place thinly

1. Exact, single passage -- 124/189.
2. Exact, adjacent passage pair -- **0/189**.
3. Elision-aware, single passage -- 31/189.
4. Elision-aware, adjacent pair -- 1/189.

Tier 2 fired zero times and is kept only because tier 4 fired once,
which is the same widening under a different tier and shows the case is
real rather than imagined. Record the zero: a later reader deciding
whether to drop the pair tiers should see that the evidence for them is
one span in 189, not be left to assume it was load-bearing.

**The cost of discarding word boundaries, stated rather than discovered
later.** `"the rapist"` and `"therapist"` flatten alike. For a span of
quotation length this is theoretical rather than practical -- it did not
occur once in 189 -- and it fails in the safe direction: it can only
turn an `absent` into a `found`, never invent a finding. Say so in the
module docstring.

## 📄 Where the source text comes from, and why a match is per passage

`passages.source_passages(con, citekey)` -- the ladder that module
already owns, best-first. Rungs 1--2 cover essentially the whole corpus
(the measurement section has the counts), so the good case is the normal
case and the fallback below is the exception.

**Match each `Passage.text` independently. Never concatenate the
document into one stream.** The flatten step strips every separator, so
concatenating fuses passage seams: `...end of para` + `Beginning of...`
becomes `endofparabeginningof`, and a span straddling that seam
*matches* -- reporting "found on p.4" for text that is not contiguous in
the source. A false `found` is worse here than a false `absent`, because
it is the outcome nobody re-reads.

Per-passage matching also makes the reported page exact: a Docling
passage carries a single `prov[0].page_no`, so a hit has one page and
nothing needs a page-range. This is why #131's page-break lesson (a run
split at a source page boundary) mostly does not bite at rungs 1--2 --
it is a fact about the page-level rungs, where there is no quotable text
anyway.

**One documented widening: adjacent passage pairs.** A genuine quotation
spanning a paragraph break would otherwise report `absent`. So after the
single-passage pass fails, retry over each *adjacent* pair only, and
report the hit as `found` with both pages and a note that it spans two
passages. Adjacent-only is the whole safety property: the fusion is one
deliberate, bounded allowance rather than a global stream where any two
of hundreds of passages may fuse.

## 🚦 Three outcomes, not two

Per quote:

| Outcome | Meaning | A finding? |
| --- | --- | --- |
| `found` | Exact match in a passage (or an adjacent pair). Page reported | No |
| `absent` | No match, and the source's text *was* readable in reading order | **Yes** |
| `unverifiable` | The source has no reading-ordered passages, or none at all | No |

`unverifiable` is not defensive padding, and this is the part most
likely to be argued away by a later reader, so the reason is recorded
here. At rungs 3--4 the only text available is `pdftotext -layout`
output, which preserves a page's *visual* arrangement rather than its
reading order: on a two-column paper each line splices two unrelated
columns (82%--89% of long lines on 4 of the 10 papers this project
measured -- `passages.py`'s own docstring). A perfectly correct quote
from one column simply is not contiguous in that text. Reporting it as
`absent` would be the aid asserting a fabrication that is not there, in
a report whose whole purpose is to be trusted about exactly that.

`passages.py` already encodes the same judgement structurally --
`Passage.text is None` at those rungs, so a caller that wants to quote
has nothing to quote. This aid inherits it rather than second-guessing
it. The repository has said this before: #408 taught the figure aid to
say when it measured nothing.

**It is a safety valve, not a common outcome.** All 189 measured spans
resolved to rung 1 or 2, so `unverifiable` fired zero times. Build it,
document it, and do not let its share of this plan's word count suggest
a reader will meet it often.

**Give `absent` a near-miss page.** A bare "not found" cannot
distinguish a fabricated quotation from one the drafter lightly edited,
and alarm fatigue is the stated risk for this whole class of aid.
`passages.distinctive()` plus the per-page scoring
`verbatim_check/_overlap.py`'s `cmd_locate` already performs gives
*"not found verbatim; its distinctive words concentrate on p.7 (86%)"*
for almost nothing. Score it on the *unstripped* passage text: a
reference marker cannot inflate it, because `passages.distinctive()`
drops words of two characters or fewer and `30` is two. Verified rather
than assumed -- none of the 33 residual absents changes its near-miss
score when markers are stripped first. It is what makes the finding
actionable, so put it on
the `absent` path -- which is a rung-1--2 path by construction, since a
page-level source reports `unverifiable` and never `absent`. Report the
same near-miss beside an `unverifiable` quote too: there it is not
evidence of anything, but it tells a human which page to open.

## 🔒 Binary, deterministic -- and still not a gate

[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)'s Layer 4 currently says
the aids *"answer questions of judgement"*. This one does not, and the
paragraph immediately after it already supplies the correct argument:
**which side a check falls on is decided by what it is measured
against, not by how decidable its answer is.**

The gate compares a citekey to the ledger -- ground truth from the
human's own `.bib` export and a real parse of a real PDF. This aid
compares a span to a *derived artefact*: the parse, at whichever rung
the ladder reached today. An enrichment run that has not happened, a
backend switched to `pdftotext`, a re-parse of an edited PDF -- each
changes the answer without anything changing about the source. `absent`
is therefore a statement about the parse as much as about the paper,
which is precisely why `unverifiable` has to exist as a third outcome,
and why a check needing a third outcome cannot be a two-valued gate.

Make the seventh aid the worked example in that section rather than an
exception to it. It is the sharpest one the layer has: deterministic,
binary, near-ground-truth -- and still advisory.

**This edit belongs in the first PR, not the documentation sweep.** It
is a claim about what the layer *is*, not a count bump, and it is the
one documentation change that argues rather than reports. Landing it
beside the module that motivates it puts it in front of a reviewer who
is already weighing whether a deterministic aid belongs in an advisory
layer; landing it in a wide mechanical diff is where it would get the
least scrutiny of anything in this plan.

## 🧾 The finding shape (R2, R10)

`finding_id(citekey, quote) = sha256(f"{citekey}\n{quote}").hexdigest()[:12]`
-- position-free, keyed on the pair whose truth is in question, matching
`uncited_prose.finding_id`'s convention. State both halves of what that
does, the way that function's docstring does, so the second is not read
later as an oversight:

- **Editing an unrelated block renames nothing**, and re-attributing the
  quote or correcting it to the real span makes the finding disappear --
  which is what "this finding is gone" should mean (R2).
- **Any edit to the quote text is a new finding by construction**,
  including a typo fix in a quote that was otherwise fine. That is
  wanted rather than tolerated: a changed span is a different assertion
  about the source, and it has not been checked. The alternative --
  keying on the citekey alone -- would let a repaired quote inherit its
  predecessor's identity and, in a `recheck`-style comparison, look
  like a finding that had been resolved.

`--json`, **no timestamp**, envelope from `review.envelope()`. Payload
beyond the envelope: `quotes_total`, `found`, `absent`, `unverifiable`,
and one `findings` object per `absent` quote -- `id`, `citekey`,
`quote`, `near_miss_page`, `near_miss_score`. The `found` and
`unverifiable` quotes are counted, and the `unverifiable` ones named
with their reason, so a reader can tell "seven checked, all clean" from
"seven skipped".

**Every confirmed quote carries the tier that confirmed it** --
`exact`, `exact-pair`, `elided`, `elided-pair` -- in both the Markdown
and the JSON. Not decoration: `elided` means the aid matched fragments
around an ellipsis, and a reader deciding whether to trust a rendered
quotation should be able to see that the check was ordered-subsequence
rather than contiguous. It is also the field that would show a later
maintainer whether the pair tiers ever fire in practice, which this
plan can only answer for one corpus.

Flags mirror `uncited`: `--json`, `--write`, `--formats md,tex,pdf`.
Exit 0 on every successful run, findings or not; 1 for a draft the
layer will not read; 2 for a malformed invocation.

## 🧱 Module layout

C2 caps a module at 250 code lines, so this lands as:

| File | Holds |
| --- | --- |
| `chitragupta/review/quotation.py` | The CLI surface, `Report`, findings, payload -- `uncited_prose.py`'s shape |
| `chitragupta/review/_quotation_match.py` | `flatten()`, the per-passage and adjacent-pair search, the near-miss scoring. The only part with an argument in it, and the only part worth unit-testing directly |
| `chitragupta/review/_quotation_render.py` | The Markdown report, beside `_uncited_render.py` |

## 🧪 Tests, to the 100% bar

The five #383 names, plus the ones this plan's own decisions create:

1. An exact span is found, and its page reported.
2. An absent span is a finding.
3. A hyphenated / line-wrapped span is still found.
4. A pre-A2 dossier (no `quote:`) checks nothing and exits 0.
5. Byte-identical output over two runs.
6. A legacy `support:`-only block raises nothing -- not even
   `unverifiable`; it is not in the universe at all.
7. A ligature (`ﬁ`) and a curly-quote variant are both found.
8. A span straddling two passages' seam is **not** reported `found` by
   the concatenation path -- the false-`found` guard, and the one test
   that pins the per-passage decision.
9. A genuine span across an adjacent pair *is* found, with both pages.
10. A page-level-only source reports `unverifiable`, never `absent`.
11. An `absent` finding carries a near-miss page when the words are
    there.
12. A quote for a citekey the draft no longer cites is not checked.
13. A span the source carries with an inline `[30]` reference marker in
    the middle is **found** -- the single biggest cause of a false
    finding in the measurement above, and the one no reader would guess
    from the issue text.
14. An elided quote (`"... ... ..."`) whose fragments appear in order is
    **found**; one whose fragments appear *out of order* is `absent`.
    The second is what keeps tier 3 exact rather than fuzzy, and it is
    the test that stops a later reader loosening it into a word-overlap
    score.
15. An editorial insertion (`"with low budget [who] can start"`) is
    treated as an elision, not as a literal bracket to match.

**Build fixture 3 and 7 from a real
`content/parsed/<citekey>.passages.json` passage**, not from
hand-authored source text. Those are the two tests whose whole point is
that real PDF text carries ligatures and line-wraps a reconstruction
would not reproduce -- the same lesson
[plans/d2-tikz-layout-check.md](d2-tikz-layout-check.md)'s history
records about validating against real figures. There are currently zero
`quote:` blocks in the live dossiers, so the fixture dossier is
synthetic by necessity; the *source* text it is checked against does not
have to be.

**Fixtures 8 and 9 are the hardest to construct** and the plan owes them
a source. Take two consecutive records from one real
`content/parsed/<citekey>.passages.json`: fixture 9's quote is the tail
of the first plus the head of the second, which is a real span across a
real paragraph break; fixture 8's is the *last few words of the first
plus the first few of the second* chosen so that the two fuse into
something that reads as a phrase but is not one -- the seam artefact
itself. Both are cut from the same file by the same rule, so the pair
stays honest about what distinguishes them.

## 🧹 R10: the sweep, in full

The `RuntimeError` in `review/__main__.py` catches a half-registered
dict. Nothing catches a stale prose count, and there are more than the
issue lists. `grep -rn '\bsix\b' chitragupta/ docs/ *.md` before
starting and again before pushing.

**Registration (fails at import if missed):** `review.AIDS`,
`review/__main__.AIDS`.

**Named in #383:** `AGENTS.md` (the review-layer paragraph, ~l.197),
`docs/CLI.md` (index entry, the command table, and a
`### 🔍 chitragupta review quotation` section with the JSON field list),
`docs/REVIEW.md` (`## 🧩 The six aids`, the per-aid section, and the
report-paths block ~l.128), `README.md` (~l.82, the enumerated list),
`mkdocs.yml` (nav -- the silent one, since missing nav is INFO rather
than a `--strict` failure).

**Six-count prose #383 does not list:**
`chitragupta/review/__init__.py` (six sites), `review/__main__.py`
(docstring and `DESCRIPTION`), and the "one of the six" line in each of
`citation_provenance.py`, `citation_coverage.py`, `synthesis.py`,
`uncited_prose.py`, `verbatim_check/__init__.py`,
`figure_layout/__init__.py` -- each of which also carries a "beside
`...`" enumeration that gains a name. In `docs/`: `ARCHITECTURE.md`
(l.312, 344, 430, 510, 614 -- excluding the Layer 4 rewrite, which is
the next section and not part of this sweep), `LADDERS.md` (l.461),
`CONFIG.md` (l.140), `INSPIRATION.md`
(l.94), `DIAGRAMS.md` (l.76), `FEATURE-ROADMAP.md` (l.659, the agenda's
input count).

**Four Mermaid diagrams enumerate the aids** and need a name added and
a re-render: `docs/diagrams/00-main-workflow.mmd` (node `A6` is the
last aid; this adds `A7`), `v3-artifacts.mmd` (two sites),
`g1-corpus-led.mmd`, `extra-sequence.mmd`. `mmdc` needs `--no-sandbox`
on this host, and an unchanged `.mmd` still re-renders to a different
width, so expect diff noise and do the four in one commit.

That footprint looked like an argument for **splitting the work into two
PRs** -- module, tests, AIDS dicts and the Layer 4 rewrite first, then
the count-and-enumeration sweep. **It is not, and the split did not
happen**; see "What changed on the way". Four test modules machine-check
that every registered aid reaches REVIEW.md, FEATURES.md, PACKAGING.md
and the four diagrams with their SVGs, so a first PR that registered the
aid without sweeping would ship a red suite. The sweep is part of
landing an aid here, not follow-up tidying.

## 📋 The agenda class

[docs/AUTO-IMPROVEMENT.md](../docs/AUTO-IMPROVEMENT.md)'s item-class
table gains a row. #383 asks that the unattended question be answered
explicitly, because the layer's default is surfaced-only.

| Class | Source | Kind | Unattended? |
| --- | --- | --- | --- |
| `misquoted` | quotation | defect -- the span is not in the source | no -- surfaced. Binary and deterministic, so R3 is satisfied and the agenda may rank it; but the defect is in `evidence.md`, and `agenda-reviser` edits drafts. There is no unattended repair for a bad `quote:` |

So: a legitimate candidate for an unattended class *on the check's
character*, declined on where the defect lives. That is the honest
answer, and it follows the `uncited-claim` row's own shape -- binary,
rankable, repair left to a human, with the reason stated rather than
implied. Bump the "Six item classes" count in
`docs/FEATURE-ROADMAP.md` (l.663) to seven.

## 🚫 Deliberately out of scope

- **Finding where a misattributed quote actually came from.** "This span
  is verbatim in `X`, but attributed to `Y`" would be a better finding
  than `absent`, and `chitragupta/overlap_index.py` could answer it.
  It is a whole-corpus scan with its own cost and cache story, and it
  turns a cheap per-draft check into an expensive one. A follow-up
  issue, not this one.
- **A `page:` field.** Rejected above, with reasons.
- **Checking `claim:`.** That is C2, continuous, and a different
  question.
- **Quotations that are prose rather than a field.** Every real dossier
  writes its quotations inline, in quotation marks, inside a bullet that
  names a citekey -- 189 of them in the backup alone. Those are exactly
  the artefacts C3 is about, and a field-based aid cannot see one. It is
  a genuinely harder problem, and the measurement shows why rather than
  merely asserting it: 11 of the 33 residual absents are the book's own
  scare-quoted phrases (`"explain it to a sponsor"`, `"which do you
  believe?"`), which no rule distinguishes from a quotation by shape
  alone. A `quote:` field carries the human's declaration that this *is*
  a quotation, and that declaration is what makes the check decidable.
  Worth its own issue; not worth widening this one to guess at.
- **Any gate.** Barred outright by `DEVELOPER-AGENTS.md`, and argued
  above on this aid's own terms rather than on the general rule.

## 📝 Record the outcome

Per [plans/README.md](README.md), when this merges, replace the status
line with the PR that closed it and add a "What changed on the way"
section naming anything that landed differently from the above. A plan
that no longer matches what shipped is worse than no plan.
