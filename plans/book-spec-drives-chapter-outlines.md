# The book spec owns structure; the genre skills own content

Status: **proposed.** Written 2026-08-30.

**Written for** whoever builds the bridge between the book track
(`chitragupta/spec/`, `chitragupta/unit/`) and the dossier track that
actually drafts a book's chapters. It replaces the unimplemented half of
[BOOKS.md](../docs/BOOKS.md)'s step 3.

**Assumed:** [#465](https://github.com/prasadtalasila/chitragupta/issues/465)'s
per-chapter sign-off has landed, so "this chapter is approved" is a
question the spec can already answer without re-approving the book.

**Not covered here:** splitting `spec.md` into per-chapter files (#465's
own remaining follow-on), and the cross-reference graph (#138).

## 🔍 What measurement found

Three facts, each checked against the real
`digital-twins-for-software-engineers` book rather than inferred.

**`unit contract` has no consumer.** It is documented as what a genre
skill generates a unit *from*. No skill reads it: `textbook-chapter-writer`,
`thesis-chapter-writer` and `survey-writer` mention `draft unit contract`
and `draft spec show` zero times each, and `book-assembler` -- the only
skill referencing the book track at all -- runs `registry build/check`,
`spec sign/status` and `unit accept/status`, never `contract`.

**So chapters are drafted through the dossier path.** That is where
`outline.md`'s declared `queries:`, the draft fingerprint and
`retrieve search --y-prev` already live, and a book chapter already gets
all three: `dossier status` on
`content/drafts/books/.../03-anatomy-of-a-twin.md` prints its fingerprint
section today.

**The book track and the drafts have drifted apart.** `unit status`
reports **0 of 15 unit(s) accepted and current**, every one "stale: draft
changed since accepted", while `dossier status` reports the fingerprint
"not recorded" on every chapter. Nothing reconciles them and neither
report mentions the other.

Nothing here is a bug in either track. It is a missing bridge.

## 🧭 The split of responsibilities

| Layer | Owns | Does not own |
| --- | --- | --- |
| `spec` | the **structure** -- which chapters, which sections in each -- the human sign-off on it, and whether the authored chapters still match it | any prose, any retrieval, any revision |
| dossier + the genre skills | the **content** -- briefs, claims, declared queries, retrieval, prose, revision, stamping | what the structure is allowed to be |
| `book-assembler` | assembly and rendering of accepted units | both of the above |

The rule that follows, and the reason this is worth building: **a book is
signed off on its structure, and misalignment between that structure and
what was authored is what withholds the sign-off.**

## ▶ The flow this produces

1. A human writes `spec.md` -- parts, chapters, sections.
2. `spec sign` approves the structure, per chapter (#465).
3. **`spec seed`** (new) writes each chapter's dossier `outline.md` with
   one `##` heading per spec section, and nothing else. Empty briefs.
4. A genre skill drafts each chapter through the ordinary dossier path,
   filling `brief:`/`claim:`/`queries:` and writing prose. Unchanged.
5. **`spec align`** (new) compares each chapter draft's authored headings
   against the spec's sections for that chapter.
6. `unit accept` records acceptance, and refuses a chapter that does not
   align.
7. `registry build/check`, `book-assembler`, render, second sign-off.
   Unchanged.

Steps 3 and 5 are the whole of this plan. Steps 1, 2, 4, 7 already work.

## 🔒 The retrofit constraint, measured

The one real book's spec was retrofitted: it declares **one section per
chapter**, titled identically to the chapter. Its drafts author about
forty headings each -- for the first four chapters, 4 declared sections
against 161 authored headings (one level-1 chapter title, ~15 level-2
sections, ~25 level-3 subsections apiece).

A strict title-match rule would therefore report roughly **225 findings
on a book that is not wrong**, only described at chapter granularity.
That would make the check the first thing anyone turns off.

**So alignment is scoped to chapters the spec actually describes at
section level.** A chapter is *section-described* when its spec declares
two or more sections, or one whose title differs from the chapter's own.
Otherwise `align` reports it as "described at chapter level; nothing to
align" -- no findings, and no refusal in step 6. The retrofitted book
stays silent and usable; a book drafted fresh through the real track is
checked in full.

## 📐 Level mapping

A chapter draft's own `#` is the chapter title and its `###` are detail
below the generation unit. **A spec `####` section maps to a draft `##`
heading**, and only that level participates. `sections()` in
`chitragupta/dossier/_sections.py` already extracts these for Markdown
*and* LaTeX, so `thesis-chapter-writer`'s `.tex` output needs no separate
path.

Matching is on the **normalised title** -- case-folded, whitespace
collapsed, any leading `N.` / `N.M` numbering stripped. Not on `{#id}`:
draft headings carry none, and inventing a mapping would be the derived-id
mistake [BOOKS.md](../docs/BOOKS.md) already refuses. A reworded heading
*is* a misalignment, which is the point; `align` reports a near-miss as a
rename rather than as one missing plus one extra.

## 🧱 The three PRs

**PR 1 -- `spec align`, read-only.** The check, and nothing else. Per
chapter: declared-but-not-authored, authored-but-not-declared, renamed,
reordered. Reports, refuses nothing, exits non-zero on a finding the way
`spec status` already does. Ships with the section-described rule above,
so it is silent on the retrofitted book from day one.

**PR 2 -- `spec seed`.** Writes `outline.md` into each chapter's dossier
from the signed spec, one `##` per section. Refuses an unsigned spec:
seeding from a structure nobody approved is the thing step 2 exists to
prevent. **Never clobbers.** A heading whose `brief:`/`claim:`/`queries:`
a human has filled in is left exactly as it is; a section added to the
spec later is appended. Re-running it on a fully-drafted book is a no-op,
which is what makes it safe to re-run at all.

**PR 3 -- alignment binds, and the docs stop lying.** `unit accept`
refuses a section-described chapter that does not align, for the same
reason it already refuses one whose outline is unsigned -- an existing
precondition on acceptance, not a second gate beside
`python -m chitragupta.draft gate`. `spec status` reports alignment
alongside sign-off. `unit status` cross-reports the dossier fingerprint,
so "stale: draft changed since accepted" stops being the whole story.
BOOKS.md's step 3 is rewritten to describe the flow above, and the
responsibility table lands in it.

PR 3 depends on PR 1. PR 2 is independent of both and can go first or
last.

## ⚠ What this deliberately does not do

**It does not give `spec.md` declared `queries:`.** The field would have
no consumer -- no drafting path reads `spec.md` -- and adding a labelled
part to `input_digest` changes every existing digest (checked:
`445bcf4f1c99` becomes `5d96da75353a`), marking every acceptance record
stale for a feature nothing reads. Chapters declare queries in their own
`outline.md`, which already works.

**It does not merge the two prose digests.** `unit`'s `output_digest`
answers "has this changed since a human *accepted* it"; the dossier
fingerprint answers "has it changed since the sidecars were reconciled".
Same hash, different questions, both legitimate. PR 3 makes each report
mention the other; neither record moves.

**It does not delete `unit contract`.** It stays as the record of what a
unit was accepted against. Only its documented role as a generation input
goes, because nothing ever consumed it.
