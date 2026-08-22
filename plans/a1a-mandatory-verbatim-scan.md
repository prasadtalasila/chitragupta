# Making the verbatim scan a required step

Status: **shipped in 6.20.1.** Written 2026-08-22 for
[#312](https://github.com/prasadtalasila/chitragupta/issues/312) /
[A1a](https://github.com/prasadtalasila/chitragupta/pull/350),
and implemented the same day.

**What changed between planning and building**, recorded here rather than
silently corrected, because two of the three are the kind of thing this
directory exists to catch:

1. **The sweep was 22 sites, not the 17 this document first counted.**
   `#346` and `#347` merged while the plan was being written -- the
   review layer went from four aids to six -- and each new aid carried
   its own copy of the sentence. The final tally is in
   [Part 1](#part-1----the-amendment-sweep), rewritten against the tree
   as built.
2. **The `#313` interaction turned out to be moot, and for a better
   reason than expected.** It shipped as `#346` with the evidence
   material in a **rendered sidecar beside the draft**, not an appendix
   inside it -- because `content/dossiers/` is gitignored precisely
   because it quotes copyrighted sources, while the example draft
   directories are tracked. So the quoted spans never enter the file the
   scan reads, and none of
   [the three predicted interactions](#the-interaction-with-313-being-built-in-parallel)
   materialised. The section is kept because its finding about
   `_mask_for_scan` is still true and still unrecorded elsewhere.
3. **The test's window had to be re-anchored.** The plan assumed the
   scan command could anchor every check. It cannot: four skills mention
   `verbatim scan` outside the step -- `overlap-reviser` four times,
   once in its own frontmatter -- so demanding a `tiers_not_run` sentence
   near every mention would demand one in a skill description. The step
   is anchored on the regeneration command instead, which appears only
   in the step.

**Written for** whoever flips the nine skills. It assumes
[docs/GENRE.md](../docs/GENRE.md) for the shared skill invariants,
[docs/PLAGIARISM-DESIGN.md](../docs/PLAGIARISM-DESIGN.md) for the three
detection tiers, and
[plans/f-auto-improvement-adoption.md](f-auto-improvement-adoption.md)
for the amendment this depends on.

**Not covered here:** why the review layer may be driven at all. That is
[AUTO-IMPROVEMENT-RATIONALE.md](../docs/AUTO-IMPROVEMENT-RATIONALE.md)
§"The amendment this needs", and this document does not restate its
argument -- only its consequences for one item.

**Why this item gets a plan at all**, when
[plans/README.md](README.md) excludes "one mechanical edit repeated": the
skill edits are mechanical, and the two things around them are not. The
issue's precondition -- *"whatever makes `sections.md` carry
citekeys"* -- turns out to be misdiagnosed, and what a skill must say
when tier 3 cannot run is a contract nobody has written down. Both are
settled below rather than left for an implementer to invent.

## Table of contents

- [Three corrections to the issue as filed](#three-corrections-to-the-issue-as-filed)
- [The measurement that justifies the whole item](#the-measurement-that-justifies-the-whole-item)
- [Part 1 -- the amendment sweep](#part-1----the-amendment-sweep)
- [Part 2 -- the three diagrams](#part-2----the-three-diagrams)
- [Part 3 -- the nine skills](#part-3----the-nine-skills)
- [Part 4 -- the `sections.md` precondition](#part-4----the-sectionsmd-precondition)
- [Part 5 -- what a skill says when tier 3 cannot run](#part-5----what-a-skill-says-when-tier-3-cannot-run)
- [Part 6 -- the test, written first](#part-6----the-test-written-first)
- [Part 7 -- the measurement, as taken](#part-7----the-measurement-as-taken)
- [The interaction with #313, being built in parallel](#the-interaction-with-313-being-built-in-parallel)
- [Order of work](#order-of-work)
- [Explicitly not in scope](#explicitly-not-in-scope)
- [Risks, and what would falsify this plan](#risks-and-what-would-falsify-this-plan)

## Three corrections to the issue as filed

The issue was written before two things happened. Each correction is
verifiable from the tree, and each changes what gets built.

### 1. The blocker is discharged, and two documents do not know it

Issue #312 opens *"Blocked on a person's decision, not on engineering
time"* and says the amendment *"is the user's call and comes first."* It was
taken on **2026-08-21** and is recorded in
[plans/f-auto-improvement-adoption.md](f-auto-improvement-adoption.md)
§"Decision 1 -- the amendment is approved".

Two documents still read as though it is pending, and reconciling them
is part of this work rather than a separate cleanup:

| Site | What it still says |
|---|---|
| `docs/FEATURE-ROADMAP.md`, §"The decision that gates part of this" | frames the amendment as an open question, and A1a as blocked on it |
| `docs/AUTO-IMPROVEMENT-RATIONALE.md`, §"The amendment this needs" | *"It is the first thing to settle, before any code"* |
| `docs/AUTO-IMPROVEMENT.md`, build order step 1 | **"Settle the amendment."** Not a coding task -- unannotated, where steps 2/3/5 carry a *Done in x.y.z* rider |

The rationale is a **reasoning document** and keeps its argument intact;
what it gains is a dated line saying the decision went the way the
argument recommended, in the shape steps 2--5 of the build order already
use. The roadmap's gating section shrinks to a pointer.

### 2. "Twelve sites" is stale -- it is thirteen, plus a four-site family

The rationale counted twelve on 2026-08-11. Two things have moved since,
and the sweep it publishes finds only one of them.

**#341 landed the `synthesis` aid on 2026-08-22** with its own copy of
the never-automatic docstring, and with three new copies of the banner
sentence. **The rationale's own grep misses `docs/GENRE.md`**, because
its regex has no term for *offered* -- and GENRE.md is the one file that
states the rule for all nine skills at once, which makes it the most
load-bearing site of the set.

The re-derived table is [Part 1](#part-1----the-amendment-sweep). Do not
carry the number twelve into the PR body; re-run the sweep and count
what is there on the day.

### 3. The `sections.md` precondition is misdiagnosed, and the truth is cheaper

Issue #312 says tier 3 is skipped on the four sample drafts *"because
`sections.md` records no citekeys"*, and asks for "whatever makes
`sections.md` carry citekeys by the time the scan runs."

That message is misleading, and following it would build the wrong
thing. `/workspace/content/dossiers/digital-twins-for-software-engineers`
**does not exist** -- those four drafts have no dossier at all. The
reason string names a `sections.md` path that was never there because
`dossier.citekeys_by_section()` returns `{}` for a missing directory and
`overlap_embed._dossier_scope()` reports both cases with one sentence.

So the four sample drafts are not evidence that skill-written drafts lack
citekeys in `sections.md`. **Every dossier on this host that has one has
citekeys in it** -- 22 `sections.md` files, 12 to 54 distinct citekeys
each, and not one of them empty.

The real gap is narrower and entirely mechanical:

| Skill | Writes `sections.md` today? |
|---|---|
| `survey-writer` | yes, step 8 |
| `thesis-chapter-writer` | yes |
| `textbook-chapter-writer` | yes |
| `tutorial-writer` | yes |
| `deep-research` | yes |
| `draft-reviser` | **no** -- uses `dossier sections` for the outline only, and again when bootstrapping a dossier |
| `corpus-reviser` | **no** -- outline only |
| `book-assembler` | **no** |
| `overlap-reviser` | **no** |

And even in the five that do, the write happens mid-run: a draft edited
after that step is scanned against a stale table. So the precondition is
not "make `sections.md` carry citekeys". It is **regenerate
`sections.md` immediately before the scan, in every skill** --
[Part 4](#part-4----the-sectionsmd-precondition).

## The measurement that justifies the whole item

Run 2026-08-22 against `/workspace`'s real corpus, read-only, no lock:

```console
$ python -m chitragupta.review verbatim scan \
    content/drafts/book-chapters/digital-twin-platforms/digital-twin-platforms.md --json
tiers_not_run: []
findings: 7   -- all 7 embedding-tier, zero exact, zero skip-gram
```

Read it twice. Tier 3 **does** run on this host, on a draft whose dossier
records citekeys. And on that draft the deterministic tiers found
**nothing at all** while the embedding tier found seven passages. That is
[PLAGIARISM.md](../docs/PLAGIARISM.md)'s claim -- restatement is "an LLM's
default failure mode" and "invisible to both deterministic tiers by
construction" -- reproduced on real output, not argued.

It is also the sharpest possible statement of why the precondition
matters: had that draft's dossier been missing, the same command would
have reported zero findings and exited 0, and the report would have
looked like an answer.

## Part 1 -- the amendment sweep

The surviving invariant, from the rationale, unchanged by this document:

> A review finding may be read, may be invoked by a driver, and may never
> block a draft.

Advisory versus blocking, not manual versus automatic.
`python -m chitragupta.draft gate` remains the only gate.
[SOUL.md](../SOUL.md) is **not** amended -- its review bullet claims only
that the layer "never blocks, and must not be made to", which survives
intact. That is what makes this an amendment rather than a rewrite of the
project's premises, and it is why nothing below touches that file.

### Family 1 -- "never automatic" (16 sites, as built)

The rule the amendment abolishes. Each becomes a statement about
blocking. The count is 16 rather than the 13 this document first found:
`figure_layout` (#344) and `uncited_prose` (#347) each landed carrying
their own copy, and `docs/CLI.md` gained a §`figure` statement with them.

| # | Site | Current wording |
|---|---|---|
| 1 | `chitragupta/review/__init__.py` docstring | "None gates, none runs automatically" |
| 2 | `chitragupta/review/__main__.py` docstring | "nothing invokes them automatically" |
| 3 | `chitragupta/review/citation_provenance.py` docstring | "never automatically, never a gate" |
| 4 | `chitragupta/review/citation_coverage.py` docstring | "never automatically, never a gate" |
| 5 | `chitragupta/review/verbatim_check.py` docstring | "never automatically, never a gate" |
| 6 | `chitragupta/review/synthesis.py` docstring | **#341** |
| 7 | `chitragupta/review/figure_layout/__init__.py` docstring | **#344** |
| 8 | `chitragupta/review/uncited_prose.py` docstring | **#347** |
| 9 | [AGENTS.md](../AGENTS.md), Layer 4 bullet | "run by hand on a finished draft, never invoked automatically" |
| 10 | [ARCHITECTURE.md](../docs/ARCHITECTURE.md), §Layer 4 | "Nothing invokes them automatically" |
| 11 | [ARCHITECTURE.md](../docs/ARCHITECTURE.md), inline mermaid label | "advisory, never automatic, never a gate" |
| 12 | [LADDERS.md](../docs/LADDERS.md), the layer table | "never automatic, never a gate" |
| 13 | [CLI.md](../docs/CLI.md), first-run walkthrough | "none of these runs automatically" |
| 14 | [CLI.md](../docs/CLI.md), §`coverage` | "unlike the gate it never runs automatically" |
| 15 | [CLI.md](../docs/CLI.md), §`figure` | **#344** |
| 16 | [GENRE.md](../docs/GENRE.md), shared conventions | "The verbatim scan is **offered**, never run silently and never a gate" |

Site 16 is the substantive one. It is not merely wording: it is the
sentence that tells a reader what all nine skills do, and
[Part 3](#part-3----the-nine-skills) makes it false. It was rewritten to
describe a scan that runs, not one that is offered -- and it is the site
the published sweep missed entirely, because that grep has no term for
*offered*.

**Two of these were missed by the published grep for a second reason**,
and it is worth knowing before the next rule-wide sweep: sites 7 and 8
wrap the phrase across a line ("never\nautomatically"), and a line-based
`grep` cannot see it in prose hand-wrapped to 72 columns. A sweep that
has to be right normalises whitespace per file first. The rationale now
says so.

### Family 2 -- "nothing reads it back" (6 sites, was 1)

Distinct from family 1 and worth separating, because the amendment
touches it for a different reason: a skill that runs the scan and then
presents its findings *is* something reading a report back. Five of the
six landed after the count was taken.

| # | Site | New since the count |
|---|---|---|
| 17 | `chitragupta/review/__init__.py`, `BANNER` | |
| 18 | `chitragupta/review/_synthesis_render.py`, the report preamble | **#341** |
| 19 | `chitragupta/review/synthesis.py`, docstring | **#341** |
| 20 | [CLI.md](../docs/CLI.md), §`synthesis` | **#341** |
| 21 | [CLI.md](../docs/CLI.md), §`uncited` | **#347** |
| 22 | [WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §11 | **#341** |

Plus `tests/test_review_synthesis.py` and `tests/test_review_uncited.py`,
whose module docstrings restate the same sentence in test prose and moved
with it.

**`BANNER` needs care.** It is not only prose: `tests/test_review.py`
asserts the JSON envelope's `notice` is a substring of it, and it is
copied verbatim into every written report. The replacement kept the
two properties that file pins -- no Markdown link, and the
`notice` relation -- so this was a wording change inside an existing
contract, not a free edit. Everything else in the banner ("evidence for a
human judgement, never a verdict", "no draft is blocked by what it says")
is unaffected and stays.

### The replacement text, written once

Seventeen sites have to end up saying the same thing. Pinning the
sentence here is the whole reason this document exists -- nine
hand-written variants is how eight files agree and one does not.

**The shared sentence, for the six code docstrings** (sites 1--6). It
replaces "run by hand on a finished draft, never automatically, never a
gate":

> read over a finished draft, by a person or by a driver, never a gate,
> and never holding the write lock

**The banner sentence** (sites 14--17). It replaces "Nothing in this
pipeline reads it back":

> A driver may read it back; no draft is blocked by what it says

The rest of the banner is untouched -- "evidence for a human judgement,
never a verdict" is the sentence that was always doing the work.

**Per-site, where the surrounding grammar differs:**

| # | Site | Replacement |
|---|---|---|
| 7 | `AGENTS.md` Layer 4 | "read over a finished draft -- by you, or by a skill that runs one on your behalf. Never a gate." |
| 8 | `ARCHITECTURE.md` §Layer 4 | "A skill may invoke them; none of them gates anything" |
| 9 | `ARCHITECTURE.md` mermaid label | `advisory, never a gate` -- drop "never automatic", keep the rest |
| 10 | `LADDERS.md` layer table | "Advisory over a finished draft -- never a gate." Its "When" column becomes "When you ask, and at the end of a drafting skill's run" |
| 11 | `CLI.md` walkthrough comment | "Review aids, not gates: a skill runs the verbatim scan for you, and none of them can block a draft." |
| 12 | `CLI.md` §`coverage` | "**Informational, not a gate** -- unlike the gate, nothing it reports can block a draft." |

**Site 13, `docs/GENRE.md`**, is the one that speaks for all nine skills
and therefore the one worth writing out in full. The heading changes from
**"The verbatim scan is offered, never run silently and never a gate"**
to **"The verbatim scan is run, reported, and never a gate"** -- which is
deliberately the shape of the paragraph two below it, *"The prose check
is run, reported, and never acted on"*, because that is now the same
posture. The body becomes: the scan runs once the gate has passed and the
renders are done, before presenting; it reports wording the draft shares
with any parsed source, cited or not; **it cannot block a draft, and no
skill treats it as a condition of presenting**; and the caveat travels
with it, because the drafter is the one it is about.

The rest of that paragraph -- the two-of-three-tiers explanation and the
"clean scan is not a clean bill of health" close -- is already correct
and stays word for word.

### Two constraints on how the code sites may be edited

**Six of the seventeen sites are docstrings inside modules the C2
ratchet watches, and one has no room.** `code_lines()` in
`tests/test_code_standards_scan.py` *"deliberately counts docstrings"*,
and the limit is 250:

| Module | Code lines | Headroom |
|---|---|---|
| `chitragupta/review/citation_coverage.py` | **250** | **0** |
| `chitragupta/review/__init__.py` | 229 | 21 |
| `chitragupta/review/synthesis.py` | 219 | 31 |
| `chitragupta/review/_synthesis_render.py` | 107 | 143 |
| `chitragupta/review/__main__.py` | 72 | 178 |
| `chitragupta/review/citation_provenance.py` | 457 | registered |
| `chitragupta/review/verbatim_check.py` | 1880 | registered |

So **the `citation_coverage.py` rewrite must not add a single physical
line.** The shared sentence above was written to fit: its four-line
paragraph swaps for a four-line paragraph. Getting this wrong reddens the
suite, and the tempting fix -- adding the module to `LEGACY_LONG_FILES`
-- is exactly the "excused rather than fixed" move that
[plans/f-auto-improvement-adoption.md](f-auto-improvement-adoption.md)
§"The allowlist pin" forbids.

The two registered modules are in no danger: a docstring rewrite cannot
take a 1880-line module under 250, and the register's other half only
fires on an entry that has come back *under* its threshold.

**`BANNER` is a contract, not prose.** `tests/test_review.py` asserts it
holds no Markdown link (`"](" not in review.BANNER`) and that the JSON
envelope's `notice` is a substring of it with `**` stripped. It is also
copied verbatim into every written report. The replacement above keeps
both properties; any other wording must be checked against that file
before it is written.

### Matched the sweep, and deliberately left alone

Recorded so the next person does not "finish" the job by editing them:

| Site | Why not |
|---|---|
| `AGENTS.md`, "reads it back out of the ledger" | the ledger, not a review report |
| `tests/test_sync.py`, "never invoked" | a pool initializer |
| `chitragupta/dossier/_acronyms.py`, "still never automatic" | **drafting** layer. #190's own rule about `acronyms-suggest --apply`, and the amendment is stated only about layer 4 |
| `docs/HOOKS.md`'s title | a document title |
| `docs/AUTO-IMPROVEMENT.md`, "never invoked" | about skill *descriptions* as a trigger mechanism |

That third row is the same carve-out the roadmap already makes for
`style_check`: a drafting-layer command running automatically was never
covered by the rule being amended.

### Two riders on sentences this sweep already rewrites

Both are pre-existing drift that sits *inside* an edited sentence, so
fixing it costs nothing and leaving it costs a later PR:

- `docs/ARCHITECTURE.md` §Layer 4 opens **"Three aids behind one
  command"**; there are four.
- `docs/LADDERS.md`'s layer-4 row names three modules; `synthesis.py` is
  missing.

## Part 2 -- the three diagrams

Three diagrams make a manual-invocation claim on exactly the axis the
amendment abolishes:

| Diagram | Label |
|---|---|
| `00-main-workflow` | `<b>REVIEW AIDS</b> — you run these; none of them is a gate` |
| `g1-corpus-led` | `LAYER 4 · REVIEW — afterwards, by you, never a gate` |
| `extra-sequence` | `Layer 4, the review layer — optional afterwards, never a gate` |

**Each diagram is three artefacts, not one.**
[DIAGRAMS.md](../docs/DIAGRAMS.md) is explicit that the fenced `mermaid`
block in that file is the source of truth and both the `.mmd` and the
`.svg` are exports: *"Edit the fenced block first, then re-render, or the
two drift apart."* So each of the three costs an edit in
`docs/DIAGRAMS.md`, an identical edit in `docs/diagrams/<name>.mmd`, and
a re-render of `docs/diagrams/svg/<name>.svg`.

The `.svg` under `docs/diagrams/svg/` is the "never a gate" text's home
too; that half stays true and untouched.

**Also add `synthesis`.** All three list three aids; there are four as
of #341 -- and the re-render is happening anyway, and a four-aid layer drawn as
three is drift that would otherwise need its own PR.

### The render toolchain, verified on this host

`mmdc` is not installed, and the documented `npm install -g` line is not
what worked. Verified 2026-08-22:

```bash
# Chromium's sandbox is unavailable here; bare mmdc dies with
# "No usable sandbox!" before rendering anything.
cat > /tmp/pptr.json <<'EOF'
{"args": ["--no-sandbox", "--disable-setuid-sandbox"]}
EOF
npx -y @mermaid-js/mermaid-cli@latest -p /tmp/pptr.json \
    -i docs/diagrams/<name>.mmd -o docs/diagrams/svg/<name>.svg -b white -w 1900
```

**Expect whole-file SVG churn, and say so in the PR body.** Re-rendering
an *unchanged* `.mmd` on this host already moves the viewBox
(`extra-sequence`: 3130.5 → 3270.5 wide), because the committed SVGs were
rendered where different fonts were installed. That is a font-metric
difference, not a diagram change, and a reviewer who is not warned will
read three enormous diffs as three rewritten diagrams.

Whether to record the `-p /tmp/pptr.json` workaround in
`docs/DIAGRAMS.md` is a judgement call for the implementer: it is
host-specific, but so is the `npm install -g` line already there, and the
next person to re-render will hit the same wall.

## Part 3 -- the nine skills

### The edit

Every skill carries a step of the form *"**Offer the verbatim scan.**
Before presenting, offer this -- don't run it silently, and never make it
a condition of presenting"*. It becomes a step that runs it. The three
clauses do different work and only the first changes:

| Clause | Becomes |
|---|---|
| "offer this -- don't run it silently" | **run it, and show what it found** |
| "never make it a condition of presenting" | **unchanged.** This is the not-a-gate clause, and it is what the amendment preserves |
| "say what it misses" | **unchanged**, and extended by [Part 5](#part-5----what-a-skill-says-when-tier-3-cannot-run) |

### The canonical step, written once

Nine files must end up saying the same thing, so the source text lives
here and is copied, not re-composed per skill. Only the bracketed parts
vary: the step number, the draft path, and each skill's existing
one-sentence reason why the scan earns its place in *that* genre (the
tutorial's "the prose between steps cites nothing", deep-research's "a
dozen subagents wrote sections independently"). Those sentences are good
and specific; keep every one of them.

> N. **Run the verbatim scan.** Once the gate has passed and the renders
> are done, and before presenting, regenerate the section map and scan:
>
> ```bash
> python -m chitragupta.draft dossier sections content/drafts/<path> --citekeys --write
> python -m chitragupta.review verbatim scan content/drafts/<path>
> ```
>
> The first command is what lets the embedding tier run at all -- it
> compares each section against the sources that section cites, and reads
> them from the table the first command writes. If it exits 1 for a
> missing dossier, say so and run the scan anyway.
>
> `<the genre's own one-sentence reason>` It reports wording the draft
> shares with **any** parsed source, cited or not -- including a source
> the citing paragraph never names. **A review aid, not a gate: it exits
> 0 either way, it cannot block the draft, and it is never a condition of
> presenting.** Show what it found rather than summarising it away, and
> report the `long` and `short` buckets first; a `quoted` run that also
> cites its source is a legitimate attributed quotation, so give those a
> count rather than a list.
>
> **Say what it did not check.** If the report's `tiers_not_run` is not
> empty, quote each reason as the scan wrote it, and where the reason
> names a fix (`poetry install --with enrich`, `python -m
> chitragupta.enrich`) pass that on once. It sees verbatim and
> near-verbatim reuse only, and **genuine restatement is only detected
> where the embedding tier can run**, so a clean scan is not a clean bill
> of health (`docs/PLAGIARISM.md`). Repairing a finding is
> `overlap-reviser`'s job, and only if the user asks.
>
> If the user wants the finding kept, add `--write`: the report goes to
> `content/review/`, mirroring the draft's path.

The phrase pinned by `tests/test_skill_verbatim_scan_offer.py` --
*"genuine restatement is only detected where the embedding tier can
run"* -- appears above, unchanged and within the test's 900-character
window of the scan command. That is not incidental; keep it inside the
window when adapting the block.

### It is eight edits and one that already runs it

The issue says nine mechanical edits. `overlap-reviser` is not one of
them: its step 2 baseline **is** the scan, so it already runs. What its
closing section does is say what the scan missed, and that stays. It
still needs [Part 4](#part-4----the-sectionsmd-precondition)'s
regeneration, because it has no `sections.md` step at all and its
baseline is therefore scanned against whatever was last written.

`book-assembler` phrases its step per unit ("Assembly is the last moment
before a whole book is read by somebody else"), and stays per unit.

### What must not change, and why

`overlap-reviser`'s frontmatter ends *"never runs unless a person asked
for it"*, and `docs/GENRE.md` §"Repairing overlap" says *"Only a person
starts it. No hook, no scheduled job, no genre skill at the end of its
run."* Both stay true and both stay written, because
[A1b is withdrawn](../docs/FEATURE-ROADMAP.md#a1b-auto-route-findings-into-overlap-reviser----declined):
the scan runs, the findings are surfaced, and a person decides whether to
invoke the repair loop. A skill repairing its own output is marking its
own homework.

## Part 4 -- the `sections.md` precondition

One block, identical in all nine skills, immediately before the scan:

```bash
python -m chitragupta.draft dossier sections content/drafts/<path> --citekeys --write
python -m chitragupta.review verbatim scan content/drafts/<path>
```

The first line is deterministic and idempotent -- `sections_markdown()`
derives the table from the draft by joining each heading's line range to
the citekeys cited inside it, and the dossier template already calls the
file "rebuildable from the draft". Running it again costs nothing and
guarantees the table describes the draft as it is about to be presented,
not as it was at step 8.

**Two failure modes the skill must handle rather than ignore:**

- **No dossier.** `--write` exits 1 with *"No dossier for `<draft>` --
  run `init` first"*. The skill says so and **runs the scan anyway**: two
  tiers of three is still worth having, and refusing to scan would make
  the missing dossier block a draft, which is the one thing the amendment
  does not permit.
- **A citekey cited above the first heading.** The command already prints
  this on stderr rather than dropping it. The skills that have the step
  today tell the drafter to fix it in the draft and never to hand-edit
  the table; the new block keeps that instruction.

For the four skills that already write `sections.md` mid-run, the earlier
step stays -- it is what makes the table available to a *revision*, which
is a different consumer. This adds a regeneration, it does not move one.

## Part 5 -- what a skill says when tier 3 cannot run

`overlap_embed.open_scope()` has four reasons tier 3 is unavailable, and
a skill can fix exactly one of them:

| Reason | Can the skill fix it? |
|---|---|
| the draft is not under `content/drafts/`, so it has no dossier | no |
| the dossier's `sections.md` records no citekeys | **yes** -- [Part 4](#part-4----the-sectionsmd-precondition) |
| the enrichment layer is not installed | no |
| `CHROMA_DIR` holds no embedded corpus for the model | no |

So on an ordinary checkout the mandatory scan reports **two tiers of
three**, which #312 calls *"worse than not running it, because it looks
like an answer."* Three obligations, decided 2026-08-22, and they are
what stops that:

1. **Print the reason verbatim.** When `tiers_not_run` is non-empty, the
   skill quotes each reason as the aid wrote it. Those sentences were
   written to be read by a person mid-review -- *"the four ways this tier
   is unavailable want four different fixes"* -- and paraphrasing them
   loses the fix.
2. **Never present a partial scan as clean.** The existing caveat --
   *"genuine restatement is only detected where the embedding tier can
   run, so a clean scan is not a clean bill of health"* -- is already in
   all nine skills and is already pinned by a test. It stays, and it is
   the sentence that carries this obligation.
3. **Say how to enable it, once.** Where tier 3 is unavailable for an
   installable reason, surface the fix the aid names -- `poetry install
   --with enrich`, or `python -m chitragupta.enrich` -- so a host can
   become able to detect restatement. Once, in the same breath as the
   reason; not a standing nag.

The scan still exits 0, and none of this can block a draft.

## Part 6 -- the test, written first

`tests/test_skill_verbatim_scan_offer.py` already pins that every skill
mentions the scan and carries the caveat within 900 characters of it. It
is the natural place for the new invariant and the natural failing test
to write first:

- a skill must carry the **regeneration** command (`dossier sections
  ... --citekeys --write`) within the same window as its scan command;
- the file's name and docstring say *offer*, and after this change the
  invariant is that the scan **runs**. Rename to
  `tests/test_skill_verbatim_scan_step.py` and rewrite the docstring; the
  existing docstring's reasoning about why the caveat is conditional is
  still correct and should survive the rewrite.

**The rename is not free -- six other files name that path**, and a
grep-and-replace has to reach all of them, one of which is production
code rather than a test:

| File | What it says |
|---|---|
| `chitragupta/review/verbatim_check.py` | "`tests/test_skill_verbatim_scan_offer.py` holds every skill's offer" -- prose that also has to stop saying *offer* |
| `tests/test_skill_style_check_step.py` | "and for the same reason" |
| `tests/test_skill_book_assembly.py` | "Same shape and same reasoning as" |
| `tests/test_command_depth_scan.py` | cites it for the `encoding="utf-8"` discipline |
| `tests/test_review_entrypoint.py` | same |
| `tests/test_style_assets_match_the_standard.py` | same |

Nothing under `docs/`, `DEVELOPER-AGENTS.md` or `docs/TECHNICAL-DEBT.md`
references it, so the rename does not reach the prose contract or the
debt register. If the rename looks like more churn than it is worth,
keeping the filename and fixing only the docstring is a defensible
second-best -- but then say so, because a file called `..._offer.py`
that asserts a mandatory step is the next reader's trap.

`test_genre_doc_still_speaks_for_every_skill_that_exists` pins the count
at nine and pins the string `"What all nine have in common"` in
`docs/GENRE.md`. Site 13 of the sweep is in that same section, so expect
this test to be the one that notices a half-done edit.

Per [DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md), the failing test comes
first. It is a text scan over `.claude/skills/`, so it is cheap and it
fails for the right reason on the current tree.

## Part 7 -- the measurement, as taken

Issue #312 asks for the roadmap's baseline table before and after. **The table
as published cannot be re-measured**, and forcing it would corrupt the
result: its four drafts have no dossiers, so an "after" run would require
fabricating dossiers for drafts this pipeline never wrote -- and the
roadmap already notes their evidence shape "cannot be verified after the
fact."

What was measured instead, on 2026-08-22, is **tier-3 reach across every
draft on the measuring host** -- all 27 under `content/drafts/`,
read-only, no lock. This is the honest form of the question, because the
skill edits do not change what the command reports on an already-written
draft; they change what happens on the next draft written.

| | Drafts | Deterministic findings | Embedding-tier findings |
|---|---|---|---|
| tier 3 ran | **21** | 519 | **256** |
| tier 3 skipped | **6** | 3 | -- |

**The roadmap's baseline reproduces exactly.** Its four sample drafts
still report `book-chapter` 3, `deep-research` 0, `survey` 9,
`tutorial` 6 -- and all four are in the skipped six, alongside the two
assembled artefacts (`book.md`, `table-of-contents.md`) that have no
dossier of their own. Every one of the 21 drafts with a real dossier ran
all three tiers.

**The number that matters is 256 against 0.** On fourteen of those
twenty-one drafts the deterministic tiers found **nothing at all** while
the embedding tier found between 7 and 21 passages each:

```text
book-chapters/digital-twin-platforms.md                 7 findings, all 7 embedding
books/.../03-anatomy-of-a-twin.md                      13 findings, all 13 embedding
books/.../06-simulators.md                             20 findings, all 20 embedding
book-chapters/digital-twin-life-cycle-considerations…  21 findings, all 21 embedding
```

That is [PLAGIARISM.md](../docs/PLAGIARISM.md)'s claim -- restatement is
"an LLM's default failure mode" and "invisible to both deterministic
tiers by construction" -- reproduced on real output rather than argued.
It is also the sharpest statement of why the precondition matters: had
those drafts' dossiers been missing, the same command would have
reported zero findings and exited 0, and the report would have looked
like an answer. Six drafts on this host are in exactly that state today.

**One draft is worth naming as a counter-example.**
`da/anvendelser-af-digitale-tvillinger.md` reports 408 findings, 404 of
them deterministic. It is a Danish-language draft, and the deterministic
tiers are matching structure that is not restatement. It is the reason
the skills lead with the `long` and `short` buckets and give `quoted` a
count: a mandatory scan is only useful if its output can be read.

## The interaction with #313, being built in parallel

[#313](https://github.com/prasadtalasila/chitragupta/issues/313) (A4, the
Evidence appendix) is in a separate worktree with no PR open yet. It is
**not** a dependency in either direction, and neither item should wait
for the other. But it puts attributed verbatim spans *into the draft*,
and this item makes the scan that reads the draft mandatory -- so the two
meet, and three things follow. None changes the design above; all three
change what the implementer must check.

### 1. Where the appendix sits decides whether it is scanned at all

`verbatim_check._mask_for_scan()` blanks everything from
`references.section_start()` to end of file, because the References
section is generated from bib metadata and scanning it would "flag every
source's own title page as verbatim overlap with itself". Tier 3 inherits
the same exclusion through `_tokenize_draft`'s word stream.

So the placement #313 chooses is load-bearing for this item:

| Appendix placement | What the mandatory scan sees |
|---|---|
| per section, in the body | **scanned** -- every quoted span becomes a finding |
| once at the end, *before* References | **scanned** -- same |
| once at the end, *after* References | **blanked entirely** -- the quarantined quotes are never checked |

The third row is the trap. It is silently the quietest option and it
means a draft's only verbatim material is the one part nothing looks at.
Neither issue mentions the masking; this is the note to carry across.

### 2. The `quoted` bucket stops it being alarming -- if the render fires it

`_bucket` demotes a run that is both quoted **and** cites its source to
the lowest-priority bucket (`BUCKET_ORDER = ("long", "short",
"quoted")`), which is exactly the exemption an Evidence appendix wants.
That exemption keys off `_run_is_quoted`, which reads straight or curly
double-quote delimiters and Markdown blockquote lines, `any` rather than
`all`.

It therefore fires only if #313 renders the span with those delimiters. A
`.tex` appendix using `\begin{quote}` with no quotation marks, or a
Markdown appendix using an indented block, produces runs marked
`quoted: false` -- and every legitimately attributed quotation would then
be reported in the `short` bucket as unmarked reuse. #189 already fixed
one bug of this exact shape (`fix/189-quoted-straddle`), so it is a
demonstrated failure mode rather than a hypothetical.

**The coordination requirement, in one sentence:** #313's rendered quote
must carry real quotation marks or a Markdown blockquote in every output
format, or #312's mandatory scan mis-buckets it.

### 3. Tier 3 will align the appendix with its own sources, by construction

`attribute_citekeys()` joins headings to the citekeys cited under them,
so an `Evidence` heading becomes a `sections.md` row holding every
citekey it lists. Tier 3 then compares that section against exactly those
sources -- and the section *is* spans copied from them. A near-perfect
cosine alignment per quote is the guaranteed result.

That is not a bug in either item, but it means an A4 draft's scan output
is systematically noisier, and the noise is concentrated where it is
least informative. So [Part 5](#part-5----what-a-skill-says-when-tier-3-cannot-run)
gains a fourth obligation:

> **Present the buckets separately.** A skill reporting findings shows
> the `long` and `short` buckets first and the `quoted` bucket as a
> count, not a list. The rationale names alarm fatigue -- not
> correctness -- as this loop's real risk, and a mandatory scan whose
> output is mostly a draft's own attributed quotations is how that risk
> arrives.

Write that obligation now, whether or not #313 lands. It is correct today
for any draft that quotes, and it is what makes the two items compose
instead of collide.

### 4. Decision: this item waits for #313 to merge

**Safe to wait, and better to wait.** Recorded 2026-08-22.

Neither item is a dependency of the other, so waiting costs nothing that
has to be recovered later. What it buys is that the three findings above
stop being predictions:

- the appendix's placement relative to the References heading is a fact
  to read rather than a note to hand over;
- whether `_run_is_quoted` fires on the rendered quote can be **measured**
  by scanning a draft that has one, instead of specified as a
  requirement;
- the fourth obligation in Part 5 can be written against the bucket
  distribution an A4 draft actually produces.

The risk of waiting is bounded and visible: #306 is closed, so #313 is
unblocked, and it has no PR open yet. If it stalls, nothing here depends
on it -- [Part 1](#part-1----the-amendment-sweep) and
[Part 2](#part-2----the-three-diagrams) touch no skill file and could be
taken alone at any point, leaving only the nine skill edits behind #313.

**What waiting does not change:** every finding in this document was
verified against the tree as it stands and none of it is contingent
on #313. Re-run the sweep before implementing regardless -- that advice was
already here for a different reason.

### 5. The mechanical collisions

Both items edit the same nine `SKILL.md` files, both near the tail.
Issue #313 adds an appendix step in the rendering neighbourhood, and this one
rewrites the scan step just after it. Expect a textual conflict and no
semantic one. And both bump `[tool.poetry].version`, which is the
collision `scripts/check_version_bump.py` exists to catch: whichever
merges second re-bumps against the **tags**, not against `main`.

## Order of work

**Start after #313 merges**, per
[the decision above](#4-decision-this-item-waits-for-313-to-merge).

One PR, closing #312. The alternative -- documentation first, skills
second -- was weighed and declined: every PR here bumps
`[tool.poetry].version`, so two PRs on one issue serialise anyway, and
`scripts/check_version_bump.py` has already caught two branches taking
the same number.

1. Take the measurements ([Part 7](#part-7----the-measurement-as-taken)).
   They are read-only and they are stale the moment the skills change.
2. Write the failing test ([Part 6](#part-6----the-test-written-first)).
3. The amendment sweep ([Part 1](#part-1----the-amendment-sweep)),
   including the two riders and the three reconciliation sites.
4. The diagrams ([Part 2](#part-2----the-three-diagrams)) -- fenced block,
   `.mmd`, re-render, in that order, per diagram.
5. The nine skills ([Parts 3](#part-3----the-nine-skills),
   [4](#part-4----the-sectionsmd-precondition) and
   [5](#part-5----what-a-skill-says-when-tier-3-cannot-run)) -- one edit
   shape, applied nine times, so review it once and repeat it exactly.
6. The full local check suite, `mkdocs build --strict` included, then the
   ten-step cycle.

**Version:** `main`'s `pyproject.toml` reads 6.17.0 but tags run to
**v6.17.2**, so this branch takes 6.17.3 or later. Check the tags, not
`main`.

**Impact: MINOR.** No module, CLI argument shape, config key or output
format changes -- but `BANNER` is copied into every written report and
into the JSON envelope's `notice`, so a consumer diffing report text will
see it. That is worth a minor rather than a patch.

## Explicitly not in scope

- **Auto-routing findings into `overlap-reviser`.** Withdrawn as
  [A1b](../docs/FEATURE-ROADMAP.md#a1b-auto-route-findings-into-overlap-reviser----declined),
  and re-declined here.
- **Any hook.** The rationale's §"Why not a PostToolUse hook" holds: the
  objection is not cost, it is that a review report in the path of a
  write is one step from a report that blocks it. The scan runs from a
  skill step, at the end of a run, and nowhere else.
- **[SOUL.md](../SOUL.md).** Not amended, by design.
- **The `agenda` aid and `agenda-reviser`.** Theme F, not this item.
- **`chitragupta/dossier/_acronyms.py`'s never-automatic rule.** A
  drafting-layer rule about a different feature.

## Risks, and what would falsify this plan

- **The sweep's counts are a snapshot.** #341 added four sites in one PR,
  the day before this was written. Whoever implements this re-runs the
  sweep rather than trusting the table above; if the count differs, the
  table is what is wrong.
- **The SVG churn could hide a real error.** Three whole-file diffs that
  are mostly font metrics are exactly where a broken diagram would go
  unnoticed. Open each rendered SVG before committing.
- **The three-tier claim depends on a host.** Every measurement here was
  taken on a host with the enrichment layer installed and the corpus
  embedded. On a host without it, [Part 5](#part-5----what-a-skill-says-when-tier-3-cannot-run)
  is the whole of what the user gets, which is why its three obligations
  are the load-bearing part of this plan and not a footnote.
- **If a skill's scan step is ever made a condition of presenting**, this
  item has become a gate and the amendment did not authorise that. The
  "never make it a condition of presenting" clause is the tripwire; it
  stays in all nine files and in `docs/GENRE.md`.
