# Verbatim scan: content/drafts/dt-overview/survey.md

> **Review aid, not a gate.** This report is evidence for a human judgement, never a verdict. A driver may read it back; no draft is blocked by what it says. See SOUL.md, and docs/ARCHITECTURE.md's "Layer 4: the review layer".

- Draft: `content/drafts/dt-overview/survey.md`
- Command: `python -m chitragupta.review verbatim scan content/drafts/dt-overview/survey.md --min-run 8 --gap 1 --write`
- chitragupta 6.166.1
- Allowlist: none configured (`content/verbatim_allowlist.toml` not found)

## How to read this

Every run of at least `--min-run` words this draft shares with **any**
parsed source in the corpus, cited or not. Sharing wording is not by
itself misconduct -- a defined term, a standard's name and a correctly
quoted sentence all show up here -- so each finding is a place to look,
not a charge.

Two flags narrow the reading:

- **UNCITED SOURCE** -- the paragraph the run sits in does not cite the
  source it matched. That is the finding `overlap` structurally cannot
  make, and the one most worth reading first.
- **quoted** -- the run touches quote delimiters, so it is most likely
  a deliberate quotation. A run is usually wider than the quotation
  inside it -- it can open in the draft's own framing prose -- so this
  reads as overlap, not containment.

Each finding names its `tier`: **exact** is a verbatim run; **skip-gram**
is a tolerant stemmed-subsequence match that also catches a passage
with a handful of words substituted. A skip-gram finding's word count
is `matched words / span`: how many words the tier actually matched,
out of the raw width of text those matches span -- the two can differ
a lot, since a skip-gram window can stretch across stopwords and
opposite-family words that were not themselves matched.

**embedding** is the third tier: a sentence-level alignment between a
section of this draft and the sources its dossier records that section
as written from. It matches meaning rather than wording, so it is the
only tier that can see a genuine restatement -- and the only one whose
findings are not reproducible from the draft and the corpus alone,
since the vectors change with `[enrich].embedding_model`. Its `score`
is that alignment's strength, not a probability and not comparable to
anything the other two report; a passage a deterministic tier already
flagged is left to that tier rather than reported twice.

**Where a finding shows two blocks, `Draft:` and `Source:`, the two are
not the same wording** -- had they been, the exact tier would have
caught it and the tier that did report it would have stood aside. Read
them against each other, using the markup:

- **Bold** on either side -- a word that side has and the other does
  not: substituted, or added by the draft.
- *Italic*, source side only -- a word the source has that the draft
  dropped.
- Unmarked -- the wording the two actually share. That is the overlap,
  and it is left bare so it is the one thing on the line the eye finds
  without looking.

The draft side is normalized (lowercased, punctuation dropped) because
that is the stream the tiers compare; the source side is its own text as
parsed. So do not read a difference in capitals or apostrophes as a
finding -- the comparison behind the markup is run on normalized words on
both sides, and marks none of that.

An **exact** finding shows one unmarked block instead of two: the tier
only fires where the wording is identical, so there is no second side to
show and nothing to mark.

An **embedding** finding's word count says `aligned`, not `matched`: it
is the width of the aligned sentences, not a count of words the two
sides share. A long `aligned` count with a low `score` is a weak
alignment over a long sentence, not a long lift.

Findings below are grouped most-damning-first: long runs, then short
ones, then quoted runs -- but a quoted run only drops into the last
group when it also cites the source it matched. A quoted run from an
uncited source is still grouped by length (on matched words, not raw
span), not buried under `quoted`.

The allowlist bullet above names a per-host, gitignored file
(`content/verbatim_allowlist.toml`, see docs/PLAGIARISM.md) of
boilerplate this host's owner has decided never to flag -- a run is
only dropped when what's left after discounting the allowlisted text
would no longer clear `--min-run` on its own, so a real lift that
merely contains a defined term still shows up below.

