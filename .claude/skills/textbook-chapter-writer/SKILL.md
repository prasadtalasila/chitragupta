---
name: textbook-chapter-writer
description: Drafts an undergraduate textbook chapter -- learning objectives, motivation, worked examples, exercises -- for a student who is studying the topic, not yet doing it. Diataxis-wise this is explanation with worked application, not a tutorial; if the user wants a hands-on lesson the reader follows at a keyboard, use `tutorial-writer` instead. May cite grounding papers from the synced corpus (content/ledger.sqlite via chitragupta.retrieval.search()) for motivation/background, but is not citation-dense; most content is original worked examples and exercises. Triggers when the user asks to draft a textbook chapter, lecture notes, course reader, teaching material, or worked-examples handout for students. To change one that already exists in content/drafts/, use draft-reviser instead -- never re-run this skill to make a change. Any citations it does include must pass `python -m chitragupta.draft gate` before the draft is presented -- never a fabricated citekey.
tags: [textbook, teaching, undergraduate, pedagogy, explanation]
---

# textbook-chapter-writer

Drafts a textbook chapter for a student who is studying the topic:
objectives, motivation, worked examples and exercises, citing the corpus
only where that helps. Paths in this skill are from the project root,
not from this skill's own folder.

## Before you start

**The corpus is read-only: never run `python -m chitragupta.corpus sync`
or `python -m chitragupta.enrich`.** Before the first retrieval, read
`.claude/skills-common/references/genre-steps.md` §1: what the corpus
holds, and why those are the user's to run. Of its two paragraphs on an empty
ledger, the one for a genre where citing is optional is this genre's.
Check:

```bash
python -m chitragupta.corpus ledger
```

If it reports no items, or none `parsed`, say so before you start: the chapter is
still possible, but it will carry no citations. Ask whether to proceed
uncited or to sync first, and wait for the answer.

## When to invoke

A hands-on lesson the reader follows at a keyboard is
`tutorial-writer`'s, a survey or literature review `survey-writer`'s, a
thesis chapter `thesis-chapter-writer`'s, and a change to a chapter in
`content/drafts/` is `draft-reviser`'s: never re-run this skill to make
one. If the request is ambiguous ("write something teaching X"), ask one
question: *will the reader be reading this, or doing it?* Reading is
this skill; doing is `tutorial-writer`. Don't guess.

## Collection scoping

At step 0, before any retrieval, check whether the library is sorted
into collections:

```bash
python -m chitragupta.corpus ledger --collections
```

If it reports none, say nothing, ask nothing, record
`- collection: (whole corpus)` in `scope.md`'s header, and skip this
section. Otherwise read
`.claude/skills-common/references/collection-scoping.md` now and follow
it for the whole run. If retrieval inside the shelf comes back thin, the
honest fix to offer is a whole-corpus pass with `corpus-reviser`, which
is the one skill allowed to widen.

## Prose standards

Follow `docs/WRITING-STANDARDS.md` for the rules every genre shares, and
`docs/writing-standards/genres/textbook-chapter.md` for what a textbook
chapter owes its student: read it before step 0. Read
`.claude/skills-common/references/mathematical-prose.md` now and follow
it: it governs the sentences around every symbol and derivation.

## Process

