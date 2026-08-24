# Format-native equation rendering, from a dossier-held mapping

Status: **proposal, unbuilt.** Written 2026-08-24.

**Written for** whoever implements this. **Assumed:**
[docs/RENDERING-FLOW.md](../docs/RENDERING-FLOW.md) for the two paths
through `render()`, [docs/DOSSIER.md](../docs/DOSSIER.md) for the
dossier's documented shape, and `docs/WRITING-STANDARDS.md` §12 for the
convention this would supersede. **Not covered here:** that convention
and the conversion already shipped, which is
`plans/math-typesetting-convention.md`.

**No roadmap item yet.** Rendering is not one of themes A--F, so this
needs either a new theme or a home under an existing one before it is
scheduled. That editorial call is deliberately left open.

## 🎯 The idea in one line

**The draft holds ASCII; the dossier holds the LaTeX; each output format
gets the spelling it can actually use.**

`` `k = 4` `` stays in the Markdown source. A mapping in the dossier says
that span means `k = 4` in math. `--format tex` emits `\(k = 4\)`,
`--format docx` gets a native Word equation, and `--format md` emits
whatever its consumer can read.

## 📌 Why this is worth building, and what changed

`§12` as shipped puts `$…$` in the draft. That is correct for
`tex`/`pdf`/`docx` and imposes a cost on `md`, which
[RENDERING-FLOW.md](../docs/RENDERING-FLOW.md) never sends through
pandoc -- so `$k = 4$` reaches `content/rendered/` verbatim. `§12`
accepts that cost on the grounds that rendered Markdown is a preview
artefact.

**That premise is wrong for this project's actual use.** The rendered
`.md` is read directly, as Markdown. It is a consumed artefact, not a
preview, and a reader of it should see `k = 4` rather than `$k = 4$`.

Three mechanisms for ASCII-in-`.md`-with-math-in-`.tex` were rejected in
`plans/math-typesetting-convention.md`. A dossier-held mapping is a
fourth, and it is the one that works -- **the key is the existing
backtick span, so the draft needs no new syntax at all**:

| Objection to the rejected three | Why the mapping avoids it |
| --- | --- |
| A regex cannot tell `` `k` `` from `` `as_of` `` | The mapping *declares* which spans are math. No inference. |
| An inline `math:` marker needs new draft syntax | The key is the span already there. |
| Pandoc raw spans (`{=latex}`) are dropped by non-LaTeX writers | Substitution runs before pandoc, so every writer gets real math. |
| Two spellings with nothing checking they agree | One spelling per artefact, and the mapping is checkable (see Drift). |

## 🗂 The artefact

`content/dossiers/<mirrored path>/math.md` -- an **8th file** in a
7-file documented dossier shape, so [docs/DOSSIER.md](../docs/DOSSIER.md)
gains a row and `§ Why several files rather than one` gains a sentence.

Markdown with a table, for the same reason the rest of the dossier is
Markdown ([DOSSIER.md](../docs/DOSSIER.md) `§ Why Markdown`): a human
reads and edits it.

```markdown
| ASCII in the draft | LaTeX |
| --- | --- |
| `k = 4` | `k = 4` |
| `Ts` | `T_s` |
| `k_day` | `k_\mathrm{day}` |
| `0.005^3 = 1.25e-7` | `0.005^{3} = 1.25 \times 10^{-7}` |
| `slope = 0.02` | `\mathrm{slope} = 0.02` |
```

Left column is matched **verbatim against the content of a backtick code
span**, never against prose. A span with no row is left alone -- that is
what keeps `as_of` and `GET /sensing/{unit}` in `\texttt{}` by
construction rather than by heuristic.

## 🔌 Where it hooks in

A new `chitragupta/render_output/_math.py`, beside `_figures.py` and
called from `render()` on the same temp-copy discipline as
`_safe_render_inputs` -- **the draft and the dossier are never written
to**.

**The one architectural constraint, and why it does not block.**
`render_output/_paths.py:57-60` commits that package to stdlib plus
`config`/`citation_gate`/`references`, *"so a genre skill can render
under bare `python`, which rules out importing `chitragupta/dossier/`."*
That is a **module-dependency** boundary, not a data one. The dossier's
location comes from `config.mirrored_dir()`, which is already shared
with `dossier.dossier_dir()` and is inside the allowed set. So `_math.py`
locates and parses `math.md` with stdlib alone and never imports the
dossier package. **Do not "simplify" this by importing
`chitragupta.dossier` -- it breaks bare-`python` rendering.**

