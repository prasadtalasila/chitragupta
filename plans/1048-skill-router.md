# 🧭 XII-1c: `figure-drawer` as a router with a taste gate

Status: **built.** Written 2026-10-29 against `main` at `dc0d9c4`, from a
brainstorming session on issue
[#1048](https://github.com/prasadtalasila/chitragupta/issues/1048), and
implemented in the same PR as this plan. Decisions marked *user* were
agreed in that session; the rest was the session's proposal, which the
user accepted as a whole.

**Written for** whoever changes the three copies of the `figure-drawer`
skill next. Such a session is governed by `DEVELOPER-AGENTS.md`, because it
edits `tests/` as well as skill prose.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` ("The skill"), #1039
(references live once under `.claude/`), and the commands that shipped
in #1052 (`figure new`, `figure look`) and #1053 (`figure check`).

**Not covered here:** the other ten skills' sizes, which are filed as
[#1091](https://github.com/prasadtalasila/chitragupta/issues/1091) (*user*)
with a ratcheting per-skill budget; and any change to the genre skills'
figure stubs.

## What it is for

`SKILL.md` had grown to 13,658 bytes of prose in ten steps. Several of
those steps asked the agent to assemble commands by hand, and nothing
before drawing asked whether the figure should exist, or should be
smaller, or should be two. The router keeps each step to a command or a
check. The judgement that matters most, whether to draw at all, now comes
before the first file is written.

## Decisions

| Question | Decision |
| --- | --- |
| What the taste gate does when it fires | **Option A** (*user*). It trims by itself: a node, edge or label that fails the remove test is cut, and the return names what was cut. A *structural* verdict (a sentence or a table would do; this is two figures) draws nothing and goes back to the caller with its reason, and the caller decides. On direct use the caller is the person, so the skill asks them and draws only if they still want the figure |
| Which skills the byte cap covers | `figure-drawer` only, at 8,000 bytes per copy. Every other skill is 14 to 42 KB; their budget is #1091 |
| The hand-built LuaLaTeX probe | **Dropped.** `figure check` compiles the figure in the render's own engine and fonts, reports `does-not-compile`, and exits 2 with no `lualatex` or `tikz.sty`. One `kpsewhich tikz.sty` before `figure new` still decides the inline-ASCII fallback, before anything is written. The library-loading rule (#781) moves to `references/figures.md` §6 |
| What stays in `SKILL.md` | Every command, because #1039 measured a pointer-only step being skipped (see #1068), plus the steps' order, the taste-gate questions, the no-citekey rule, both placement shapes, and "never presents a draft". Rationale, worked detail and edge cases move out |
| Where moved prose goes | `references/placement.md` (new: where the pair goes, and the three direct-use cases); `references/taste.md` (new: the gate's five questions, with what each cuts and what goes back to the caller); `references/figures.md` gains §5 (looking at a source's figures), §6 (libraries and compiling) and §7 (looking at the render) |
| The link test | Every `## N.` section of a figure-drawer reference is cited as `` `<path>` §N `` by all three copies, and every cited section exists. This is the `verify-docs-sync.py` idea from diagram-design. `test_every_neutral_file_is_named_by_some_skill` already fails a reference file no copy names |
| The rider scan (`tests/test_skill_figure_step.py`) | It reads the drawer's `SKILL.md` *and* its references, since `tikz@node@reset@hook` and the pre-flight list now live in a reference. The genre-side "no rider drifted back" check is unchanged |
| The genre skills | Unchanged. Their figure step already says "come back to this step when it returns". The drawer's return now says whether it drew, and if it did not, why |
| Version | PATCH: skill prose and tests, with no pipeline behaviour changed |

## The router

Two short sections, "Who called you" (a genre skill, `draft-reviser`, or
the person directly) and "Where it goes" (both shapes, one sentence each;
the rest in `placement.md`), then nine steps:

1. Look, never copy (optional): `draft figures <citekey>`.
2. Pattern, then layout: `patterns.md`, then the layout's own file.
3. **The taste gate**: a sentence or a table, the remove test, nodes that
   travel together, one focal node, one figure or two. Trim, or hand back.
4. `kpsewhich tikz.sty`; with none, no pair (`placement.md` §2). Then
   `figure new`.
5. Draw below the house block: panels lettered, no citekey, one
   `\usetikzlibrary` line.
6. Redraw the twin.
7. `figure check`: resolve or allow each objective finding, read the
   advisory ones, say so on exit 2. It never blocks.
8. `figure look`, and look; skip it when the tools are missing, and say so.
9. Return: the paths (or the gate's verdict), what the gate cut, what
   `check` reported and allowed, and whether the look was done.

## Tests

- `tests/test_skill_figure_router.py` (new): the 8,000-byte cap on each copy;
  the section-link test both ways; the taste gate sitting before `figure new`;
  its five questions and the hand-back; `figure check` read as never blocking;
  the return naming the gate's result.
- `tests/test_skill_figure_step.py`: the rider scan reads the references too,
  and the order test checks `kpsewhich tikz.sty`, `figure new`, `figure check`,
  `figure look`.

## What was not built

- A per-skill budget for every other skill: #1091.
- Moving the genre stubs' compile wording, which still tells a session that
  never loaded the drawer to compile with `lualatex`. That remains true and
  safe.
