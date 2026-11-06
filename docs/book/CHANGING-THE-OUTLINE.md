# 🔁 Changing the outline after sign-off

Status: **workflow**, part of [Write a book](../WRITE-A-BOOK.md).

**Written for** an author whose book has outgrown the outline they
signed: a chapter to add, drop, split or move, a preface no longer
wanted. **Assumed:** a signed outline and some accepted units
([steps 2 to 4](SIGN-OFF.md)). **Not covered here:** changing a
chapter's prose, which is `draft-reviser`'s job and needs no outline
change.

The rule is short: **the book is the outline.** Every assembly writes
`book.tex` afresh from the signed outline and the units accepted under
it, so whatever the outline says is what the next build prints, and
nothing else.

## 🧭 The loop

1. **Edit `spec.md`.** Add, remove, rename or move entries.
2. **See what moved.**

   ```bash
   chitragupta draft spec status content/drafts/twins
   ```

   ```text
   content/specs/twins/spec.md: Composable Twins
     2 parts, 4 chapters, 4 sections
     changed since sign-off: approved at 7cfc6678f261, now 6246a85473b1.
     chapters changed: ch-cost
     chapters no longer in the outline: ch-sync
   ```

   Until you re-sign, the assembler refuses to build: an outline nobody
   approved is not one it composes from.
3. **Re-sign.** `chitragupta draft spec sign content/drafts/twins`. Only
   the chapters whose span you edited count as changed
   ([why](DESIGN-NOTES.md#-why-sign-off-is-recorded-per-chapter)), so
   accepted units elsewhere stay accepted.
4. **Write and accept what is new or changed** ([steps 3b and 4](CHAPTERS.md)).
5. **Reassemble and rebuild** ([steps 6 and 7](ASSEMBLE.md)). A PDF
   built before the change stays as it was until you rebuild it.

## ✂ What each change does

| You | The next build | On disk |
| --- | --- | --- |
| add a chapter | includes it once accepted; until then `unit status` shows it `unwritten`, and the assembler reports it rather than composing it | nothing until you write it |
| remove a chapter (or the preface, or a whole part) | leaves it out: no `\input`, no table-of-contents line, nothing in the registries | its prose and acceptance record stay; `unit status` lists them |
| edit a chapter's brief or sections | includes it once re-accepted; until then it is `stale: inputs changed` | unchanged |
| move a chapter to another part | prints it in its new place once re-accepted; until then it is `stale: inputs changed`, because the part above a unit is one of its inputs. Its id, label and every `\cref` to it are unchanged | unchanged |
| reword a chapter's heading | prints the new title once re-accepted (the title is an input too); every `\cref` still resolves, because they follow the id | unchanged |
| add or drop a back-matter page | prints or leaves out that page ([back matter](BACK-MATTER.md)) | nothing: generated pages have no file |
| change the `- author:` line | prints the new name on the title and copyright pages | the whole-book digest moves, no chapter's does |

## 🗂 What a removal leaves behind

Removing an entry never deletes anything. After removing `ch-sync`:

```text
  accepted, but no longer in the outline: ch-sync (records and prose are left on disk)
```

`unit status` prints that line after its summary, and `--json` carries
the ids under `"orphaned"`; neither counts towards its exit code. The
three files left are yours to keep or delete:

| File | What it is |
| --- | --- |
| `content/drafts/twins/ch-sync.md` | the prose you wrote |
| `content/specs/twins/units/ch-sync.json` | the record that you accepted it |
| `content/rendered/twins/ch-sync.tex` | its last conversion; not `\input` any more |

Put the entry back with the same id, in the same part, with the same
title and brief, and the record applies again: if the prose is
unchanged too, the unit is `accepted` with no re-acceptance.

## 🧩 A chapter with no sections

A chapter whose brief is all the outline says about it (no `####`
lines) is a unit by itself, written as `<chapter-id>.md`. Adding two
or more sections to it later, or one with a different title, makes it a
chapter described at section level: still the same unit and file, but
now `spec align` compares its headings against the sections you declared
([why](DESIGN-NOTES.md#-why-a-chapter-is-the-authored-document)).

Adding exactly **one** section that carries the chapter's own title is
the retrofitted shape instead: the *section* becomes the unit, written
as `<section-id>.md`, and the chapter's old record is then listed as
"accepted, but no longer in the outline" although the chapter is still
there. Give that section its own title, or none at all, unless you are
retrofitting ([retrofit](RETROFIT.md)).
