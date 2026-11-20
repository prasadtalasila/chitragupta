# 🚫 Rejection

Status: **reasoning document.**

**Written for** someone weighing a change to retrieval, or wondering why
a stage that looks obviously useful was built and withdrawn. **Assumed:**
[RETRIEVAL.md](RETRIEVAL.md). **Not covered here:** how retrieval is run,
which is [CLI.md](CLI.md).

Turning a source *down* is the judgment the rest of this pipeline rests
on. A two-stage retrieval read built to make rejection cheaper was
withdrawn before it shipped, and parts of it were kept. The reasoning is
recorded because the mistake is easy to make twice.

This page assumes the two-pool token framing of
[TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md),
which works the accounting through with caching applied.
[DRAFT-ITERATION.md](DRAFT-ITERATION.md) covers the dossier. Every token
figure below is an estimate derived from file sizes and documented
defaults; measured costs are in [PERFORMANCE.md](PERFORMANCE.md).

## 💡 Why rejection and not selection

A genre skill retrieves fifteen candidates per query and keeps about
three. Almost all of its retrieval work is therefore *rejection*, which
has three properties selection does not.

**It is invisible in the output.** A source wrongly kept shows up as a
citation someone can check: `citation_gate` verifies the citekey,
`citation_provenance` scores the claim against the source, and a reader
can disagree. A source wrongly rejected leaves no trace in the draft.

**It is sticky.** [DRAFT-ITERATION.md](DRAFT-ITERATION.md) records
rejected candidates in `rejected.md`, and `draft-reviser` is instructed
not to retrieve and re-judge a candidate listed there with a reason.
That is what makes revision cheap, and also what makes a rejection
permanent: acceptances are revisited every time the draft is edited,
rejections never.

