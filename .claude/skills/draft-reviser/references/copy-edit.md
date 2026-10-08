# Copy-edit mode: what changes, and where it stops

Read this once you have said you are in copy-edit mode and named the
convention. The numbered steps below are the skill's own loop. Paths here
are from the project root.

What changes, relative to the skill's loop:

| Step | In copy-edit mode |
| --- | --- |
| 1. Locate and read state | Unchanged, and load-bearing. `scope.md`'s `language:` line is the target a dialect pass converts *to*, and `steering.md` may already carry a house-style decision. Skip this and you apply your own default instead of the user's recorded one |
| 2. Check against recorded scope | Not applicable -- wording is not scope |
| 3. Map the change onto sections | Read the whole draft. This is precisely the case step 3's exception exists for, and it is paid for deliberately |
| 4. Decide whether to search | **No, and never.** A copy-edit that needs a retrieval call has stopped being one; see "Where the line is" below |
| 5. Edit in place | Unchanged, and load-bearing for a second reason, which the step that sent you here gives |
| 6. Write the dossier back | `revisions.md`, one entry -- **and `math.md`, if the draft has one.** There is no evidence delta, no new rejection and no moved section to record, but a wording pass is exactly what desyncs a mapping keyed on exact span text: "convert to en-GB" or "fix the grammar" rewrites the sentence around an equation. This is the one thing a copy-edit changes structurally, and step 7's render is what catches it |
| 7. Gate, reference, render | Unchanged. Run the gate even though you changed no citation: that is the point |
| Run the prose check | **Inverted, and this is the one place it inverts.** The findings are this pass's work list rather than a report: the user asked for exactly this class of change. Run it before you start, to scope the pass, and again at the end, to say what is left |

If `scope.md`'s `language:` still says `not settled`, ask which dialect
before converting, and write the answer to that line as part of the pass.
A conversion applied against an unrecorded target is one the next session
cannot repeat or check.

**One `revisions.md` entry for the whole pass**, not one per section, and
it names the convention rather than the sections:

```text
2026-08-14 -- copy-edit: converted to en-GB per scope.md's `language:`
(-ise, -our, -re endings); whole document; no claim, citation, section
order or citekey changed.
```

One entry because the log's later reader wants to know *what convention
now governs this draft*; forty entries reading "converted section 4" do
not answer that. `docs/DRAFT-ITERATION.md` has the shape and why it
carries no evidence delta.

## Where the line is

If the rephrasing wants to change what a sentence claims, add or drop a
citation, or reorder an argument, that is an ordinary revision. Finish the
copy-edit, then say what you found and ask -- never take a substantive
change under cover of a style pass, where it arrives in a diff the user is
reviewing for spelling.

Two things this mode refuses outright:

- **Never change a claim to make a sentence read better.** Hedging that
  carries real uncertainty is information (`docs/WRITING-STANDARDS.md`
  §4), and "X may be a factor" flattened to "X is a factor" is a new claim
  with an old citation behind it.
- **Never touch quoted material, a cited title, a proper noun, or a
  dataset or code identifier.** The recorded dialect governs the draft's
  own prose only (`docs/WRITING-STANDARDS.md` §8), and "organization"
  inside a quoted abstract or a venue's name stays as the source spelled
  it. Nothing downstream catches this one: the citation gate checks
  citekeys, not the words around them.