0. **Name the reader and the scope, and open the dossier.** Before
   creating it, read `.claude/skills-common/references/genre-steps.md`
   §2 and §3: the slug, `scope.md`, the dialect, the acronym vocabulary
   and the fingerprint. Settle `<slug>` with the user, then:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<slug>.md --genre textbook-chapter
   ```

   A chapter that will carry no citations still gets a dossier. Before
   you record anything in `evidence.md` or `rejected.md`, read
   `.claude/skills/textbook-chapter-writer/references/textbook.md` §4.
   Done when `scope.md` records the reader, what they already know, the
   scope, the glossary and `language:`.
1. **Establish the learning objectives** first: 3-5 concrete "students
   will be able to..." statements, each with an observable verb, and
   drop anything in the chapter that serves none of them. Before writing
   them, read
   `.claude/skills/textbook-chapter-writer/references/textbook.md` §1.
   Done when each objective names something an exercise can assess.
2. **State scope and prerequisites** near the top: what the chapter
   covers, what it deliberately doesn't, and what the student is assumed
   to know. Done when the opening says all three.
3. **Motivation: establish the need before the mechanism.** Before
   writing it, read
   `.claude/skills/textbook-chapter-writer/references/textbook.md` §1
   again. First check for an `outline.md`:

   ```bash
   python -m chitragupta.draft dossier outline content/drafts/<slug>.md --check
   ```

   If it passes, read `.claude/skills-common/references/genre-steps.md`
   §4, then run each section's declared queries verbatim; a thin
   section's reformulations are `--origin extended`. Citing stays
   optional, so a `claim:` block is a steer.

   ```bash
   python -m chitragupta.draft retrieve search "<declared query>" --k 15 --collection "<from scope.md>" --origin declared --log content/drafts/<slug>.md
   ```

   Otherwise, if you search the corpus for a motivating example,
   over-fetch:

   ```bash
   python -m chitragupta.draft retrieve search "<topic>" --k 15 --collection "<from scope.md>" --log content/drafts/<slug>.md
   ```

   Pass `--log` on every call. Cite a result as `[@citekey]` only if
   attributing it helps the student. If a search comes up thin, read
   `.claude/skills-common/references/genre-steps.md` §6; before you
   record a kept source, §5. Done when the motivation section answers
   "why would anyone need this", and every query ran with `--log`.
4. **Diversify sources within a section -- the unit here is the section,
   not the paragraph.** Don't write a multi-source paragraph. **A section
   that cites at all spans two or more citekeys, and its consecutive
   paragraphs do not rest on the same single citekey.** Before reusing
   the same citekey a third time within one section, do one more search
   pass for a different paper covering the same point. Where one paper
   genuinely is the only source for a sustained point, say so with
   `<!-- single-source: why -->` on the line above or below, no blank
   line between (`docs/WRITING-STANDARDS.md` §11;
   `python -m chitragupta.review synthesis <draft>` reports the spread
   and the longest single-source run). When a section cites more than
   one paper, read
   `.claude/skills/textbook-chapter-writer/references/textbook.md` §2.
   Done when every citing section meets the floor or carries the marker.
5. **Worked example(s), then faded ones.** Show the reasoning at each
   step, construct the example for the course level, and fade the
   support from fully worked to posed. Before the first one, read
   `.claude/skills/textbook-chapter-writer/references/textbook.md` §3.
   Done when each example shows why, not only what.
6. **Exercises.** Label each one
   `**Exercise N (Objective M, easy|medium|hard).**`, those three grades
   only, and say whether you give solutions or hints. Cut any exercise
   that maps to no objective, and note each cut, and each abandoned
   worked example, as a row in the dossier's `rejected.md`. Before
   writing them, read
   `.claude/skills/textbook-chapter-writer/references/textbook.md` §3.

   A table in the chapter (symbols, units, parameter values) carries a
   caption line under it, `<!-- table: <id> -->` on the line below that,
   and an inline `<!-- tableref: <id> -->` where the prose reads it
   (`docs/writing-standards/tables.md` §13). Done when every exercise
   carries its label and objective.

7. **Add a figure, if a worked example or concept earns one.** A figure
   is a pair of files, `figures/<name>.tex` and `figures/<name>.txt`,
   named by a marker line of its own
   (`docs/writing-standards/figures.md` §10):

   ```html
   <!-- figure: figures/<name> -->
   ```

   Hand the drawing to `figure-drawer` and come back to this step when
   it returns. A figure considered and dropped is a `rejected.md` row.
   What holds even if that skill is never loaded:

   - **A topic directory is required.** If step 0 settled on a flat
     `content/drafts/<slug>.md`, move the draft and its dossier first, or
     drop the figure.
   - **Check for TikZ, and that the figure compiles.** If
     `figure-drawer` was not loaded, run `kpsewhich tikz.sty`: if it
     finds nothing, write the ASCII inline in a fence, no pair and no
     marker, and say so in chat. A figure you keep compiles on its own
     first, with `lualatex`: a malformed one fails the whole pdf render.
   - **No citekey inside either figure file.**
   - **Nothing redrawn from a source.**
   - **The `.txt` form is 7-bit ASCII, and the caption is in the
     draft**, never in a figure file. Never write the word "Figure" or
     a number yourself: the renderer assigns both.
   - **A caption line directly below the marker**, and
     `<!-- figureref: <name> -->` where the prose points at it.

   Every quantity follows `docs/writing-standards/mathematics.md` §12,
   with a row in the dossier's `math.md` and a displayed equation under
   a `<!-- math -->` marker. To number an equation, put
   `<!-- equation: <id> -->` above it and `<!-- equationref: <id> -->` in
   the sentence that names it. Before adding a figure or numbering an
   equation, read `docs/writing-standards/genres/textbook-chapter.md`.
   Done when each figure has both files and a caption, and each numbered
   equation a sentence that refers to it.
8. **Close the loop.** End with a short summary of what the chapter
   established, tied back to its objectives, and where a student who
   wants more goes next, including corpus papers you consulted but did
   not cite inline. Done when every objective is named in it.
9. **Read it once as the student.** Before presenting, reread the draft
   as the reader in `scope.md`, against the checklist in
   `docs/writing-standards/genres/textbook-chapter.md`. Done when every
   problem it found is fixed.
10. **Map the chapter's sections.** Once the draft is saved:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    ```

    A chapter with no citations still gets this map, with empty citekey
    cells. Done when `sections.md` is written.