**A clean run is not a clean bill of health.** This draft has been
checked against all three tiers, but they do not cover the same
ground: the two deterministic ones see wording, and the embedding
tier sees meaning only within each section's own recorded sources.
Reuse from a source a section's dossier does not record is outside
what any of the three can find by restatement alone. See
docs/PLAGIARISM.md.

## Findings

11 run(s), grouped most-damning-first.

### Short runs

#### 17 words, 8 matched -- `sample_dt_sync_2023` p.1 (tier=skip-gram)

At draft line 23, paragraph 6.

Draft:

> across nine simulated production cells event driven **synchronisation** reduced transmitted volume by 71 percent against one second

Source:

> across nine simulated production cells, event-driven **flows** reduced transmitted volume by 71 percent against one-second

In context: threshold push and event driven flows across nine simulated production cells event driven synchronisation reduced transmitted volume by 71 percent against one second polling while holding worst case staleness...

#### 15 words, 6 matched -- `sample_dt_overview_2024` p.1 (tier=skip-gram)

At draft line 12, paragraph 3.

Draft:

> synthetic survey of forty deployments twenty eight systems described as twins were by **this** definition

Source:

> synthetic survey of forty deployments, twenty-eight systems described as twins were, by **the** definition

In context: strictly keeps expectations honest in one synthetic survey of forty deployments twenty eight systems described as twins were by this definition shadows this survey groups the sample...

#### 13 words, 5 matched -- `sample_dt_factory_2022` p.1 (tier=skip-gram)

At draft line 37, paragraph 7.

Draft:

> **showing** supervisors agreeing with the twin in over ninety five percent **of cases**

Source:

> **showed** supervisors agreeing with the twin’*s choice* in over ninety-five percent

In context: accuracy but a published override log showing supervisors agreeing with the twin in over ninety five percent of cases both failures it records were silent...

#### 13 words -- `sample_dt_overview_2024` p.1 (tier=exact)

At draft line 7, paragraph 3.

> a digital model exchanges data with its physical counterpart only through manual steps

In context: here begins by fixing that vocabulary a digital model exchanges data with its physical counterpart only through manual steps a digital shadow adds an automatic...

#### 13 words -- `sample_dt_overview_2024` p.1 (tier=exact)

At draft line 12, paragraph 3.

> synthetic survey of forty deployments twenty eight systems described as twins were by

In context: strictly keeps expectations honest in one synthetic survey of forty deployments twenty eight systems described as twins were by this definition shadows this survey groups...

#### 13 words -- `sample_dt_sync_2023` p.1 (tier=exact)

At draft line 32, paragraph 7.

> a twin that knows it is stale must say so on every read

In context: much as technical marking staleness explicitly a twin that knows it is stale must say so on every read roughly halved operator mistrust incidents in...

#### 11 words -- `sample_std_interop_2021` p.1 (tier=exact)

At draft line 58, paragraph 11.

> twin pilots rarely die of modelling problems they die of integration

In context: model 4 integrating with everything else twin pilots rarely die of modelling problems they die of integration interoperability requires agreement at three layers...

#### 10 words -- `sample_std_interop_2021` p.1 (tier=exact)

At draft line 63, paragraph 11.

> integrated a new asset in a median of six days

In context: named owners sites that maintained one integrated a new asset in a median of six days against seven weeks where semantics were...

#### 9 words -- `sample_dt_sync_2023` p.1 (tier=exact)

At draft line 22, paragraph 6.

> twin is only as trustworthy as its last synchronisation

In context: 2 keeping the twin true a twin is only as trustworthy as its last synchronisation comparing periodic pull threshold push and...

#### 9 words -- `sample_dt_sync_2023` p.1 (tier=exact)

At draft line 24, paragraph 6.

> reduced transmitted volume by 71 percent against one second

In context: simulated production cells event driven synchronisation reduced transmitted volume by 71 percent against one second polling while holding worst case staleness...

#### 9 words -- `sample_dt_sync_2023` p.1 (tier=exact)

At draft line 28, paragraph 6.

> both during slow thermal drift that never crossed its

In context: study s two worst staleness excursions both during slow thermal drift that never crossed its configured delta trust is behavioural as...
