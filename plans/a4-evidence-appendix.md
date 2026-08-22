# A4: the evidence sidecar

Status: **built.** Written 2026-08-22, and amended the same day to match
what shipped. Three things landed differently from the design below, and
the text has been corrected rather than left to disagree with the code:

- **`render_evidence()` became `evidence_appendix.emit()`**, and lives in
  the new module rather than in `chitragupta/render_output/__init__.py`.
  `render_output/_paths.py` commits that package to stdlib plus
  `config`/`citation_gate`/`references` so a genre skill can render under
  bare `python`, and says in as many words that this "rules out importing
  `chitragupta/dossier/`". `chitragupta.dossier` turns out to be
  stdlib-only and imports fine under bare `python3`, so the *purpose*
  would have survived -- but putting all sidecar knowledge in one module
  keeps the documented contract intact instead of quietly widening it.
- **`render` does not auto-emit a sidecar.** The file table below listed
  `render_output/_cli.py` as calling it after `render()`; neither
  `render_output` file was touched in the end. Leaving it an explicit
  `draft evidence` call keeps `render()`'s single-`Path` return and its
  printed output exactly as they were, keeps `chitragupta/dossier` out of
  the render path entirely, and matches A2's rule that a quote is a
  deliberate act rather than a residue. **The cost is that the five genre
  skills are what make the feature reachable at all** -- see "Files".
- **`_strip_sidecar_suffix` imports `evidence_appendix` lazily.** At
  module scope it is a genuine cycle: `evidence_appendix` reads the
  dossier, so `chitragupta/dossier/__init__.py` -> `_archive` ->
  `evidence_appendix` -> `chitragupta.dossier` fails on a partially
  initialised package.

