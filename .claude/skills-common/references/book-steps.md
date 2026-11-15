# Book steps: what composing a book from accepted units involves

Read a section of this file when the step that sent you here cites it;
each section opens with when it applies. Paths here are from the project
root, and `<book>` is the book's directory under `content/drafts/`. The
commands themselves are in the step, never here: this file holds what
they are for and how to judge what they return. `docs/WRITE-A-BOOK.md`
is the track this procedure belongs to, and `docs/book/` its pages.

## 1. The spec and the acceptance records

Read this before the first status check of a run, and again whenever a
unit reads anything but `accepted`.

A book is planned top-down and composed bottom-up. What is planned is
the outline; what is composed is only what a person accepted against
it. Composing reads these, and writes none of them:

- `content/specs/<book>/spec.md`: the outline. Its parts and chapters,
  each under an `{#id}` that names one unit, the reserved parts for
  front matter, appendices and back matter, and the book's `- author:`
  line.
- `content/specs/<book>/signoff.md`: the digest the outline was approved
  at, with one digest per chapter, so a change to one chapter's entry is
  told apart from a change to the whole.
- `content/specs/<book>/units/<unit-id>.json`: one acceptance record per
  unit, written when a person accepted that unit's prose against the
  outline as it then stood, and only once the unit passed the citation
  gate.
- `content/drafts/<book>/<unit-id>.<ext>`: the units, one authored file
  per outline id, each with its own dossier.

The unit status table reads each record against the outline and the
prose as they are now:

| Status | Means | Composable |
| --- | --- | --- |
| `unwritten` | no draft on disk | no: drafting it is a genre skill's job, or the author's (a preface) |
| `drafted` | prose exists, nobody accepted it (also what an unreadable record reads as) | no: acceptance is a person's call, made per unit |
| `accepted` | the record matches both the current outline and the prose | yes |
| `stale: inputs changed` | the outline moved under an accepted unit | no |
| `stale: draft changed since accepted` | the prose moved after acceptance | no |

Report the table as it stands, and say which units are not composable
and why. The reason matters to the user: `stale: inputs changed` means
the outline moved under prose somebody already accepted, which is a
decision for them, not a thing to paper over by composing the old text.
A record whose unit has left the outline is listed after the summary;
it is not composed, and nothing is deleted.

**The record of a book is these files, so composing keeps no dossier.**
A drafting run keeps one because it makes judgement calls (what to
retrieve, what to keep, what to reject and why) that a later revision
has to read. Composing retrieves nothing and decides nothing. The
outline and its sign-off, one acceptance record per unit, and the
registries under `content/specs/<book>/registries/` are the whole
record. There is no acronym step either: there is no prose here to
expand an acronym in, and each unit's own genre skill handled that when
the unit was drafted.

## 2. The two human sign-offs

Read this before the first status check of a run, and again before
presenting what was composed.

A book has exactly two human sign-offs, and neither can be automated.
Everything between them is mechanical.

1. **The outline**, before anything is composed. It covers the book's
   shape: which parts and chapters exist, in what order, under which
   ids, and what each chapter's entry asks for. Its status is zero only
   when the outline on disk is the one a person approved. Non-zero
   means nobody approved this outline, or it changed after somebody
   did, and the per-chapter digests name the chapters that moved.
   Either way, compose nothing: stop and say which. Approving it is the
   user's act, and the signing command is theirs to run.
2. **The book**, after it is composed. It covers what no check reads:
   whether the argument is any good. Every check in this pipeline
   verifies that a book is grounded, consistent and complete, and none
   of them verifies that it is any good. That judgement is the user's,
   deliberately, and there is no command for it.

At the second, present what was composed: how many units, which units
the registries could not read, every registry finding, and what the gate
and the review aids said. Then stop. The book is the user's to call
finished, so do not say it is.

## 3. Checking the registries before composing

Read this before building the registries, and follow it for every
finding they report.

The registries are derived from the accepted units' dossiers: the terms
each unit defines, the claims each makes, the cross-references between
them, and the generated pages a book prints from those (a glossary, a
list of symbols, an index). They are rebuilt on every run, so a unit
revised since the last build is read as it now stands.

