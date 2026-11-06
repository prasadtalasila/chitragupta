# Copying a run into a digest: exact words, clean type, nothing dangling

Read this before the first run you copy into a digest, and again before
any repair pass. It says what "copied exactly" means, how a copied run
carries an equation or a figure, and how it stops without pointing at
something the digest does not contain. Paths here are from the project
root.

## 1. Exact words, clean typography

`review digest` matches a run against the source after reducing both
to lower-case letters and digits, and it drops the source's own
reference markers (`[2]`, `[16, 34]`) before comparing
(`chitragupta/review/_quotation_match.py`). So the words and numbers
are what must be exact; the type is yours to clean. Keep every letter
and every digit in the source's order, and fix the parse's noise:

| The parse wrote | Write |
| --- | --- |
| `Supposeweareaskedtobuildavirtual model` | `Suppose we are asked to build a virtual model` |
| `Lumpedparameter models` | `Lumped-parameter models` |
| `37 . 5 ◦ C` | `37.5 °C` |
| `𝑇 ℎ`, `𝐺 𝑏𝑟` (math italic) | `` `T_h` ``, `` `G_br` ``, mapped in `math.md` (§2) |
| `Δ 𝑡` | `` `Δt` ``: keep the Greek letter itself, never the word `Delta` |
| `[2]`, `[ 24]`, `14,15 .` | delete them |
| `( i.e. , by another model)` | `(i.e., by another model)` |

Two edits look like cleaning and are not: a dropped word (`as close to
as possible` stays as written; fixing it is a `copy-mismatch`), and a
LaTeX command written into a run (`\Delta` adds the letters `delta`,
which the source does not have). If a parse is too broken to read,
pick another passage.

## 2. Equations: typeset, in the house math form

A digest typesets every equation it carries, exactly as a book chapter
does (`docs/WRITING-STANDARDS.md` §12, mapped form). A source equation
sits in the sidecar as its own passage with `"label": "formula"` and
LaTeX text, between the paragraphs around it:

```text
formula | C _ { h } \frac { d T _ { h } } { d t } = H _ { h } \cdot V _ { h } \cdot I _ { h } - ...
text    | where 𝑇 ℎ is the temperature of the heater ...
```

When a run you copy introduces, uses or explains an equation, carry
the equation too. End the paragraph before it, display it, and start
the next paragraph after it:

````markdown
The model is two coupled heat balances, one for the heater and one for
the box air. [see @key]

<!-- math -->
```
C_h dT_h/dt = H_h V_h I_h - G_hb (T_h - T_b)
```

where `T_h` is the temperature of the heater (measured in °C), ...
[@key, p. 114]
````

The fence holds an ASCII key; the dossier's `math.md` maps it to the
source's LaTeX with the parse's spacing removed
(`C_h \frac{dT_h}{dt} = H_h \cdot V_h \cdot I_h - G_{hb} (T_h - T_b)`).
Every symbol a copied run uses is a mapped code span too, so the run
and the equation are set alike in the pdf. A paragraph directly after a
displayed equation may open on "where": that is what the equation is
for, and the report knows it. Number an equation
(`<!-- equation: id -->`) only if a sentence of yours refers to it.
An equation is a display, never a run: the report does not match it,
so get it from the `formula` passage, not from memory.

**An equation of your own is set the same way.** A relation you write
to compare two sources, or a symbol you define in a sentence of yours,
is a `<!-- math -->` display or a mapped code span with its row in
`math.md`, never plain text and never a bare code span: one digest, one
way of setting mathematics.

## 3. Figures

`python -m chitragupta.draft figures <citekey>` lists a kept source's
figures and their crops. A digest may carry a source figure itself:
copy the crop into the topic's `figures/` and place it directly after
the run it belongs to, captioned in your own words and ending with the
cite string:

```markdown
![The parts of a model: inputs, parameters, states and the formalism beneath them, Figure 3.6 of [@key], p. 74](figures/<file>)
```

A copied run that names that figure of that source ("as Fig. 3.6
shows") is then not dangling; the caption's `Figure N of [@key]` is how
the report knows. A crop never travels into another draft.

## 4. Nothing dangling

The reader has only the digest. `review digest` reports three ways a
run points at nothing, as `dangling-reference`:

- **A numbered item of the source** ("Fig. 5.13", "Eq. (5.1)",
  "Sect. 6.4.3", "Chapter 5") that the digest does not show. Show it
  (§2, §3); or replace the mention with a bracketed editorial
  substitution, which the matcher reads as one: "`[The equation above]`
  is an instance of the first law"; or end the run before the sentence
  that names it.
- **A leftover reference marker** (`[2]`, `[44,45]`): delete it.
- **A run that opens on a word pointing back** ("where", "thus",
  "these", "however") with nothing before it from the same source.
  Start the run one sentence earlier, so its antecedent comes with it,
  or start it one sentence later.

None of this means "write fewer runs". It means each run is chosen to
be read on its own, the way a quotation in a published survey is.
