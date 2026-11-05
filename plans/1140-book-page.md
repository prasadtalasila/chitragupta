# X-1, X-3, X-5 (reduced): the book's page, measured once and checked against

Status: **built** in
[PR 1155](https://github.com/prasadtalasila/chitragupta/pull/1155),
2026-11-05. Written 2026-11-05, for
[epic 1140](https://github.com/prasadtalasila/chitragupta/issues/1140),
items X-1, X-3 and X-5 in their reduced form. X-2, X-4, X-6, X-7 and X-8
are parked on the epic.

**Written for** whoever builds the one PR that closes the three reduced
items. **It assumes** `docs/FIGURE-ROADMAP.md` Part X for the full
output-targets design this is a slice of,
`.claude/skills/book-assembler/references/latex-conventions.md`
("Margins") for why the book has 80pt margins, and
`docs/figure-checks/size.md` for what `size-width` and `size-height`
report.

**Not covered here:**

- **No output targets.** No config key, no target table, no `--target`
  on `draft render`, nothing that lets a project print at A5 or A6.
  There are exactly two pages, the article and the book, because those
  are the two this repository already sets.
- **No change to how type is measured.** The probe sets a figure's
  labels in a 12pt `article` (`review/figure_layout/_probe.py`) and
  `type-below-floor` measures against 12pt (`figure/_house.py`). A book
  sets its body at 10.95pt, so both are slightly off for a book figure.
  That is a known, separate gap, left out by the user's decision; the
  probe and `FLOOR_PT` do not move here.

## The problem, measured

`figure check` measures every figure against one page: `article`, 12pt,
A4, 1in margins. `book-assembler` sets a book on another one: `book`,
11pt, A4, 80pt margins. Measured with LuaLaTeX (`\the\textwidth`,
`\the\textheight`) on this host, 2026-11-05:

| Page | Preamble | Text width | Text height |
| --- | --- | --- | --- |
| article | `\documentclass[12pt,a4paper]{article}` + `\usepackage[margin=1in]{geometry}` | 452.9679pt | 700.50687pt |
| book | `\documentclass[11pt,a4paper]{book}` + `\usepackage[a4paper,margin=80pt]{geometry}` | 437.50787pt | 685.04684pt |

So a book unit's figure between 437.5pt and 453pt wide passes
`size-width` and then does not fit the book, and `size-height` reports
its share of a page 15pt taller than the one it prints on. Nothing
reports the first; the second is advisory.

The two pages are written down separately in six places: the
`render_output/__init__.py` and `_cli.py` defaults, `figure/_check.py`'s
`DEFAULT_WIDTH_PT`, `figure/_advisory.py`'s `TEXT_HEIGHT_PT`,
`figure/_look.py`'s document, and `book-skeleton.tex` for the book; and
the one test that ties two of them
(`tests/test_figure_check.py::TestDefaultWidth`) does so by arithmetic,
which would not notice a class or geometry change that moved the real
`\textwidth`. That is how the book's page went unchecked.

## Design

### 1. `chitragupta/page.py`: the two pages, as data (X-1 reduced)

A frozen dataclass `Page` with:

| Field | article | book |
| --- | --- | --- |
| `name` | `"article"` | `"book"` |
| `documentclass` | `"article"` | `"book"` |
| `fontsize` | `"12pt"` | `"11pt"` |
| `papersize` | `"a4"` | `"a4"` |
| `margin` | `"1in"` | `"80pt"` |
| `preamble` | the two lines `figure look` writes today, verbatim | the two lines `book-skeleton.tex` carries, verbatim (without its trailing comments) |
| `text_width_pt` | `452.97` | `437.51` |
| `text_height_pt` | `700.51` | `685.05` |

`ARTICLE` and `BOOK` are the module's two instances, and `PAGES` maps
name to page for the CLI's `choices`.

**Measured values, not formulas.** The text block is decided by the
class and the geometry options together, so it is recorded as what
LuaLaTeX reports, to two decimals, and a test pins it (below). This is
the epic's own "Alternatives considered" rule.

**Article output, before and after.** `DEFAULT_WIDTH_PT` was `453.0`
and becomes `452.97`; `TEXT_HEIGHT_PT` was `700.0` and becomes
`700.51`. The text report prints the target `.1f`, so `target 453.0pt`
is unchanged, but the pass/fail line does move: with `_HFUZZ_PT` of
0.1pt the limit was 453.10pt and becomes 453.07pt, so an article
figure between 453.07pt and 453.10pt wide now reports `size-width`.
The PR says so plainly. (`tests/test_figure_check.py`'s 453.09pt case
passes its own `width_pt=453.0`, so it does not move.) The height share
prints `.2f` and moves
only where a figure sits within 0.005 of a rounding boundary. `--json`'s
`width_pt` reads `452.97` where it read `453.0`. Those are the only
article-side output changes; the PR lists them, and the docs' example
report lines are re-run rather than assumed.

*Alternative kept open for review:* keep the article's recorded values
at exactly 453.0 / 700.0 and let the test allow 0.1pt. Rejected in this
plan because a value that disagrees with its own measurement is the
drift this PR is removing; reviewers may overrule.

`page_for(figure: Path) -> tuple[Page, str]` answers which page a
figure prints on, and why, in words the report prints:

- Resolve `figure` and `config.DRAFTS_DIR` both, as `spec.spec_dir`
  does. If the figure is not under the drafts directory, it is
  `ARTICLE`, "not under content/drafts/".
- Otherwise walk its ancestors from its own directory up to (not
  including) `DRAFTS_DIR`. The first ancestor `d` for which
  `config.SPECS_DIR / d.relative_to(DRAFTS_DIR) / spec.SPEC_MD` is a
  file makes it `BOOK`, with that spec path as the reason.
- No such ancestor: `ARTICLE`, "no book spec above it".

A book's units are files, `content/drafts/<book>/<unit-id>.md`, and
their figures sit at `content/drafts/<book>/figures/<name>.tex`
(`docs/WRITE-A-BOOK.md`, `docs/CLI.md`), so the walk finds the spec one
level up. There is no false positive, since only books have specs. The
one accepted mismatch is a book unit rendered standalone: its figures
are still checked against the book, the narrower page, and the report's
reason names the spec so the reader can see why.

It reads nothing from the spec beyond its existence, and never calls
`spec.spec_dir` (which raises outside `DRAFTS_DIR`). A spec reached
through a symlink out of `SPECS_DIR` is not followed: the existence
check goes through `config.resolves_inside`, so a planted symlink
cannot turn the book page on, matching `spec_dir`'s own refusal.

The module lives at the top of `chitragupta/` beside `render_output`
because three layers read it: the render defaults, the figure review
aids and (in tests) the book skeleton. **It imports `config` only.**
Importing `chitragupta.spec` at module level would close a cycle:
`spec/__init__.py` → `dossier._sections` → `dossier._draft_fingerprint`
→ `render_output`, which itself imports `page`. So `page.py` holds its
own `SPEC_MD = "spec.md"`, and a test asserts it equals
`spec.SPEC_MD`; another imports `chitragupta.render_output` in a fresh
interpreter so a reintroduced cycle fails a non-slow test.

### 2. Render defaults read `ARTICLE` (X-1 reduced)

`render()`'s signature defaults and `draft render`'s argparse defaults
become `page.ARTICLE.documentclass` and so on. The values are
unchanged, so `draft render` output is byte-identical.
`render_output/__init__.py` is at 250 code lines, the C2 ceiling, so
the import has to replace a line rather than add one, or a docstring
sentence has to move into a `#` comment (the standard's own sanction);
the PR says which.

### 3. `figure check` picks the page (X-3, X-5 reduced)

- `DEFAULT_WIDTH_PT` and `TEXT_HEIGHT_PT` are deleted. `advise()`
  takes the text height as a keyword-only `height_pt`. `advise()` is
  called from `apply()`, not `check()`, so both `check()` and `apply()`
  gain a keyword `height_pt` defaulting to
  `page.ARTICLE.text_height_pt` and pass it through; the 15-odd tests
  that call `apply()` positionally keep their shape. That is about four
  of `_check.py`'s six lines of headroom.
- New `--page {article,book}`. Default: `page_for(figure)`.
- `--width PT` keeps its meaning and overrides the width alone; its
  default becomes "the page's text width". Height always comes from the
  page.
- The text report gains one first line under the path:
  `page     book (437.5pt x 685.0pt), from content/specs/<book>/spec.md`,
  or `page     article (453.0pt x 700.5pt), not under content/drafts/`,
  or `... , --page` when the flag chose it. `--width` adds
  `, width from --width`. `--json` gains a `page` object
  (`name`, `text_width_pt`, `text_height_pt`, `why`). Adding a key and
  a line is backward compatible: no existing key changes meaning.

`figure/_check.py` has 6 code lines of headroom; the page resolution and
the report line live in `__main__.py` and `_check_report.py`, so
`_check.py` loses `DEFAULT_WIDTH_PT` and gains `height_pt` on `check()` and `apply()`.

### 4. `figure look` previews on the figure's page (X-5 reduced)

**A figure has one page everywhere.** `look(figure, out_dir=None,
page=None)` uses `page_for(figure)` when `page` is not given, and every
caller (`figure look`, `figure look --draft`, and `draft render`'s look
step through `_look_draft.refresh`) leaves it to that. One `<stem>.look.*`
record per figure therefore always holds one page, so alternating
`figure look` and `draft render` does not rebuild it each time. The
page PNG that `--draft` and `draft render` add is still the standalone
render's own page, and is labelled as such already.

`look` sets the figure on that page: `document(source, page)` writes
`page.preamble` in place of today's two literal lines. Its hairline and
`text width` line already read `\textwidth` from the compile, so they
follow with no other change.

`page.preamble` joins the look's digest, so a look built on one page
is never reported `current` for the other. That changes every existing
article digest once, which rebuilds each look on its next run; the
look's files are regenerated, not edited, so this costs one LuaLaTeX run
per figure and nothing else. `DOCUMENT_VERSION` does not also need
raising: the preamble bytes already change every digest.

### 5. The book skeleton is held to `BOOK` (X-5 reduced)

`book-skeleton.tex` stays a plain template the skill copies. A test
asserts both lines of `BOOK.preamble` appear in it verbatim, so the
skeleton and the checks cannot part again without a red test.
`latex-conventions.md`'s "Margins" paragraph gains one sentence: the
text block those margins leave (437.5pt by 685.0pt), and that
`figure check` measures a book unit's figures against it.

## Tests

Written first, each red before its fix:

1. `tests/test_page.py`
   - **(slow)** For each page, compile `page.preamble` with LuaLaTeX,
     read `\the\textwidth` / `\the\textheight`, and assert the recorded
     values to 0.01pt. Replaces `TestDefaultWidth`'s arithmetic.
   - `render()`'s and `draft render`'s defaults equal `ARTICLE`'s fields.
   - `BOOK.preamble`'s lines are in `book-skeleton.tex`.
   - `page_for`: outside drafts; under drafts with no spec; a book unit
     figure (`drafts/b/figures/f.tex` with `specs/b/spec.md`); a
     nested book; a spec directory that is a symlink out of
     `SPECS_DIR` (article, not book; skipped where symlinks are not
     available, as the existing spec symlink tests are).
   - `page.SPEC_MD == spec.SPEC_MD`, and `import chitragupta.render_output`
     in a fresh interpreter (the cycle guard).
2. `tests/test_figure_check.py`: a 445pt figure under a book is reported
   by `size-width` (red today: it passes); the same figure outside a
   book is not; `--page article` on the book figure silences it;
   `--width` beats the page's width; the `page` line and JSON object.
   The CLI-level cases go through `main()` with `check` stubbed where
   they need no compile, so CI's non-slow leg covers them.
3. `tests/test_figure_advisory*`: `size-height` divides by the height
   it is given.
4. `tests/test_figure_look.py`: `document(source, BOOK)` carries the
   book preamble; the digest differs between pages; `look()` and
   `refresh` default to `page_for`'s page; the `text_width` assertion
   reads `page.ARTICLE.text_width_pt`.

**Before and after on a real book.** Run `figure check` over a real
book's `figures/` (the digital-twins book in `chitragupta-drafts`) on
`main` and on the branch, and list in the PR every `size-width` finding
the book page adds. Nothing gates on `figure check`, but `figure-drawer`
treats a finding as something to resolve or allow, so the new ones are
named rather than discovered.

## Docs touched

- `docs/CLI.md`: the `figure check` flag table (a `--page` row), the
  `--json` key list (`page`), the `figure look` paragraph that says it
  sets the figure "on the render's own page", and the example.
- `docs/PACKAGING.md`'s CLI table: `[--page article|book]`.
- `docs/figure-checks/README.md` ("The default is 453pt", "453pt by
  default", the example lines) and `size.md` (`size-width`'s target;
  under `size-height`, one sentence that a book figure's share is of
  685pt while the layouts' reference ranges were taken at 700pt).
- The layout references' "fractions of the render's 453pt text width
  and 700pt text height" stay: those ranges were measured on the
  article page, and the `size.md` sentence covers the book.
- `chitragupta/figure/_look.py`'s module docstring, `_check.py`'s
  comment, and `tests/fixtures/figure/check/wide.tex`'s comment.
- `.claude/skills/figure-drawer/references/check.md` (the only copy:
  the other harnesses carry `SKILL.md` alone): the same sentence, and
  that a book unit's figure is checked against the book automatically.
- `docs/FIGURE-ROADMAP.md` Part X: X-1/X-3/X-5's reduced form shipped,
  the rest parked.
- Re-run every example report line that prints a width or a height
  share.

## Version

MINOR: a new module and a new optional CLI flag, nothing removed or
renamed. 6.160.1 became 6.163.0: `main` moved to 6.161.0 (#1152) and 6.162.0
(#1154) first.