**A build that refuses stops the run.** The build exits non-zero on a
glossary bullet or a symbol row it cannot print, and writes neither
page. Stop and report each: the fix is in that unit's own `scope.md` or
`math.md`, through the revision skill the step names, never in the
composed book. An index problem is the author's to fix, in
`content/specs/<book>/index.toml`.

**The check never blocks, and that is why it must be seen.** The
consistency check exits 0 whatever it finds: it is a machine's reading
of prose, and `docs/ARCHITECTURE.md`'s "Layer 4" is why such a check
reports and never blocks. What is guaranteed instead is that it ran and
that its findings were seen. So print every finding to the user, in
full, before composing: a term defined twice, the same claim made in two
chapters, a cross-reference that resolves to nothing. Each is the
user's call, and a finding paraphrased into "a few small issues" has
not been seen. Report the coverage line too: a registry built over
units it could not read is a narrower claim than it looks.

## 4. Composing from accepted units

Read this before writing the composed document.

**Compose only what was accepted, in outline order.** A unit the status
table did not report as `accepted` is not composed in any form: stop,
and say which unit is missing or unaccepted and whose job it is. Never
compose an older text in its place, and never draft the missing one.

**Composing writes no prose.** The only thing written is the document
that holds the units: its preamble, its structure, and one inclusion per
unit. A sentence the book's reader will read belongs to a unit, so
writing one here means the work belongs to a genre skill or to the
author. Likewise, a unit's wording is changed only in that unit, through
the revision skill the step names, and then the unit is accepted again
before it is composed.

**The composed document is output.** It and every converted unit go
under `content/rendered/<book>/`, where a unit's own renders already
land, because renders mirror the draft's path. `content/drafts/<book>/`
holds the units a person wrote and nothing else.

**A unit is found by its path.** Never move or rename a unit's file:
its dossier is found by path alone, and so is its `math.md`, the
mapping its equations render through
(`docs/writing-standards/mathematics.md` §12). Each unit keeps its own
mapping, so two units may map the same ASCII differently and both stay
right; there is no book-level mapping to assemble. A renamed unit loses
its mapping, and every equation in it silently becomes typewriter text.
A math marker with no mapping fails that unit's render outright, which
is the loud half of the same rule.

**The outline's ids carry through unchanged.** Each `{#id}` becomes the
label in the composed document, which is what makes the cross-references
the registry checked resolve in the built book. Never rename one on the
way through.

**An id that is unique in a unit can collide in a book.** A table,
captioned figure or numbered equation is named by an id its unit chose,
and the book numbers them itself. Two units that each chose the same
id produce two labels in one document, and every reference to that id
silently resolves to whichever one was read last. The per-unit prose
check reports a duplicate id within one unit; across units, the check
the step runs before composing is the only one. An uncaptioned figure
marker sharing a name counts too, since it collides the moment its unit
adds a caption (an uncaptioned marker is also a `FigureNoCaption`
finding in its own unit's prose check, so it should not survive this
far). A collision goes back to one of the units through the
revision skill; never rename a label in the composed document.

**The book's author comes from the outline.** Ask the user only if the
outline has no `- author:` line, and never invent one.

## 5. Gating what was composed

Read this before running the gate on the composed document, and before
the per-unit review aids.

**The gate runs on the composed document.** Every unit passed it
already, but the composed document is a new file, and the gate is the
only exit from this layer whatever produced the file. A `FAIL` is a
failing test, not a warning. Never fix one by inventing or altering a
citekey: correct the reference or take the claim out, in the unit it
came from, through the revision skill.

**Never gate a converted unit.** The gate is for the composed document
and for a unit's authored file, which every unit already passed. A
converted unit is render output: its citekeys may be aliased, and an
alias is not a ledger key, so the gate would report a `FAIL` on a book
that is correct.

**The review aids run per unit, never on the composed document.** The
composed document is structure and holds no prose, so the prose check
or the verbatim scan run over it would report nothing and mean nothing.
Run each over every accepted unit. Both are review aids, never a
condition of presenting: a unit with findings is still a composed unit,
and the step reports rather than withholds. Acting on a finding happens
in the unit that owns the wording, and only if the user asks.

**Report the per-unit results as one table.** Fifteen separate reports
is how a real finding gets skimmed past.

**A unit changed after composing** is checked again on its own (the
prose check and the scan, on that unit), accepted again, and the book is
composed again. The composed document is regenerated every time, so an
edit made to it by hand is lost at the next run.
