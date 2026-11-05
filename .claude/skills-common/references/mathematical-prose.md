# Mathematical prose: the sentences around a symbol

Read this on every run of a chapter skill, whether or not the outline
promises maths: a single formula in a worked example brings it in. It
governs the prose around symbols, conditions and derivations.
`docs/WRITING-STANDARDS.md` §12 governs how a symbol is *set*, and the
dossier's `math.md` holds its LaTeX and, under `## Symbols`, its
meaning. No sentence here is checked by a tool; the rules are for the
writing pass and for the reread as the reader. Paths here are from
the project root.

The examples share one model: a potted plant whose soil moisture `m`
(percent) falls at a drying rate `d` each hour and rises by `g` points
per millilitre of water `V`, checked every `T_c` hours. Each rule shows
two pairs, *before* and *after*.

## Define a symbol in its own sentence

Give a new symbol a sentence of its own, starting a line, that states
its type or unit and a **role word**: the noun the reader will use to
recall it. The role word agrees with the symbol's `## Symbols` row in
`math.md` (the glossary term it links, or its words). The table holds
the meaning once; this sentence is where the reader meets it.

- *Before:* "The pot dries at a rate `d`, so after `T_c` hours the
  reading is lower."
  *After:* "Let `d` be the drying rate, in percentage points per hour.
  With no water, the reading falls by `d` each hour."
- *Before:* "Watering with `V` ml raises it by `g * V`."
  *After:* "Let `V` be the dose, the volume of water given at one
  check, in millilitres. Let `g` be the dose response: the rise in
  moisture per millilitre, in percentage points."

## Repeat the role word after a gap

When a symbol returns after a gap -- a new `##` or `###` section, or
three or more paragraphs since its last mention -- put the role word
back in front of it. The student who skipped ahead, or lost the
definition, recovers it from the phrase.

- *Before:* "In this section `d` doubles."
  *After:* "In this section the drying rate `d` doubles."
- *Before:* "Choose `T_c` so that `m` never drops below `m_lo`."
  *After:* "Choose the check interval `T_c` so that the moisture `m`
  never drops below the lower threshold `m_lo`."

## Choose letters on purpose

Pick a letter the reader can remember (`d` for drying, `V` for volume),
and keep each region of the alphabet to one job: `i`, `j`, `k`, `n` for
indices and counts, `t` for time, `T_` with a subscript for intervals
and periods, `a`, `b`, `c` for constants fitted from data. The regions
govern the base letter; a subscript is a label, so `m_t` (target
moisture) is a moisture, not a time. One letter means one thing for the
whole chapter, and in a book for the whole book. A book's `registry
check` reports a symbol naming two things, but a clash is cheaper to
avoid than to repair across chapters.

- *Before:* "The checks are counted by `k`; later, `k` is also the
  fitted slope."
  *After:* "The checks are counted by `k`, and the fitted slope is `a`."
- *Before:* "Let `x` be the moisture and `y` the dose."
  *After:* "Let `m` be the moisture and `V` the dose."

## Write the "then"

An "if" without its consequence leaves the student to guess where the
condition ends. State the consequence, and do not open a sentence with a
symbol: a capital letter cannot mark the start of `d`.

- *Before:* "If the reading is below `m_lo`, water."
  *After:* "If the reading is below the lower threshold `m_lo`, then the
  controller gives one dose `V`."
- *Before:* "`d` is larger in summer."
  *After:* "The drying rate `d` is larger in summer."

## State the claim first, and say what was shown

Before the first step of a derivation, say what it will establish.
After the last step, say that it has: "so we have shown ...", restating
the claim in words. The student then knows where the argument is going
and when it has arrived.

- *Before:* a chain of four displayed lines ending in the formula for
  `T_c`, followed by the next section.
  *After:* "We now show that checking every `T_c = (m - m_lo) / d`
  hours is just often enough. ... So we have shown that a check interval
  of `(m - m_lo) / d` hours keeps the moisture at or above `m_lo` without
  water in between."
- *Before:* "Substituting, rearranging and simplifying gives the dose."
  *After:* "We want the dose `V` that restores the target moisture
  `m_t`. ... So we have shown that a dose of `(m_t - m) / g` millilitres
  restores the target moisture from any reading `m` below it."

## Keep the argument linear

One paragraph per step, each opening with what the step does. An
argument is a line, not a map: no boxes-and-arrows diagram of the
logic. A figure is for the objects the argument is about, never for its
reasoning.

- *Before:* one paragraph that substitutes, rearranges and checks
  units in a single run of clauses.
  *After:* three paragraphs, opening "Substitute the dose ...",
  "Rearrange for `V` ...", "Check the units: ...".
- *Before:* a figure of arrows from "drying" and "dose" to "next
  reading" standing in for the update rule.
  *After:* the update rule derived in two short paragraphs, with the
  figure (if any) showing the pot and its sensor.

## Say which condition you checked

Before applying a result, name the condition it needs and the fact that
meets it. A student who applies the result elsewhere then knows what to
check first.

- *Before:* "So the linear model gives the next reading."
  *After:* "The dose is below the pot's 200 ml capacity, so no water
  drains away and the linear model applies: the moisture just after
  watering is `m + g * V`."
- *Before:* "Hence the controller never lets the plant dry out."
  *After:* "The drying rate `d` was measured as constant across the
  day, which the interval bound assumes; hence the controller never
  lets the moisture fall below `m_lo`."

## Where the notation table lives

A Markdown draft writes no symbol list of its own. The dossier's
`math.md` `## Symbols` table *is* the chapter's notation table, and a
book prints every unit's table as its List of Symbols. A list in the
draft, or in `scope.md`, is a second copy that drifts. When a section
introduces many objects at once, a figure of how they relate (drawn
through the figure step) can earn its place; the definitions still
come one sentence each.

A `.tex` unit has no `math.md`. Its symbols belong in the thesis's own
front matter, which the user owns: never write a list of symbols into
the fragment, and never add a `## Symbols` row for it. The prose rules
above apply unchanged, with symbols set as LaTeX:

- "Let \(d\) be the drying rate, in percentage points per hour."
- "In this section the drying rate \(d\) doubles."

## Source

The ideas in this file are Gareth Wilkes's, *A Brief Guide to
Mathematical Writing* (Department of Pure Mathematics and Mathematical
Statistics, University of Cambridge, revised 2023): §1 "General tips"
(its "If ... then", linearity, checking conditions and diagrams), §2
"Notation and definitions" and §3 "Formatting and structuring proofs". The
guide states no licence, so they are paraphrased here and none of its
wording or examples is used. `docs/WRITING-STANDARDS.md` "Sources and
attribution" carries the credit.
