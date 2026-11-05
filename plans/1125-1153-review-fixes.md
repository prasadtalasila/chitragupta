# Review reports: private-use characters and outdated passages

Status: **planned.** Written 2026-11-05, for
[issue 1125](https://github.com/prasadtalasila/chitragupta/issues/1125)
and [issue 1153](https://github.com/prasadtalasila/chitragupta/issues/1153).
The same pull request closes
[issue 1156](https://github.com/prasadtalasila/chitragupta/issues/1156),
which needs no code: f0d6238 (PR 1151) already moved
`test_biggest_document_is_submitted_first` to record order at `submit`.
[Issue 1124](https://github.com/prasadtalasila/chitragupta/issues/1124)
was planned alongside these and closed as not planned: no shipped
workflow writes YAML front matter into a draft.

**Written for** whoever builds it. **It assumes**
`docs/ARCHITECTURE.md`'s review layer and the passage ladder in
`chitragupta/passages.py`'s docstring.

**Not covered here:** characters outside the private-use ranges that no
font in the chain has. Knowing that needs the fonts' coverage, which
Python does not have; LuaLaTeX still stops on one, as it does today.
`passages.structural_passages` called on its own (`_abstract.py`) takes
no ledger connection and is left as it is.

## 1125: a private-use character stops a report's PDF

PDF text layers carry private-use code points (U+E000-U+F8FF, planes 15
and 16) for font-specific glyphs. A review report quotes them from
`content/parsed/`, LuaLaTeX stops on them (`\tracinglostchars=3`), and
`review.write` skips the PDF. The author cannot fix a character that
came from the source.

Decision (user, 2026-11-05): every such character is written as a
visible `[U+E230]` in the report's `.md`, and so in its `.tex` and
`.pdf`. The `.json` keeps the original code point. Drafts keep today's
strict behaviour.

- New `chitragupta/_private_use.py`, stdlib only: `mark(text)` returns
  the text with each private-use character replaced by `[U+XXXX]`, and
  the sorted set of code points it replaced.
- `review.write` marks `body` before writing the `.md`, so all eleven
  aids get it from one place, and prints one note to stderr naming the
  code points.
- `evidence_appendix.write` does the same to the sidecar text, which
  quotes dossier spans copied from the same parsed text.

## 1153: passages from a row that is not `parsed`

`passages.source_passages` reads rungs 1 and 2 (the passage sidecars)
before it looks at the ledger, and then reads `parsed_path`/`pdf_path`
whatever the row's `status`. A row that went `parse_failed` or `no_pdf`
after a corpus change keeps the old parse's sidecar and text, and the
review aids quote it as the paper's current wording. A key removed from
the `.bib` has no row, but its sidecars stay on disk and are still read.

- The ledger row is read first, with `status`. No row gives
  `not found in the corpus`, without the old `run corpus sync` advice,
  since a sync is what removes such a key and the key may never have
  been real. A row whose status is not `parsed` gives
  `status is <status> -- no current parsed text`. Neither reads a
  sidecar, the parsed text or the PDF. This is `retrieval._full_text`'s
  rule (#490).
- Tests: `parse_failed` after a parse, with a sidecar and parsed text on
  disk, yields no passages; a sidecar for a key with no row yields none.

## Version

MINOR: a new `chitragupta/` module, which DEVELOPER-AGENTS.md's
versioning rules class as MINOR, though the change is two bug fixes.