`_figures.py` is the working precedent for the fork itself: one thing in
the draft, a different substitution per output format
(`_figures.py:201` vs `:218`).

## 📊 Per-format policy

| Format | Reaches pandoc? | Emit | Why |
| --- | --- | --- | --- |
| `tex`, `pdf` | yes | `\(…\)` | Real math; `amsmath` is already loaded. |
| `docx` | yes | `$…$` → pandoc | Pandoc turns `$…$` into **native Word equations** (OMML), not text. |
| `md` | **no** | the ASCII, untouched | Markdown is read as Markdown. |

**`--format md` does nothing at all**, which is the point: the draft is
already ASCII, so the no-op is the correct behaviour rather than a
special case to code. `_math.py` runs only on the LaTeX-bound path,
exactly as `_figures.py` forks today.

That also means the feature is **inert for `md`** -- if the mapping is
missing, malformed or stale, the Markdown output is unaffected. Only
`tex`/`pdf`/`docx` can regress, and those are the formats where the
gap/orphan report below runs.

## ⚠ Drift is the real cost

`draft-reviser` edits prose. It introduces `` `h = 2` ``, no row exists,
and the span renders `\texttt{h\ =\ 2}` -- silently reintroducing exactly
the defect `§12` was written to remove. **The mapping is only correct
while someone maintains it.**

Unlike "is this span math?", this is mechanically checkable, because the
mapping declares intent:

- **Gap:** a math-shaped span (contains `=`, `<`, `>`, or arithmetic
  between digits) with no row.
- **Orphan:** a row whose left column matches no span in the draft --
  the tell that a revision deleted or reworded the sentence.

Report both from `draft render` and from `dossier status`. **An aid, not
a gate**: [docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md) keeps
`chitragupta.draft gate` meaning exactly one thing -- a fabricated
citekey fails -- and this must not blunt it. Same standing as the review
layer.

Be honest in the plan's own record that the dossier has form here:
`scope.md`'s corpus fingerprint is a staleness marker that
[DOSSIER.md](../docs/DOSSIER.md) says is *"written once, by `init`, and
is not maintained by any"* later step. A mapping nobody updates decays
the same way. The gap/orphan report is the whole defence.

## 🧩 Known limitation: homographs

The key is a bare string, so one spelling gets one meaning per dossier.
`` `quality` `` as an API field in §3 and as a variable in §9 of the same
unit cannot both be served. Options, in order of preference:

1. **Accept and detect.** Flag a key that matches spans in sections with
   conflicting neighbours, and make the author rename one. Cheapest, and
   the collision is rare -- it did not occur once across the 15-chapter
   book.
2. Scope rows by section heading. More faithful, more machinery.

Do **not** solve this by making the left column a regex. That
re-introduces the ambiguity the mapping exists to remove.

## 🚚 Migration

Dossiers already on disk have no `math.md`. Absent file = no
substitution = today's behaviour, so **the change is inert until a
mapping exists** and no migration is forced. Say so in
[DOSSIER.md](../docs/DOSSIER.md), because a silently-optional dossier
file is otherwise indistinguishable from a broken one.

For the drafts already converted to `$…$`, adopting this means reverting
their `.md` to ASCII. That is exact, not a rewrite: the pre-conversion
sources are backed up outside `content/`, and
`plans/math-typesetting-convention.md` records where.

## 🌱 Seed data already exists

The 515-span conversion recorded in
`plans/math-typesetting-convention.md` produced ~100 distinct, **already
human-adjudicated** ASCII → LaTeX pairs -- `Ts` → `T_s`, `k_day` →
`k_\mathrm{day}`, `0.005^3 = 1.25e-7` →
`0.005^{3} = 1.25 \times 10^{-7}`, `= square root of (1/0.022569) = 6.66`
→ `= \sqrt{1/0.022569} = 6.66`. Those are the first `math.md` files,
not work to redo.

## 🛑 What would make this not worth building

Stated so a later reader can tell a decision from an accident:

- **Nobody maintains the mapping.** This is the one that matters. A
  `math.md` that goes stale is worse than no mapping, because the
  failure is silent and looks exactly like the original bug. If the
  gap/orphan report cannot be made to run automatically on every render
  of a LaTeX-bound format, reconsider the whole item.
- **The `.md` stops being read directly.** The entire benefit is that a
  human reading `content/rendered/*.md` sees `k = 4`. If that stops
  being true, `§12` as shipped is simpler and strictly better.

**HTML is explicitly out of scope.** This pipeline has no `--format
html`, and what any downstream converter does with the Markdown is not a
requirement on this design.
