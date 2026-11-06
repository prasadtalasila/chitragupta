# ✅ Sign the outline off

Status: **tutorial**, step 2 of [Write a book](../WRITE-A-BOOK.md).

**Written for** the person who decides what the book is. **Assumed:**
an outline that parses ([step 1](OUTLINE.md)). **Not covered here:**
changing an outline someone already signed; that is
[its own workflow](CHANGING-THE-OUTLINE.md).

## ▶ Step 2: sign the outline off

The first of the two human gates. Nothing generates prose from an
unsigned outline, and no command can do this for you:

```bash
chitragupta draft spec sign content/drafts/twins --by "Your Name"
chitragupta draft spec status content/drafts/twins
```

```text
content/specs/twins/spec.md: Composable Twins
  2 parts, 4 chapters, 4 sections
  signed off at digest 7cfc6678f261.
```

**The first `sign` also dates your copyright page.** If
`content/specs/twins/copyright.tex` still holds the `<year>`
placeholder `spec init` put there, `sign` writes the current year over
it and says so, once:

```text
Wrote the year 2026 into content/specs/twins/copyright.tex; change it there by hand from now on.
```

Every later `sign` leaves the file alone: a copyright year is the year
the book was first published, not the year it was last rebuilt. Which
year to print after that is your edit to make
([front matter](FRONT-MATTER.md#-the-copyright-page)).

`sign` records a twelve-hex digest of `spec.md` in a sibling file
([why a sibling](DESIGN-NOTES.md#-why-sign-off-is-a-sibling-file)), so
`status` can tell
three states apart:

| State | Exit | Means |
| --- | --- | --- |
| signed off at digest `x` | 0 | the approved outline is the one on disk |
| not signed off | 1 | nobody has approved this outline yet |
| changed since sign-off | 1 | approved at one digest, now another |

That non-zero exit is not a new gate
([what it is](DESIGN-NOTES.md#-what-statuss-exit-code-is-and-is-not)).

It records **one digest per chapter as well**, and `status` names the
chapters that moved. After a reword of `ch-cost`'s brief:

```text
content/specs/twins/spec.md: Composable Twins
  2 parts, 4 chapters, 4 sections
  changed since sign-off: approved at 7cfc6678f261, now 6246a85473b1.
  chapters changed: ch-cost
```

Recording per chapter keeps a revision to one chapter from freezing the
other fourteen ([why](DESIGN-NOTES.md#-why-sign-off-is-recorded-per-chapter)).

Next: [write and accept the chapters](CHAPTERS.md).
