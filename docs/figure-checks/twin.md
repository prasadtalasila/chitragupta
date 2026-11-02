# 🔤 Figure checks: the ASCII twin

Status: **reference.**

The rules about a figure's ASCII twin. Every figure exists twice: once
as a TikZ picture, `<name>.tex`, for the PDF and LaTeX renders, and
once as a plain 7-bit ASCII diagram, `<name>.txt`, beside it. The twin
is the only figure a reader of the `md`, `docx` or `html` render sees,
so it must name what the TikZ names. The contract is
[WRITING-STANDARDS.md §10](../WRITING-STANDARDS.md#-10-figures).
[README.md](README.md) explains how to read a report and how to record a
deliberate exception.

The twin is written by hand, so the two drift: a box renamed in one, a
tag added to the TikZ and never to the ASCII. These rules read both
files from source, so they hold whether or not the figure compiles.
"Appears in the twin" means every word of it, as a whole word, in any
order, case aside. Markup is stripped and maths dropped first, because
ASCII cannot spell `\hat{x}`. A gloss is never compared: the twin may
reword it to fit a narrow box. Whether the arrows join the same boxes
is still yours to check by eye.

Each rule below shows a faulty figure, the line `figure check` prints
for it, and the fixed one. Both are real files in
[examples/](examples/), and `tests/test_figure_check_examples.py`
compiles them, so the report lines on this page are what the check
prints today. The TikZ listings show the picture only; every file also
carries the house style block above it. The two renders of a pair look
the same, since only the twin differs, so this page shows the twins
instead of images.

## 🧭 Rules on this page

- [`twin-missing`](#twin-missing)
- [`t1-labels`](#t1-labels)
- [`t2-tags`](#t2-tags)
- [`t3-panels`](#t3-panels)

### `twin-missing`

**Catches.** No `<name>.txt` beside the figure. The target is
`figure`. The three comparisons below then have nothing to compare, so
they are listed under "not measured" rather than reported three times
over. This rule cannot be allowed: a figure without a twin is fixed,
never excused.

**Why it matters.** The `md`, `docx` and `html` renders have nothing to
show where the figure should be.

Faulty: `faulty.tex` has no `faulty.txt` beside it.

```latex
\node[cgbox, text width=26mm] (parse) {\cglab{Parse}{read the PDF}};
\node[cgkey, text width=26mm, right=8mm of parse] (index) {\cglab{Index}{store passages}};
\draw[cgedge] (parse) -- (index);
```

```text
  twin-missing          figure     no faulty.txt beside the figure
not measured
  t1-labels: no twin
  t2-tags: no twin
  t3-panels: no twin
```

Fixed: the same picture, with `fixed.txt` written beside it.

```text
+--------------+   +================+
|    Parse     |-->#     Index      #
| read the PDF |   # store passages #
+--------------+   +================+
```

**Fix.** Write `<name>.txt` beside the figure (the twin step of the
skill). Cannot be allowed.

### `t1-labels`

**Catches.** A name in the TikZ that is not in the twin. A name is a
node label's first line (`\cglab`'s name), a zone title or a legend
entry. Every word of it must appear in the twin. The target is the
node, or the name's text for an unnamed node.

**Why it matters.** A reader of the twin meets a box the prose calls
by another name, and cannot tell whether the two are the same step.

Faulty: the TikZ names the gate `Citation gate`.

```latex
\node[cgbox, text width=26mm] (draft) {\cglab{Draft}{cite from the ledger}};
\node[cgkey, text width=26mm, right=8mm of draft] (gate) {\cglab{Citation gate}{check citekeys}};
\draw[cgedge] (draft) -- (gate);
```

The twin shortens it to `Gate`.

```text
+----------------------+   +================+
|        Draft         |-->#      Gate      #
| cite from the ledger |   # check citekeys #
+----------------------+   +================+
```

```text
  t1-labels             gate       missing "citation"
```

Fixed: the twin uses the TikZ's words. The TikZ is unchanged.

```text
+----------------------+   +================+
|        Draft         |-->#  Citation gate #
| cite from the ledger |   # check citekeys #
+----------------------+   +================+
```

**Fix.** Use the TikZ's words for that name in the twin: `4-ch relay`
for `4-channel relay` drops `channel`. A gloss is not compared, so
reword those freely.

### `t2-tags`

**Catches.** A line of a node placed on a `\draw` or `\path` (a tag,
whatever its style) that is not in the twin, word for word as
`t1-labels`. The target is the edge, `a->b`, or the tag's text where
it joins no two names.

**Why it matters.** The tag says what moves along the line. Without it
the twin's arrow says only that something does.

Faulty: the TikZ tags the arrow `writes passages`.

```latex
\node[cgbox, text width=26mm] (index) {\cglab{Index}{store passages}};
\node[cgkey, text width=26mm, right=34mm of index] (ledger) {\cglab{Ledger}{one SQLite file}};
\draw[cgedge] (index) -- node[cgtag] {writes passages} (ledger);
```

The twin's arrow has no tag.

```text
+----------------+                   +=================+
|     Index      |------------------>#     Ledger      #
| store passages |                   # one SQLite file #
+----------------+                   +=================+
```

```text
  t2-tags               index->ledger missing "writes"
```

Only `writes` is reported missing: `passages` is in the twin already,
in Index's gloss.

Fixed: the tag goes on the twin's arrow.

```text
                 writes passages
+----------------+                   +=================+
|     Index      |------------------>#     Ledger      #
| store passages |                   # one SQLite file #
+----------------+                   +=================+
```

**Fix.** Put the tag on the twin's arrow, in the TikZ's words.

### `t3-panels`

**Catches.** The panel letters opening a label line in the TikZ,
`(a)`, `(b)`, that are not the set of `(<letter>)` tokens in the twin.
The target is `figure`. A letter counts in the twin only in its
parentheses, so `a)` or `(A)` is not a panel letter.

**Why it matters.** The prose says "panel (b)". A reader of the twin
must be able to find it.

Faulty: the TikZ letters its two panels `(a) before` and `(b) after`.

```latex
\node[cgbox] (draft-a) {draft};
\node[cgnone, below=of draft-a] (gate-a) {no gate};
\node[cgbox, right=16mm of draft-a] (draft-b) {draft};
\node[cgkey] (gate-b) at (draft-b |- gate-a) {gate};
\draw[cgedge] (draft-a) -- (gate-a);
\draw[cgedge] (draft-b) -- (gate-b);
\begin{scope}[on background layer]
  \node[cgzone=cgMute, fit=(draft-a)(gate-a)] (panel-a) {};
  \node[cgzone=cgMute, fit=(draft-b)(gate-b)] (panel-b) {};
\end{scope}
\node[below=2mm of panel-a, font=\normalsize\bfseries] (label-a) {(a) before};
\node[below=2mm of panel-b, font=\normalsize\bfseries] (label-b) {(b) after};
```

The twin writes `a)` and `b)`.

```text
. . . . . . . . . . .    . . . . . . . . . . .
:  +------------+   :    :  +------------+   :
:  |   draft    |   :    :  |   draft    |   :
:  +------------+   :    :  +------------+   :
:         |         :    :         |         :
:         v         :    :         v         :
:  +- - - - - - +   :    :  +============+   :
:  |  no gate   |   :    :  #    gate    #   :
:  +- - - - - - +   :    :  +============+   :
. . . . . . . . . . .    . . . . . . . . . . .
     a) before                b) after
```

```text
  t3-panels             figure     tex (a), (b); twin none
```

Fixed: the twin's last line letters the panels as the TikZ does.

```text
     (a) before               (b) after
```

**Fix.** Letter the twin's panels as the TikZ's: the same `(a)`, `(b)`.