11. **Critique against the evidence packet, before gating.** Skip this
    entirely if the chapter has no citations at all, as step 12 does.
    Otherwise it runs once the draft is written and before step 12's
    gate. Read the dossier's `evidence.md` -- the `claim:`/`quote:`
    blocks recorded when a source was judged -- against the chapter's
    prose, section by section, and list in priority order up to five
    places where the prose claims more than its `claim:` supports, omits
    a kept `claim:`, or drifts from its wording. One inline judgement
    call: not a subagent dispatch and not a deterministic check.

    Read `.claude/skills-common/references/critique.md` now, before
    listing anything, and follow it with `content/drafts/<slug>.md` as
    `<draft>`; make each edit with `Edit`.
    **This step is not done until the loop the reference describes has
    run**: the baseline, then at most three repairs, each checked and
    logged in the dossier's `revisions.md`. It is never a condition of
    presenting. Come back with the list, each repair kept or reverted,
    the scan's `tiers_not_run` reason if it gave one, and whether the
    declared queries are exhausted; then continue to step 12. Done when
    the loop has returned and every attempt is logged, you have said
    that nothing cleared the bar, or the chapter cites nothing.
12. **Never write a citekey you didn't get from a search result.** If the
    chapter cites anything, save it as `content/drafts/<slug>.md` and
    gate it:

    ```bash
    python -m chitragupta.draft gate content/drafts/<slug>.md
    ```

    Fix and re-run until `OK` before presenting. With no citations at
    all, just save it. Done when it reports `OK`, or the chapter cites
    nothing.
13. **Build the References section.** If the chapter cites anything,
    follow `.claude/skills-common/references/render-and-references.md`
    §1 for `content/drafts/<slug>.md`, including its `--heading` rule if
    the chapter numbers its own headings. Done when `draft references`
    has run, or the chapter cites nothing.
14. **Render tex, pdf and md, then the evidence sidecar.** Follow
    `.claude/skills-common/references/render-and-references.md` §2 and
    §3 for the same draft: tex, pdf and md, then the sidecar in pdf
    only. Expect it to be thin or absent; if it prints
    `no quoted evidence recorded`, or the user asks why there is none,
    read `.claude/skills/textbook-chapter-writer/references/textbook.md`
    §5. Done when each command has run or its warning is reported.
15. **Record any steering.** If the user shaped this chapter in chat
    ("second-years, not first-years", "assume no probability"), append
    it to the dossier's `steering.md`, dated. Done when every in-chat
    instruction is there.
16. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<slug>.md
    ```

    Read `.claude/skills-common/references/prose-check.md` now and follow
    it. If the user wants any finding acted on, that is
    `draft-reviser`'s copy-edit mode, never an edit made here. Read the
    acronym findings rather than skipping them: a student is precisely
    the outsider an unexpanded acronym is a defect for. Done when every
    finding is reported.
17. **Run the verbatim scan.** Before presenting, rebuild the section map
    and scan:

    ```bash
    python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
    python -m chitragupta.review verbatim scan content/drafts/<slug>.md
    ```

    The first command is not optional and not a repeat of step 10. The
    scan matters most in the connective prose between worked examples,
    which cites nothing. **A review aid, not a gate: it is never a
    condition of presenting.** Read
    `.claude/skills-common/references/verbatim-scan.md` now and follow
    it. Repairing a finding is `agenda-reviser`'s job, and only if the
    user asks. Done when the findings are shown.
18. **Stamp the draft fingerprint, then present.** Read
    `.claude/skills-common/references/genre-steps.md` §7 first, then:

    ```bash
    python -m chitragupta.draft dossier stamp content/drafts/<slug>.md
    ```

    Present as that section says, adding what the chapter assumes as
    prior knowledge, what it leaves out, and where a student goes next.
    Changes go through `draft-reviser`, and
    `python -m chitragupta.draft dossier export <slug>` backs a draft and
    its dossier up. Done when the user has the draft.
