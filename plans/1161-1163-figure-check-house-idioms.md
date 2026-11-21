# `figure check`: the house idioms, two rule holes and a clean exemplar

Status: **design, approved 2026-11-21.** Tasks in
[1161-1163-figure-check-house-idioms-tasks.md](1161-1163-figure-check-house-idioms-tasks.md).
Written 2026-11-21 for
[issue 1161](https://github.com/prasadtalasila/chitragupta/issues/1161),
[issue 1162](https://github.com/prasadtalasila/chitragupta/issues/1162) and
[issue 1163](https://github.com/prasadtalasila/chitragupta/issues/1163),
items 1 to 5 of
[issue 1108](https://github.com/prasadtalasila/chitragupta/issues/1108).

**Written for** whoever builds or reviews it. **It assumes**
[plans/fig-xii-figure-drawer-v3.md](fig-xii-figure-drawer-v3.md) for the
connector rules and
[plans/1111-1113-figure-check-fixes.md](1111-1113-figure-check-fixes.md)
for the last change to them. **Not covered here:** a tool that edits a
figure to fix a finding. Fixing stays with the figure-drawer skill's
check loop (its step 7).

## Why

The figure-drawer skill copies the scaffolds and exemplars, and fixes
what `figure check` reports. A rule that misses a defect lets it into a
user's figure, and an exemplar with a defect hands it to them directly.

## Decisions (user, 2026-11-21)

1. **One pull request for the three issues.**
2. **c3 option A:** a shared end point excuses two connectors only when
   both leave the shared stretch (a fork). Where one lies on the other
   end to end, it is reported, and the finding says so.
3. **Fixing stays with figure-drawer.** The finding names which case it
   is, and `references/check.md` gives the fix for each.

## Measured before the change (2026-11-21, `main` at 9862c8c)

- `figure check` over the 11 scaffolds and 7 exemplars: 17 clean;
  `architecture.tex` reports `c6-tag-covered` twice (`sync->draft`
  under `z1` and `z2`).
- c3's shared-end skip and c6's any-node containment skip each removed
  outright: no new finding on the 18. The owner's run on the book's 40
  figures (issue 1163's comment) found the same for c3; for c6 its 4
  new findings were all inside `fit` groups, which `zones()` excuses.
- `stranded-arrowhead` with `cgedge`, `cgstart`, `cgweak` and `cgback`
  read as heads: no new finding on 74 figures (55 in the book, 19 in
  `assets/tikz/`).

## The changes

### #1162 item 1: already fixed

`overlong_nodes` counts a `\cglab` label since #1160's brace-aware
`declaration()`; `tests/test_figure_source_spellings.py:42` holds it.
No code. The PR closes the item with that pointer.

### #1162 item 2: `stranded-arrowhead` reads a head set by a style

`_source.py`'s `stranded_arrowheads` treats a statement's leading options
as drawing an end head when they hold `->`, an `arrows.meta` end tip
(`-{Latex[...]}`, `-Stealth`), or a style the figure's own source defines
with one. Styles are read from the source's `<name>/.style={...}`
definitions, following inheritance (`cgback` is `cgedge, ...`), so a
house figure works because it carries the block, and an author's own
style works the same way. A style the source does not define is looked
up in the shipped `assets/tikz/cg-figstyle.tex`, so a snippet with no
block (the issue's own reproduction) and a figure that `\input`s the
block both resolve. A start head (`<-`, `{Latex}-`) is read the
same way for the existing "continuing statement draws its own head"
clause. Pure Python; fast tests.

### #1163 item 3: c3 reports one connector lying on another

`coincident()` in `_route_rules.py`: for a pair sharing an end point, the
pair is excused only if each connector has more than `_SHARED_MM` (2mm)
of its length outside the shared stretch. Otherwise it is reported as

```text
  c3-coincident         draft->gate+gate->draft  gate->draft lies wholly on draft->gate
```

naming the shorter (or either, if equal) as the one lying on the other.
Pairs with no shared end keep today's test and message
(`share N.Nmm`).

### #1163 item 4: c6 excuses only a zone

`tag_covered()` in `_clearance_rules.py`: a tag inside a node's box is
excused only when that node is in `zones()` (a zone card or a `fit`
group, framed or not). A card holding a whole tag is reported. Unframed
zones stay skipped entirely, as today.

### #1161 / #1163 item 5: the exemplar

Drop the `ledger` tag on `sync -> draft` in
`assets/tikz/exemplars/architecture.tex:418`, and its twin's `ledger`
label in `architecture.txt:8`. The Corpus card already reads "parse,
ledger". Widening the zone gap is ruled out: the tag is 11.1mm, the gap
2.5mm, and the figure is already at its 453pt width.

### The test that catches the next one

A slow-tier test (`@pytest.mark.slow`, needs TeX) runs `figure check`
over every scaffold and every exemplar and expects no unanswered
objective finding.

### Docs

- `docs/figure-checks/CONNECTORS.md`: c3's and c6's **Catches** say what
  is now excused; c3 shows the two new cases (return edge on its
  forward edge; skip edge over a chain) as code and the line the check
  prints. No new rendered pair: `tests/test_figure_check_examples.py`
  holds each rule to exactly one faulty/fixed pair, and c3's existing
  pair still shows its main case.
- `.claude/skills/figure-drawer/references/check.md`: c3's fix row names
  both cases (offset the pair either side of the line; route or delete
  the skip edge), and `stranded-arrowhead`'s row stops saying `->`. Each
  page's **Fix.** paragraph is check.md's cell word for word (a test
  holds it), so both change together.
- `docs/figure-checks/NODES.md`: `stranded-arrowhead` says a head set by
  a style is read.

## Left to the builder

- Where the style-resolution helper lives (`_source.py` or `_scan.py`).
- The exact wording of the c6 "inside a card" message, if it differs.
- Release notes and version per DEVELOPER-AGENTS.md. The house block is
  unchanged, so no block bump.

## Acceptance

Re-run the three measurements above after the change: the 18 assets
report no finding; the book's 55 figures report none that they did not
report before, or each new one is shown to be a real defect.