Implements
[docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s A4 and closes
[#313](https://github.com/prasadtalasila/chitragupta/issues/313).
Depends on A2 ([`a2-claim-quote-split.md`](a2-claim-quote-split.md), issue
306), whose `quote:` field is the only material this reads.

**Written for** whoever builds it. **Assumed:**
[docs/DRAFT-ITERATION.md](../docs/DRAFT-ITERATION.md) for the dossier and
the `claim:`/`quote:` contract, and
[docs/CLI.md](../docs/CLI.md#python--m-chitraguptadraft-render) for where
a render lands. **Not covered here:** why quarantining verbatim material
reduces reuse -- that argument is the roadmap's, and this plan does not
restate it. Nor is verifying that a quoted span really appears at the
cited page: that is the roadmap's C3.

## The problem in one line

A2 gave source wording a place to be *recorded*; it has nowhere to be
*shown*, so the only place a warranted quotation can appear is loose in
body prose.

## What this builds, and how it departs from the issue

A separate, standalone **evidence sidecar** rendered beside the draft --
`content/rendered/<topic>/survey.evidence.pdf` next to
`content/rendered/<topic>/survey.pdf` -- rather than an `Evidence`
appendix spliced into the draft itself.

The issue and the roadmap both describe the appendix as living *inside*
the document. This plan does not, and the reversal is deliberate. Both
readings of "quarantine" were put in front of the human who owns the
decision, with the arguments below, and the sidecar was chosen.

**What the in-document appendix had going for it, recorded so the choice
is legible.** `citation_gate.run()` checks *documents*
(`chitragupta/citation_gate.py:198`), so the issue's acceptance criterion
-- "the gate still sees every citekey in the appendix as a real one" --
holds by construction only when the appendix is in the draft source.
And an appendix in the document is a place a drafter can *point at*,
which is what makes quarantine a mechanism rather than a request.

**Why the sidecar wins anyway.**

- **The tracked-examples problem, which the issue does not state.**
  `content/dossiers/` is gitignored *specifically because* `evidence.md`
  quotes copyrighted sources ([docs/DRAFT-ITERATION.md](../docs/DRAFT-ITERATION.md),
  "Nothing under `content/dossiers/` is tracked"). But
  `content/drafts/digital-twins-for-software-engineers/*.md` and the
  twelve files under `content/rendered/digital-twins-for-software-engineers/`
  **are** tracked -- `.gitignore` negates them explicitly. An appendix
  inside the draft would commit quoted spans from copyrighted PDFs to a
  public repository. A sidecar can be ignored by pattern; a section
  inside a tracked draft cannot.
- **The gate criterion survives as a stronger property.** See
  "Two structural preconditions" below: the sidecar cannot introduce a
  citekey, and contributes zero citations to anything. That is not a
  check that must be run -- it is a shape that cannot be otherwise.
- **It dissolves the issue's one expected decline.**
  `thesis-chapter-writer` was expected to refuse A4 because its `.tex`
  fragment is `\input` into someone else's thesis with no preamble of its
  own, so an appendix spliced into it lands mid-chapter under a heading
  level that document never chose. A sidecar is never `\input`. It is a
  standalone document this project controls end to end, and `render()`
  already passes `documentclass`/`fontsize`/`papersize`/`geometry` for
  exactly that case. The genre most in need of an auditable evidence
  file -- its reader is an examiner reading adversarially -- therefore
  gets one. **The issue asked for a decline to be recorded rather than
  left as an oversight; this is that record, with the opposite answer.**

**What is lost, stated plainly.** In the document, an appendix is a place
the drafter can be told to put a quotation. In a sidecar it is a place
the *reader* finds one. A drafter who genuinely wants a quotation inline
still puts it inline, in quotation marks with an attribution, which A2
already permits. So this softens A4 from "the body has nowhere to leak
to" toward "the evidence base is visible to the reader". A2 remains the
mechanism; A4 is now the display.

## The contract

### What is printed

Only a `quote:` field. Never `support:`, and never `claim:`.

**This deliberately narrows a documented rule, and the narrowing is the
most load-bearing line in this plan.**
[docs/DRAFT-ITERATION.md](../docs/DRAFT-ITERATION.md) says a *skill*
meeting a `support:`-only block "reads it as `quote:` -- the conservative
reading", and `draft-reviser` and `corpus-reviser` both state it as their
own behaviour. That is right for a drafter deciding whether it *may
quote from* a block. It is wrong for a builder that *will print* one:
a legacy `support:` holds a raw 600-character retrieval window
(`EVIDENCE_CHARS` in `chitragupta/retrieval.py`), and printing it as a
"quoted, attributed span" in a rendered PDF is the copyright failure this
whole feature exists to avoid.

`claim:` is excluded for the opposite reason: it is the drafter's own
words, so quoting it back attributes the project's prose to the source.

### Shape

```markdown
# Evidence

Generated by `python -m chitragupta.draft evidence` from the draft's own
dossier. Quoted spans are verbatim from the source named above them.

## Approaches to model synchronisation

### J. Doe and R. Roe, "Title," *IEEE Trans. Testing*, vol. 1, pp. 1-10, 2021. `doe_title_2021`

> "the verbatim span, exactly as `quote:` holds it"
```

- Sections, and their order, come from
  `dossier.citekeys_by_section()` -- row order, because that is the order
  the run itself chose.
- A citekey the draft cites but `sections.md` files nowhere goes under a
  final `## Unassigned`. This mirrors `dossier sections --citekeys`,
  which already reports an unfiled key rather than putting it under a
  section that does not contain it.
- A section whose citekeys all lack a `quote:` is omitted entirely. No
  empty stanza, and no empty heading above one.
- The attribution line is built by **reusing**
  `references.format_entry()`, not by a second formatter. One IEEE
  entry format in this codebase, not two.

### Two structural preconditions, neither of them a new check

The issue forbids promoting a new check into a gate. Both properties it
asks for are therefore shapes, not tests:

1. **The sidecar cannot introduce a citekey.** Its universe is
   `references.used_citekeys(draft_text)`. A citekey present in the
   dossier but not cited by the draft is dropped. This is `references.py`'s
   own rule -- "can never introduce a citekey that hasn't already passed
   the gate" -- inherited rather than restated.
2. **The sidecar contributes zero citations.** Citekeys appear only
   inside code spans, which `citation_gate._blank_code` blanks before
   extraction. So running the gate over a sidecar reports
   `0 citations ... OK`, and the sidecar's existence cannot perturb the
   body's first-appearance citation numbering -- the property
   `references.numbered_markdown` and pandoc's citeproc both depend on.

### Nothing to say means no file

No dossier, no `evidence.md`, or no `quote:` field anywhere in it ->
`build()` returns `None`, nothing is written, and the CLI exits 0 with a
message rather than an error.

This is how a genre "declines": not a switch, but the absence of
deliberate quotes. `tutorial-writer` cites only in "Where to go next" and
captures no `quote:`, so it emits nothing without anyone configuring
anything.

## Decisions this plan settles

**Why not put the sidecar in the dossier?** Because the material is
already there -- `content/dossiers/<path>/evidence.md` holds every
`quote:` today. A rendered copy under `content/dossiers/` would be a
third representation of spans that `evidence.md` holds and
`provenance.json` audits, readable by nobody the first two do not
already serve. The sidecar exists to be *handed to a reader alongside the
draft*, which is a rendering job, so it lands in `content/rendered/`
where every other rendering job lands.

**Why not stamp the sidecar with the draft's digest?** Because it is a
render output, and every render output in this project is stale until
re-rendered. `survey.pdf` carries no digest either. Adding one to the
sidecar alone would introduce a class of state -- and a staleness report
to maintain -- for a property the artefacts beside it do not claim.
A sidecar is regenerated whole on every render, never patched.

**Why match the render format rather than always emitting Markdown?**
Because the sidecar is a peer of the render, not a note about it.
Someone who asked for a PDF to hand to a reviewer needs an evidence file
they can hand over with it.

**Why group by section rather than list flat by citekey?** It is the
shape the roadmap read off the sample ("each section ends with an
`Evidence` block"), it lets a reader match evidence to the part of the
draft leaning on it, and `citekeys_by_section()` already exists and is
already derived from the draft. **Accepted risk:** a `sections.md` that
disagrees with the draft groups a key under the wrong heading. The
grouping is cosmetic -- the attribution and the quote stay correct -- and
`dossier sections --citekeys --write` is the existing fix.

**Why a separate `render_evidence()` rather than making `render()` emit
both?** `render()` returns a single `Path`, and
`chitragupta/review/__init__.py` renders review reports through it.
Changing that return type to accommodate a second output would ripple
into a caller that will never want a sidecar. A sibling function, called
by `_cli.py` after `render()`, leaves `render()`'s contract untouched.

**Why a new module rather than more of `references.py`?**
[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md)'s C2 caps a module at
250 lines of code, and `references.py` is already substantial. The two
also have different jobs: one builds a bibliography *into* a draft, the
other builds a standalone document *beside* it. They share
`format_entry()` and `used_citekeys()`, which is the right amount of
coupling.

**No migration.** Nothing on disk changes shape. A dossier written before
this lands works unchanged: blocks with a `quote:` are rendered, blocks
without one are skipped, and `support:`-only blocks are skipped -- which
is the point, not a gap.

## Files

| File | Change |
|---|---|
| `chitragupta/evidence_appendix.py` | **new.** Stdlib-only, sibling of `references.py`. `build(draft_text, dossier, con) -> str \| None`, plus the writer |
| `chitragupta/dossier/_evidence_check.py` | promote `_fields()` to public `fields()`. It already parses exactly `claim`/`quote`/`relevance`/`support` -- the new module reuses it rather than adding a second parser for the same file |
| ~~`chitragupta/render_output/__init__.py`~~ | **not touched.** `emit()` lives in the new module instead -- see the amendment at the top |
| ~~`chitragupta/render_output/_cli.py`~~ | **not touched.** `render` does not auto-emit |
| `chitragupta/draft.py` | new `evidence` verb in `VERBS` |
| `chitragupta/dossier/_archive.py` | `_match_target` must strip the `.evidence` suffix for the `rendered` label -- see below |
| `.gitignore` | `content/rendered/**/*.evidence.*` |
| `.claude/skills/survey-writer/SKILL.md` | emit, after `gate` passes |
| `.claude/skills/deep-research/SKILL.md` | emit, after `gate` passes |
| `.claude/skills/thesis-chapter-writer/SKILL.md` | emit; record the reversal of the expected decline and why |
| `.claude/skills/textbook-chapter-writer/SKILL.md` | emit; note it will usually be thin, by design |
| `.claude/skills/tutorial-writer/SKILL.md` | record that it emits nothing in practice, and why that is the answer rather than an oversight |
| `docs/DRAFT-ITERATION.md` | the `support:` narrowing: *may quote from* (drafter, permissive) vs *will print* (this builder, strict) |
| `docs/CLI.md` | the `evidence` verb |
| `docs/GENRE.md` | the five genres' recorded answers |
| `docs/FEATURE-ROADMAP.md` | A4: sidecar not in-document, and thesis in rather than out |

### The `_archive.py` finding

`dossier export --with-rendered` walks the filesystem (`_root_members`
uses `root.rglob("*")`), so `.gitignore` does not hide a sidecar from an
export. But `_matches` compares `relative.with_suffix("")`, so
`rendered/topic/survey.evidence.md` reduces to `topic/survey.evidence`,
which does not match a draft **named** `topic/survey`. A named export
would silently drop the evidence from an archive whose whole purpose is
to be the complete record.

The fix already exists in that file for the same reason: `_match_target`
runs `_strip_aid_suffix` for the `review` label, precisely because
`survey.provenance.md` had this problem first. Extend the same treatment
to `rendered`.

## Tests

Failing first, to the 100% bar
([DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md)).

1. A `quote:` reaches the sidecar, inside quotation marks, under its own
   attribution line.
2. A block with `relevance:`/`claim:` and no `quote:` produces no
   stanza.
3. **A legacy `support:`-only block produces no quoted text.** The
   copyright guard, and the one test that must never be relaxed.
4. `claim:` is never printed.
5. A citekey in the dossier but not cited by the draft is dropped.
6. No dossier / no `quote:` anywhere -> returns `None`, writes no file,
   exits 0.
7. A section whose citekeys all lack a quote is omitted, heading and all.
8. A cited citekey filed under no section lands under `Unassigned`.
9. `citation_gate.check_document()` over a sidecar reports 0 citations.
10. `references.used_citekeys()` over the draft is unchanged by the
    sidecar's existence -- body numbering unperturbed.
11. A **named** `dossier export --with-rendered` includes the sidecar
    (regression for the `_archive.py` finding).
12. `git check-ignore` returns 0 for the path `render_evidence()`
    actually chose, under the whitelisted example topic. Asserting
    against the chosen path rather than a hardcoded string is the point:
    it couples the ignore pattern to the naming convention, so renaming
    `.evidence.md` fails this test.
13. A thesis `.tex` fragment produces a standalone sidecar, carrying its
    own `\documentclass` and no `\bibliography` (pandoc-gated).
14. A missing pandoc and a failing pandoc are each reported as
    `[missing-binary]`/`[error]` rather than raised, and the Markdown
    sidecar survives a failed pdf render. Added after an end-to-end smoke
    run produced a traceback: a non-`md` sidecar goes through pandoc, so
    it fails the ways a render fails, and every genre skill is documented
    to warn on those two prefixes and carry on presenting the draft. A
    traceback is not something that instruction can act on.

## Known risks, accepted

**A stale `sections.md`** groups a key under the wrong heading. Grouping
is cosmetic -- the attribution and the quote stay correct -- and
`dossier sections --citekeys --write` is the existing fix.

**A verbatim scan pointed at a sidecar would report nothing but
findings**, and every one of them would be false.
`chitragupta/references.py`'s own comment records what this looks like:
scanning a reference list against the corpus produced 97.7% of all
findings on this project's 15-chapter book, "none of them reuse". A
sidecar is the worse case, because its entire content is deliberate
verbatim source wording.

It is safe today, and the reason is worth writing down rather than
assuming: **`review verbatim scan` takes one explicit draft path**
(`p_scan.add_argument("draft", ...)`), never a walk of `content/`.
Nothing points it at `content/rendered/`, so no `*.evidence.*` skip was
added -- a skip in a scanner that cannot reach the file would be dead
code claiming to prevent something. If that command ever grows a
directory-walking mode, this is the first file it must exclude.

**The release archive cannot ship a sidecar**, and by a stronger
mechanism than the `.gitignore` rule alone. `scripts/release.py` builds
its file list from `git ls-files`, not from a filesystem walk -- so an
ignored file is unreachable to it by construction, and no
`EXCLUDE_TOP_LEVEL` entry is needed. Worth stating because the
neighbouring `_archive.py` does the opposite (`root.rglob("*")`, which is
why a sidecar *is* correctly included in a `dossier export`), and the two
are easy to assume alike. If `release.py` ever changes to a walk,
`content/` becomes the first thing it must exclude.

**`emit(draft, "pdf")` deliberately leaves the `.md` beside the `.pdf`.**
Rendering a *draft* to pdf leaves no Markdown copy, so this differs on
purpose: the Markdown is the sidecar's own source, the only diffable form
of it, and what `dossier export` most usefully archives. Both are ignored
by git and both match the draft on export, so keeping it costs nothing.
A choice, not a leak.

## Done when

A `survey-writer` run over a dossier carrying `quote:` fields renders
`survey.pdf` and `survey.evidence.pdf` side by side; the draft itself
contains no verbatim span; `python -m chitragupta.draft gate` over both
reports `OK` with the sidecar contributing zero citations; a dossier
carrying only legacy `support:` blocks renders no sidecar at all; and
each of the five genre skills states its own answer in its own
`SKILL.md`, the two that emit nothing included.

**Verified end to end** on a throwaway `CONTENT_DIR`, over a two-source
draft whose dossier carried one `quote:` block and one legacy
`support:`-only block:

- the `quote:` reached `survey.evidence.pdf`, attributed and in quotation
  marks;
- the `support:` window appeared **nowhere** in the rendered PDF, and its
  `sections.md` section vanished with it rather than leaving an empty
  heading behind;
- `draft gate` over the sidecar reported `0 citation(s)`;
- deleting `evidence.md` produced `no quoted evidence recorded` and
  exit 0, writing nothing.
