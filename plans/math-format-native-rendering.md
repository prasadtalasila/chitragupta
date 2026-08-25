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

### 🧱 Display math: a `<!-- math -->` marker and a plain fence

A code *span* is to inline math what a fenced block is to display math.
The draft spells a displayed equation as an **untagged** fence preceded
by a marker, and the same table supplies its LaTeX:

````markdown
<!-- math -->
```
dW/dt = -W/tau
```
````

**Why a marker rather than a ```` ```math ```` tag.** GitHub and GitLab
render a `math`-tagged fence *as LaTeX*, so ASCII inside one is
mis-typeset there -- `tau` becomes three italic letters rather than τ,
which is worse than showing it plainly. An untagged fence renders as a
plain code block everywhere. The marker also matches
[§10's figure convention](../docs/WRITING-STANDARDS.md#-10-figures)
exactly, which that section describes as *"inert to pdflatex, dropped by
pandoc, and meaningful only to this pipeline"* -- the same three
properties are wanted here.

The cost is one extra line per equation and a marker that can drift from
its block. A marker with no fence after it, or a fence body with no row
in the mapping, are both gap conditions for the report below.

**The marker is what disambiguates.** `_math.py` must read the fence
*after* a `<!-- math -->` and no other, because every other fence holds
code. Nothing else in the draft changes meaning.

**Substitute blocks before spans.** The prototype got this wrong once:
if inline substitution runs first it walks into the fence body and
rewrites `W` and `tau` there, corrupting the block before the display
rule ever sees it. Blocks first, then spans over what remains.

### 🔤 Which notation lives in which artefact

Worth stating because three different math spellings are in play and
only one of them is ever hand-written:

| Artefact | Holds | Written by |
| --- | --- | --- |
| draft `.md` | `<!-- math -->` + fence, and `` ` ` `` spans -- **ASCII** | the author |
| rendered `.md` | the same, byte-identical | `--format md`, which does not reach pandoc |
| temp copy | `$$…$$` and `$…$` -- pandoc's native math markup | `_math.py`, discarded after the render |
| `.tex` | `\[…\]` and `\(…\)` | **pandoc** |

Neither `.md` ever contains `\[…\]` or `$$…$$`, and nobody hand-writes a
math delimiter at any layer. `\[…\]` is LaTeX's own display form --
`$$…$$` is plain TeX, ignores the `fleqn` class option and mishandles
`\abovedisplayshortskip`, which is why `amsmath` treats it as obsolete.
Pandoc already emits the correct one, so this design never has to choose.

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

**There is no per-format table, and that is the point.** The fork is a
single predicate that [RENDERING-FLOW.md](../docs/RENDERING-FLOW.md)
already draws: *does this render reach pandoc?* `--format md` on a
Markdown draft never does; every other combination does.

| Reaches pandoc? | `_math.py` does | Then pandoc emits |
| --- | --- | --- |
| **yes** (`tex`, `pdf`, `docx`) | substitute the span with `$…$` | `\(…\)` for LaTeX, OMML for Word -- format-native, per writer |
| **no** (`md`) | nothing | the ASCII, untouched |

**Substitute `$…$`, never `\(…\)`.** This is the trap: `\(k = 4\)` is
*not* math to pandoc's Markdown reader. Handed
`A $k = 4$ and B \(k = 4\)` it emits `A \(k = 4\) and B (k = 4)` -- the
second one silently loses its backslashes and becomes ordinary
parenthesised text. `$…$` is pandoc's native inline math and is the only
spelling that survives; each writer then renders it in its own idiom,
which is what "format-native" means here.

**`--format md` does nothing at all**, which is the point: the draft is
already ASCII, so the no-op is correct behaviour rather than a special
case to code. `_math.py` runs only on the pandoc path, exactly as
`_figures.py` forks today (`:201` vs `:218`).

That also means the feature is **inert for `md`** -- if the mapping is
missing, malformed or stale, the Markdown output is unaffected. Only the
pandoc formats can regress, and those are where the gap/orphan report
below runs.

### ⚠ `docx` is not a requirement, and must still be substituted

`--format docx` is not something this project needs, but it exists in
the CLI, and **"not required" must not be implemented as "excluded from
`_math.py`"**. Today `§12`'s `$…$` in the draft reaches pandoc's docx
writer and becomes a real Word equation. If the draft reverts to ASCII
and docx is left out of the substitution, that same span becomes
`\texttt{k = 4}` in Word -- *worse than before this plan existed*, and
silently.

Keying on "reaches pandoc" rather than on a list of formats avoids this
for free: docx is served by the same line of code as `tex`, no extra
case, no extra test beyond one that asserts an `oMath` element survives.
A per-format allowlist is how the regression gets written by accident.

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

### 🔁 What a revision can actually do, and what survives it

Four cases, and they are not equally safe. Substitution is a key lookup
over every span, so a *repeat* of an already-mapped span is correct with
no action from anyone -- that is the design carrying its own weight, and
it covers the common case of a symbol used again in new prose.

| A revision... | Result if nobody reconciles | Detected? |
| --- | --- | --- |
| repeats a mapped span (`` `k` `` again, new sentence) | **correct** -- substituted by lookup | n/a, nothing to do |
| rewords a mapped expression (`k = 4` → `k = 4.5`) | renders `\texttt{}` | **yes** -- gap, it has `=` |
| deletes a span | nothing renders wrong | yes -- orphan, harmless |
| introduces a **new bare symbol** (`` `j` ``) | renders `\texttt{}` | **no -- blind spot** |

**The blind spot is the worst combination: least detectable, most
common.** The gap rule keys on `=`, `<`, `>` or arithmetic, and a bare
symbol has none of them. In the 15-chapter book that shape *dominated* --
of 515 conversions, roughly 296 were single symbols (`k`×55, `h`×50,
`Ts`×47, `g`×42). A rule that misses those is not a defence.

**Fix it by closing the world over symbols, not by widening the
heuristic.** The mapping already declares which symbols this draft uses:
collect every symbol appearing in a mapped LaTeX *value* -- `\tau`, `k`,
`W_0` -- and treat any backtick span equal to one of them, but lacking
its own row, as a gap. That is document-derived rather than guessed, and
it is the same technique that took the real conversion from 253 clashes
to zero. A genuinely new symbol usually enters via an equation, so it
enters the value-space in the same revision that introduces it.

**And let `render` exit non-zero on a gap.** The "aid, not a gate" line
above protects `chitragupta.draft gate`'s single meaning; it says nothing
about `render`, which already refuses to write outside `content/` and
refuses to overwrite its own source. A skill that ignores a warning still
ships a wrong pdf; one that gets a non-zero exit cannot. This is the
difference between correct-by-instruction and correct-by-construction,
and it is worth more than any wording in the six SKILL.md files.

Be honest in the plan's own record that the dossier has form here:
`scope.md`'s corpus fingerprint is a staleness marker that
[DOSSIER.md](../docs/DOSSIER.md) says is *"written once, by `init`, and
is not maintained by any"* later step. A mapping nobody updates decays
the same way.

## 👤 Who maintains it -- the part this plan was missing

The gap/orphan report above is **detection, not ownership**, and it fires
at render time, after the revision, as an aid rather than a gate. An
earlier draft of this plan stopped there. That is a smoke alarm with
nobody assigned to call the fire brigade, and it is the difference
between a mapping that survives and one that decays exactly as
`scope.md`'s fingerprint did.

**As things stand today, no skill would touch `math.md`.** Every reviser
enumerates the dossier files it handles *by name* -- `draft-reviser`'s
step 6 is literally "Write the dossier back", against a closed list --
so an eighth file is not picked up implicitly by any of them:

| Skill | Dossier files it names today | Needs |
| --- | --- | --- |
| the four Markdown genre writers | write the dossier at draft time | **create** `math.md` alongside `evidence.md` |
| `draft-reviser`, main mode | all 7 | reconcile rows for every section it edits |
| `draft-reviser`, copy-edit mode | `revisions.md` only | **see below -- the sharp case** |
| `corpus-reviser` | 7 | same as `draft-reviser`, over a wider rewrite |
| `overlap-reviser` | 5 | **see below -- the sharpest case** |
| `book-assembler` | writes no prose | only: do not lose per-unit mappings when composing |

`thesis-chapter-writer` is deliberately absent: it emits a `.tex`
fragment and writes `\(…\)` directly, so it has nothing to map.

**The two that are worse than merely not-updating.**

*`draft-reviser`'s copy-edit mode* asserts of itself, at step 6, that
there is *"no evidence delta, no new rejection and no moved section to
record"*. That is true today and **becomes false the moment `math.md`
exists**: "convert this to en-GB" or "fix the grammar" rephrases the
sentence around an equation and can add, drop or alter a span. A mode
whose whole safety argument is "this pass changes nothing structural"
must not silently acquire a structural side effect. Either it reconciles
the mapping too, or it is barred from editing a line containing a mapped
span and says so.

*`overlap-reviser`* is sharper still. Its stated job is to rewrite *"each
short uncited run to preserve the claim and the citation while breaking
the borrowed wording"* -- deliberate rephrasing is precisely the
operation that desyncs a mapping keyed on exact span text, and it is the
skill least likely to notice, because it is reasoning about borrowed
wording rather than about quantities. Its existing discipline is the
right hook: it already re-runs `draft gate` and `verbatim recheck` on
every repair, so the gap/orphan check joins that same must-re-pass list.

**Do not solve this by making the report a gate.**
[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md) keeps
`chitragupta.draft gate` meaning exactly one thing. Ownership belongs in
the skills that do the editing, which is where every other dossier file's
upkeep already lives.

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

## 🧪 Prototyped, and what it proved

A ~25-line prototype of `_math.py` was run against a draft holding one
inline and one displayed equation, with the mapping above. Two results
worth keeping:

1. **The temp copy it produced was byte-identical** to the same document
   written under `§12`'s `$…$` convention. So this design is not an
   approximation of the shipped one -- it converges on exactly the same
   input to pandoc.
2. **The rendered PDF text was byte-identical too** (compared via
   `pdftotext`). The `.tex` carried real `\(W\)`, `\(\tau\)` and a
   displayed `\[\frac{dW}{dt} = -\frac{W}{\tau}\]`.

That is the whole claim of the design, demonstrated rather than argued:
**same PDF, different Markdown.** It also means the implementation has a
cheap and exact test -- render a fixture both ways and assert the temp
copies match, rather than asserting anything about pdf bytes.

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

- **The skill edits are not made.** This is the one that matters, and it
  is now the item's real size: `_math.py` is small, but the ownership
  above means editing **six SKILL.md files** as well. A `math.md` that
  goes stale is worse than no mapping, because the failure is silent and
  looks exactly like the original bug. If those edits are not going to
  land in the same change, do not build the module either -- a mapping
  with detection and no owner is the decay case, not a partial win.
- **The `.md` stops being read directly.** The entire benefit is that a
  human reading `content/rendered/*.md` sees `k = 4`. If that stops
  being true, `§12` as shipped is simpler and strictly better.

**HTML is explicitly out of scope.** This pipeline has no `--format
html`, and what any downstream converter does with the Markdown is not a
requirement on this design.
