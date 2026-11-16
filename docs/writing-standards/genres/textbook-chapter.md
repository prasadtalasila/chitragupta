# 🎓 Textbook chapter: what the genre owes its reader

Assumes the core, §1–9 of [WRITING-STANDARDS.md](../../WRITING-STANDARDS.md).
This file holds the writing rules that apply to an undergraduate
textbook chapter, lecture notes, a course reader or a worked-examples
handout alone: who the genre is for, its house style, how often its
figures and numbered equations appear, and what its reread looks for.
The element rules are in [figures.md](../figures.md),
[mathematics.md](../mathematics.md) and [tables.md](../tables.md); this
file repeats none of them.

## 🎯 What a textbook chapter owes its reader

A textbook chapter **teaches a student who is studying the topic**:
sitting with the text, following an argument, working problems. Its
register is teaching, not persuading a reviewer, which is what separates
it from a survey and a thesis chapter. Its reader is reading rather than
doing, which is what separates it from a tutorial, whose reader is at a
keyboard producing a working result. Both are teaching genres and they
are not interchangeable: the most common failure is writing one when the
other was asked for, and the two have opposite rules about explanation,
so a wrong guess fails at both.

**Explanation is welcome here and belongs here.** A digression into
*why* is a feature of a textbook chapter and a defect in a tutorial.

A textbook chapter's unit for multi-source synthesis is the section
([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §11): a paragraph
may rest on one source, but a section that cites at all spans two or
more citekeys and does not take them in blocks. Citing at all is
optional in this genre; most of a chapter is original worked examples
and exercises.

## 👥 Audience first

Before drafting anything, write down who the student is and what they
already know ([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §1):
in the dossier's `scope.md`, not necessarily in the chapter. Everything
downstream depends on it: what can go unexplained, which prerequisites
need a recap, how much notation is safe.

Then check yourself against the **curse of knowledge**. You know this
material and the student does not, and the specific danger is the step
that feels too obvious to state. Every term is defined once, at first
use, and then used consistently: never two names for one concept, never
one name for two. The core's §2 lists the words that mark a skipped
step; in a chapter, a sentence carrying one of them is a candidate for
expansion, not for the chapter.

## 🖋 House style for this genre

Beyond [WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §4:

- **Prefer a concrete instance over an abstract statement of the general
  case, then generalise from it.** Students build the general rule from
  instances, not the reverse, and this matters more here than in any
  other genre.
- **Put a worked instance beside each new symbol.** Notation follows
  [mathematics.md](../mathematics.md) §12 and the mathematical-prose
  rules it points to: a symbol is defined in its own sentence, and a
  student meets it in use straight away.

## 📐 Figures: common, and earned one at a time

A figure sits beside the worked example or the concept it clarifies.
Original ASCII-first diagrams suit this genre almost as well as they suit
a tutorial, but less automatically, because a chapter also leans on
prose explanation to do that work: most sections still need none. When
a chapter does draw one, the whole of [figures.md](../figures.md) §10
applies to it.

The temptation peculiar to this genre is the textbook diagram everyone
in the field already knows. Redrawing it from a source is the same
violation as copying the source's figure, in different pixels. Draw what
this chapter's own example needs instead, and attribute in the prose,
never inside the figure, where the citation gate cannot see a key.

## 🔢 Mathematics: more of it than any other genre

A worked example is mostly quantities, so this genre has more of
[mathematics.md](../mathematics.md) §12 than any other: every quantity
in it, `` `k = 4` `` as much as a displayed derivation, is written the
way §12 says. A quantity left as a bare code span renders as typewriter
text beside the equation that defines it, which is the thing §12 exists
to stop.

It also has more numbered equations than any other genre, because it has
more derivations. §12's rules for choosing them apply unchanged. In
practice: a worked example that chains several displayed steps to a
result numbers only that result, the one the student is meant to cite
back to, most often from the chapter's closing summary or a later
example that reuses it. A standalone definition is numbered the same way
if the chapter names it again later; a quantity that appears once and is
never pointed back at stays unnumbered.

## 👓 The reread

Read the draft once as the student named in `scope.md` before presenting
it ([WRITING-STANDARDS.md](../../WRITING-STANDARDS.md) §6), not as
yourself. In a textbook chapter, check specifically for:

- a term that arrives before it is defined;
- a step in a worked example that skips its reasoning;
- notation that changes meaning partway through the chapter.

This pass catches more real problems in a chapter than any other single
step.