The one deliberate exception is the drift sweep's `reconsider` list: a
declined paper the dossier's queries still reach, carried with its
reason. Re-grounding weighs that reason and re-opens the paper only if
it has stopped holding
([DRAFT-ITERATION.md](DRAFT-ITERATION.md#-re-grounding-after-the-corpus-moves)).
Conversely, a re-grounding pass may not write an unpursued candidate
into `rejected.md` to tidy a drift report, because that would
manufacture a permanent judgment out of a title.

**It propagates into claims.** A survey reports what the corpus does
*not* cover, and `deep-research` reports "blind spots" and may answer
that "no appropriate answer can be formulated from this corpus". A false
rejection therefore omits a source and also manufactures a gap.

The question is how much evidence should stand behind the one decision
the pipeline never revisits.

## ⚡ What the two-stage read costs

As built, it split retrieval into `triage` (a short window, for ruling
candidates out) and `evidence` (query-scored passages, for the survivors
only). Per sub-theme at `k=15`, in characters of payload reaching the
caller:

| | Payload | vs one-stage |
| --- | --- | --- |
| One-stage `search` | 15 x 500 = **7,500** | -- |
| Two-stage, 3 survive triage | 2,400 + 3 x 1,200 = **6,000** | -20% |
| Two-stage, 5 survive | 2,400 + 5 x 1,200 = **8,400** | +12% |
| Two-stage, 8 survive | 2,400 + 8 x 1,200 = **12,000** | +60% |

**The saving is conditional on rejecting hard.** Two-stage wins below
about five survivors and loses above eight. Models are agreeable, so the
likely failure is passing candidates through, which costs more than
one-stage, and nothing reports it.

**It is a constant factor on a cost that was already removed.** The
structural cost was having no revision path, so that changing a
paragraph meant re-running the pipeline. The dossier removed that;
context-trimming is "a constant factor on a run you'd no longer need to
make".

**The reliable reduction is somewhere else.** The two cost pools are
orchestrator-resident (re-sent every remaining turn) and subagent
one-shot (paid once). Two-stage reduces *bytes retrieved*; the subagent
boundary changes *which pool those bytes land in*. That effect is
larger and more certain, needs no retrieval change, and works the same
for every genre.

## 🐛 The bug the split exposed

The original `_snippet` anchored its window on the first occurrence of
whichever query term came out of a Python `set` first. String hashing is
randomised per process, so **the same query on the same document
returned a different snippet from one run to the next** (four hash
seeds, four windows).

At a 500-character window that was a quality wobble. Once `triage` cut
the window to 160 characters and made it the sole basis for rejection,
it meant an **irreproducible rejection**, which `rejected.md` then
entrenched for every later revision.

The ordering was also wrong. `evidence` scored its windows by
distinct-term coverage while `triage` inherited the arbitrary snippet,
so the stage whose decision cannot be undone read the worse evidence.
`search` and `evidence` now share one deterministic, best-covering
chooser, the part of this work that outlived the split.

Two lessons worth keeping:

- **Shrinking a window promotes the quality of window selection from a
  nicety to a correctness property.** The bug had been in `search()` for
  every caller; the smaller window made it matter.
- **Put the better machinery under the irreversible decision.** The
  thing you discard is where a mistake cannot be recovered.

## ⚠ Why it does not generalise across genres

Two-stage was designed against `survey-writer`'s profile (over-fetch at
`k=15`, keep about three).

| Genre | Citekeys in the measured example | Fit | Dominant problem |
| --- | --- | --- | --- |
| `tutorial-writer` | 1 | **Poor** | Pure overhead |
| `textbook-chapter-writer` | 6 | Neutral | Neither helps nor hurts |
| `survey-writer` | 36 | **Best** | A false rejection becomes a false *gap claim* |
| `thesis-chapter-writer` | 26 | Mixed | Discards the sources that qualify an argument |
| `deep-research` | 11 | **Worst** | Solves a problem it does not have; breaks one it does |

The counts are from the example drafts measured at the time; the
argument rests on each genre's citation profile, not on any one file.

**`tutorial-writer`** cites one to three pointers in a closing section.
The machinery is overhead against a saving of a few hundred characters;
its real bottleneck is verifying the lesson runs.

**`textbook-chapter-writer`** cites for motivation, which an abstract
states, so a short window already suffices. It is the least harmed and
the least helped.

**`survey-writer`** is the genre it fits. Its exposure is the gap
analysis and comparison table: a false rejection turns covered ground
into a *reported gap*, a wrong claim rather than a missing one.

**`thesis-chapter-writer`** needs the sources that complicate its
argument, and those qualifications live in discussion and limitations
sections. Triage favours sources that state their position early, which
quietly biases a chapter toward agreement.

**`deep-research`** has [its own section](#-why-deep-research-keeps-the-boundary-alone).

## ❓ Was it worth building at all?

The split was not worth it; most of what was built alongside it was.

Kept, independent of any split:

- **The window chooser.** `_windows` is anchored on every occurrence of
  every term, scored by distinct-term coverage, de-overlapped and
  deterministic. It serves one-stage `search()` too.
- **The retrieval CLI.** `python -m chitragupta.draft retrieve` replaced
  ad-hoc `python -c` one-liners whose output shape varied per skill and
  which had nowhere to hang a flag.
- **`evidence` as a command.** "Show me the passages of this paper that
  bear on this query" is useful on its own, without a triage stage.
- **`--log` and `retrieval.md`.** Measurement is what would turn the
  estimates here into numbers; a still-open issue tracks doing so.

Not carrying its weight:

- **`triage` as the default drafting path.** Its saving is conditional,
  unmeasured, and fits one of the five drafting genres. It buys an
  estimated 20% of one cost pool at best and costs 60% more in the
  plausible bad case, while adding an irreversible, entrenched decision
  made on a third of the evidence and doubling the retrieval
  instructions in every skill that adopts it.

The split was removed before merging. Keeping it as an optional mode was
also rejected: an option nobody defaults to is an option nobody tests,
it would keep inviting the "light/thorough" toggle
[the configuration section](#-should-any-of-this-be-configurable) argues
against, and it is cheap to reinstate from this page if measurement
ever finds a case for it.

The arithmetic table above exists because an earlier default (3 windows
of 700 characters) lost to one-stage in *every* scenario and nobody had
checked. No test pins that arithmetic: it went with the `triage` path,
and `chitragupta/retrieval_cli.py`'s "a lookup rather than a mandatory
stage" comment points back here.

## ✍ Recording how a rejection was made

`rejected.md` records *that* a candidate was turned down and *why*, but
not *on what evidence*. Those differ by nearly an order of magnitude:

| Rejection made at | Evidence behind it | Invalidated by |
| --- | --- | --- |
| **scope** ("adoption economics is out of scope") | none needed; it is about the draft, not the paper | a scope change |
| **triage** (removed) | ~160 characters, one window | nothing |
| one-stage `search` | ~500 characters | nothing |
| **evidence** | ~1,200 characters, two query-scored passages | the claim changing |

Recording the stage would let `draft-reviser` apply a tiered rule: never
re-fetch a scope rejection (re-read `scope.md`), trust an evidence
rejection, and **re-check triage rejections when the change touches that
sub-theme**. It would also let a gap analysis say honestly how many
candidates were ruled out unread, and give `dossier status` a health
signal.

The tension is who writes the label. A model can fill one more column
in wrong, and a wrong label is worse than none because it is trusted.
The alternatives are to **derive** it by joining `rejected.md` to
`retrieval.md` on the query (mechanical, but joining on free text is
fragile), or to **have the tool write it** via a `dossier reject`
subcommand (most reliable, but it trades away the "Markdown a human can
freely edit" property the dossier rests on).

**Unbuilt.** With `triage` removed, the weakest tier has no producer.
The drift sweep's `reconsider` list covers the "re-check when the change
touches that sub-theme" half at no cost. The stage column remains the
better answer for an honest gap analysis, and is blocked on who writes
it.

## 🤖 Why deep-research keeps the boundary alone

`deep-research` is the worst fit for the split, for four independent
reasons.

**It has already paid for the mechanism that matters.** Its interviewers
run in subagents, so what they read is already one-shot. Two-stage
inside a subagent optimises the cheap pool while adding cost: at
standard depth (6 personas x 3 rounds x up to 3 reformulations, roughly
54 triage calls), five survivors each means on the order of 270 further
process starts, each also a turn inside a subagent's own context budget.

**Contradiction mapping needs the disagreement that triage discards.**
Disagreement is stated in discussion and limitations sections, not near
a keyword hit. A paper whose abstract agrees and whose discussion
dissents is kept for the wrong reason or dropped unread.

**It turns honest findings into artifacts of the screen.** Under hard
triage, "no appropriate answer can be formulated from this corpus" and a
reported blind spot silently mean "nothing survived a 160-character
screen", a weak claim presented as a strong one.

**Persona diversity is the method.** STORM's measured gain comes from
perspectives finding *different* things. "Reject hard at triage" pushes
all six personas toward the same high-scoring core.

The place to cut `deep-research`'s cost is the interview packets held
resident across Phases 3-7, not the retrieval inside Phase 2. What
`dossier brief` collects is the *re-emission* of those packets into four
dispatch prompts
([TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md#-what-the-dossier-actually-recovers)).
That does not reopen the case for triage: these reads still happen
inside subagents, where they are billed once.

## ⚙ Should any of this be configurable?

`PROVENANCE_WEAK_SCORE` and `PROVENANCE_GOOD_SCORE` are precedent for
judgment thresholds in `config.toml`, so moving `160`, `500`, `600` and
`2` there is tempting. It is the wrong call, for four reasons.

**They are not independent knobs.** The break-even is a *function* of
`TRIAGE_CHARS`, `EVIDENCE_CHARS`, `EVIDENCE_WINDOWS` and `k` together.
Separate settings invite combinations that silently invert the design,
as the 3-windows-of-700 default did, and a config value could not be
pinned by a test.

**The flexibility already exists at a better granularity.** `--chars`,
`--windows` and `--k` are per-call, explicit at the call site and
visible in `retrieval.md`. Config would make the same choice invisible.

**`config.toml` is gitignored per-host data.** A dossier's rejections
would depend on a setting recorded nowhere and differing per machine;
see
[ARCHITECTURE.md](ARCHITECTURE.md#-what-is-reproducible-and-what-is-not).

**One global toggle re-creates the mistake.** The right regime is
genre-dependent.

### 🔀 On switching regimes between runs

This applies to *any* future setting that changes how much evidence a
rejection rests on.

A light/thorough dial has the economics backwards: two-stage is cheap
only when you reject hard, and "thorough" means keeping more survivors,
which costs more than one-stage's flat 7,500 characters. A dial would be
better as a *depth preset* like `deep-research`'s
`quick`/`standard`/`deep`, where one name moves several parameters
coherently.

The stronger objection: **a mixed dossier ratchets downward, and the
weakest setting wins permanently.** `rejected.md` accumulates across
runs and is trusted by later revisions, so one light pass's
160-character rejections are skipped by every careful run that follows.
Rejections are sticky and acceptances are not, so the mixture degrades
to the least careful setting ever used. That makes
[recording the stage](#-recording-how-a-rejection-was-made) a
prerequisite for configurability. Without it, `retrieval.md`'s totals
also cannot distinguish a cheap run from a cheap setting.

**Recommendation.** Do not add the four numbers to config. If a dial is
wanted, add named profiles (`thorough` = one-stage at 500; `frugal` =
triage/evidence) chosen per genre by default and overridable per
invocation, and land the stage column first. Revisit once measurement
has shown whether the window sizes matter on a real corpus.

## ⚖ What was decided

- **The window chooser, the CLI, `evidence` and `--log` stay.** None of
  them depends on the split.
- **`_snippet` and `evidence` share one deterministic chooser**, so the
  rejection decision is reproducible and reads the best-covering passage.
- **The broad rollout is cancelled.** The issue proposing to "wire
  the remaining four genre skills to the dossier *and* two-stage
  retrieval" is closed as not planned. The dossier half shipped on its
  own: every drafting genre skill opens a dossier with `dossier init`,
  which `draft-reviser` reads.
- **`triage` is removed**, along with `TRIAGE_CHARS`, its CLI subcommand,
  and the reject-hard instruction in every skill. `search()` plus the
  subagent boundary is the drafting path. `evidence` remains as a lookup
  for deepening an acceptance.
- **Nothing here is measured.** Every token figure is an estimate derived
  from file sizes and documented defaults. `retrieval.md` records
  characters, not tokens, and nothing records what a drafting turn costs.
