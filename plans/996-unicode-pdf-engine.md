# #996: render our own PDFs with a Unicode TeX engine

Status: **built in PR #1000 (6.132.0)**, together with this plan.
Written 2026-10-04 for
[#996](https://github.com/prasadtalasila/chitragupta/issues/996), on top
of #948 (`plans/948-latex-unicode-characters.md`, merged in #1001 as
6.131.0). The plan started as a measurement spike; the maintainer then
decided the open questions (below), and the same PR implemented them.

**Written for** whoever maintains `chitragupta/render_output/` after
this: someone who can read Python and LaTeX and has read the #823
plan (`plans/823-tex-read-hardening.md`).

**Assumed:** the shipping cycle in `DEVELOPER-AGENTS.md`.

**Not covered here:**

- `--fragment` output and the user's own thesis or book preamble. They
  choose their own engine. #948's `.sty` keeps serving pdflatex there.
- The figure-layout probe (`review/figure_layout/_probe.py`) and the
  bench compile, which stay on pdflatex. See "Out of scope".
- Tagged (accessible) PDF. LuaLaTeX is the prerequisite, not the
  feature.

## 📐 Decisions

| Decision | Why |
| --- | --- |
| **LuaLaTeX is the only engine for chitragupta's own `pdf` renders.** No `[render] pdf_engine` key, no pdflatex fallback | Maintainer's decision. luaotfload fallback chains cover a Latin draft quoting Telugu or Chinese with one list. XeLaTeX's per-script switching took three attempts in the spike and still dropped Devanagari and three symbols |
| **STIX Two Text + STIX Two Math**, Latin Modern Mono for code at `Scale=1` | The only pair that printed every character of the issue's probe. Mono at its own size: pandoc's default `Scale=MatchLowercase` grew it to STIX Two's x-height, and a sample tutorial then wrapped three code lines where pdflatex wrapped one, breaking `style_typeset.py`'s 79-column model |
| **Fallback chain**: STIX Two Math, Noto Serif, DejaVu Sans, Noto Sans Symbols 2, Noto Serif Telugu, Noto Serif Devanagari, **Noto Serif CJK SC**, Unifont, Unifont Upper (`chitragupta/pdf_fonts.py`) | Measured against all 1,873 characters of #948's `.sty`: STIX Two plus the script fonts left 97 missing; Noto Serif, DejaVu Sans and Noto Sans Symbols 2 brought that to 6; Unifont and Unifont Upper cover the last six (U+A7F2-A7F4, U+10783, U+107A2, U+107A5, Unicode 14 modifier letters no other packaged font has). Unifont comes last so it draws only those. CJK is SC only: one `.ttc` holds every regional face, so TC or JP can be added later at no install cost |
| **A missing glyph is a build error that names the character** (`assets/latex/chitragupta-lualatex.tex`) | `\tracinglostchars=3` alone makes LuaLaTeX fail, but its message is on a line pandoc drops; a `glyph_not_found` callback raises `! Missing character: There is no X (U+XXXX) ...`, which pandoc shows and `_cli.py` parses |
| **The `.bib` path is closed; Lua in the author's own TeX is an accepted residual** | Maintainer's decision. `assets/pandoc/bib_raw_tex_as_text.lua`, after `--citeproc`, prints raw TeX in the reference list and the citations as text. No Lua confinement, no Landlock (possible follow-ups, not implemented). See "The accepted residual" |
| **`chitragupta-unicode.sty` keeps shipping beside `tex` and `--fragment` output; a `pdf` render stops loading it** | Under LuaLaTeX it is a no-op (`\ifPDFTeX`). A fragment is `\input` by the user's document, which may be pdflatex |
| **`content/unicode-extra.tex` goes in behind a shim** defining `\DeclareUnicodeCharacter` on `newunicodechar` where the kernel lacks it | Measured: a #948 overlay line stopped a LuaLaTeX build with `Undefined control sequence`. An `\ifPDFTeX` wrap would have made the overlay a silent no-op on our own renders; the shim makes the same line print on both engines, so the `[unicode]` hint's fix works |
| **STIX Two by pinned, checksummed download** (`install_stix_two`, tag `v2.13b171`) | 2.0 MiB of five OTFs, against 1.65 GiB for `texlive-fonts-extra`, the only Debian package with it. Same pattern as Vale and actionlint |
| **MINOR bump to 6.132.0** | New shipped assets and module, new installer stage; no config key, no CLI change |

## 🧾 Measured answers to the issue's open questions

Measured on Ubuntu 24.04.3, **TeX Live 2023/Debian** (LuaHBTeX 1.17.0,
XeTeX 0.999995, luaotfload 3.26), pandoc 3.6.4. CI's `ubuntu-latest`
is the same release. Nothing was measured on TeX Live 2024 or later.
There was no root in the container, so `texlive-luatex`,
`texlive-xetex` and the font packages were unpacked with
`apt-get download` and `dpkg -x` into a scratch tree, which stands in
for `apt-get install`.

### Q0: why `fontspec` could not load Latin Modern under `lualatex`

`texlive-luatex` was not installed, so `luaotfload` was missing:

```console
$ lualatex -halt-on-error t.tex   # \usepackage{fontspec}, "Hello"
[\directlua]:1: module 'luaotfload-main' not found:
Error in luaotfload: reverting to OT1
! Font \TU/lmr/m/n/10=[lmroman10-regular]:+tlig; at 10pt not loadable: metric d
```

`lualatex` itself is in `texlive-binaries` and its format in
`texlive-latex-base`, which is why the binary worked with no font
loader. Installing `texlive-luatex` fixes it; nothing was wrong with
`fonts-lmodern`. The first render builds luaotfload's font database in
the invoking user's `TEXMFVAR` (1.8 s for 1,110 font files here), so
the installer, which runs under sudo, does not try to warm it.
`render()` now probes for `luaotfload.sty` and says which package is
missing (`_require_pdf_toolchain`).

Two traps found on the way: `dpkg -l` listed `fonts-noto-core` as
installed while its font directory was empty, so `chitragupta doctor`
asks `luaotfload-tool --find` instead; and `luaotfload-tool --find`
exits 0 for a font it cannot find, so `doctor` reads its message.

### Q1: `\tracinglostchars=3`

Fatal on both engines, through pandoc's template (`header-includes`
and `-H`): exit 43, no PDF. XeLaTeX's message names the character.
LuaLaTeX's does too, but on a line pandoc drops, so the user saw only
`Fatal error occurred`. The `glyph_not_found` callback fixes that.
Without the setting both engines **succeed** with a hole in the PDF and
a log warning. No false positives on the 170-page benchmark, on tabs in
prose or code, or on any of the 11 regression drafts. Only the first
missing character is named, because the build stops there; the hint
says "the first such character". Unifont covers nearly the whole BMP,
so the test fixture for "no font has it" is unassigned U+2FFFD.

### Q2: Lua file access under `openin_any=p` and `-no-shell-escape`

kpathsea's `openin_any`/`openout_any` fence TeX's own `\input` and
`\openout`. They do not fence Lua. With the #823 settings, LuaLaTeX's
`io.open` and `io.lines` read any file the user can read,
`io.open(..., "w")` writes anywhere the user can write, and `os.getenv`
returns the environment. `--safer` breaks luaotfload and still lets
`io.lines` read. `\csname`-built equivalents of `\directlua` run too, so
no text blocklist catches it.

**Citeproc does not escape.** A `.bib` title of
`\directlua{tex.print(io.open("/abs/secret"):read("*l"))}` reaches
LuaLaTeX as raw LaTeX: the secret was typeset into the reference list,
exit 0. The same inside `$...$` reaches it too, because pandoc's reader
keeps a math node's source verbatim. pdflatex and XeLaTeX fail on it
with `Undefined control sequence`.

**What ships.** `bib_raw_tex_as_text.lua`, straight after `--citeproc`
and before `breakable_inline_code.lua`, turns raw TeX in `Div#refs` and
in every Cite into code spans, and does the same for a math node whose
source holds a code-running or file-reaching primitive (`\directlua`,
`\csname`, `\input`, `\write` and the like); plain math is left as math.
Order matters twice: before the breakable filter, or its `\penalty0`
break nodes print as visible text in a `.bib` `\texttt`; and it handles
`Math`, not only `RawInline`, or a `$\directlua{...}$` slips past.
Measured: the `\directlua` title, in text and inside `$...$`, prints
literally and nothing is read or written; `$\alpha \leq \beta$` stays
math; and a normal title (`{\"U}ber $\alpha \leq \beta$ ... \emph{Lévy}
... \texttt{src/main.py} ... {CO}\textsubscript{2}`) gives
**byte-identical** LaTeX with and without this filter when both run with
the breakable filter. Converting the `.bib` to CSL JSON first was
rejected: it silently drops the command (`"title": "See  here"`), which
changes what the reference says. The filter also closes #823's "out of
scope: `tex` output" gap for the reference list.

**Denylist, not allowlist, for the math case.** The branch review
recommended keeping a math node only if every command in it is on a list
of known-safe math commands. A denylist of dangerous primitives was
chosen instead, for one reason the allowlist cannot match: a real
bibliography's math title carries arbitrary math commands, and an
allowlist would render any it did not name as verbatim source. The
denylist is complete for this threat under `-no-shell-escape`: the only
primitives that run Lua are `\directlua` and `\latelua`; the only way to
invoke a control sequence whose name is not spelled out (and so caught)
is `\csname`; and `^^5c`, TeX's input escape that becomes a backslash
before any control word forms, is matched directly, since no real math
title uses the `^^` notation. `\luafunction`/`\luafunctioncall` are
listed too, though they only call an already-registered function and
nothing can register one once `\directlua` is blocked. The `^^5c` route
was a gap in the first version of this filter, found in branch review and
confirmed to execute -- the read secret came back typeset in math
italic, which an ASCII check missed. Verified with six crafted titles
(plain, `\csname`-built, `\latelua`, `\let`-aliased, `\uccode`/`\lowercase`,
`^^5c`), none of which read a file through a real lualatex compile, the
leak check folding math-italic output back to ASCII first
(`tests/test_render_output_bib_raw_tex.py`). The allowlist tradeoff is
recorded for the maintainer to revisit if a stricter rule is wanted.

### The accepted residual

TeX in a draft body or a `figures/*.tex` file can run Lua under
LuaLaTeX, which reads any file the user can read, writes anywhere they
can write, and reads environment variables. The maintainer accepted
this: a draft and its figures are the author's own text, and rendering
one is running it. Only the `.bib` path, a collaborator's text, is
closed. TeX's own `\input` of an absolute path is still refused by
`openin_any=p` (tested on LuaLaTeX). `docs/SECURITY.md` states the
residual for users.

Possible follow-ups, deliberately not implemented: a Lua confinement
inside LuaTeX (the spike prototyped one; it was not adopted, and a
blocklist inside one interpreter is hard to make complete), and running
the engine under a Landlock ruleset (available here: Linux 5.15,
Landlock ABI 1). `bwrap` cannot create namespaces on this host, as on
any Ubuntu 24.04 with AppArmor's unprivileged-userns restriction.

### Q3: build time

No book exists in this repository; a book needs its owner's ledger. The
benchmark document is the repository's four sample drafts
(`content/drafts/digital-twins-for-software-engineers/*.md`) repeated
×10 under `# Part k` headings: 63,050 words, about 170 pages. Each side
runs its own real `_pandoc_command` (origin/main's for pdflatex, this
branch's for LuaLaTeX), so the argv is exactly what users get. pandoc
ran two LaTeX passes in every case. Cold deletes luaotfload's cache
first.

| Configuration | Pages | Cold (s) | Warm, median of 3 (s) |
| --- | --- | --- | --- |
| pdflatex (origin/main) | 170 | n/a | 5.20 (5.21, 5.19, 5.20) |
| LuaLaTeX, this branch | 166 | 38.57 | 27.28 (27.24, 27.34, 27.28) |
| the same, plus a Unicode probe paragraph per chapter | 168 | 38.57 | 27.39 (27.39, 27.31, 27.42) |

About 5× slower warm. A render is a deliberate action and the drafting
skills render once per draft, so the maintainer accepted the cost.
Linear extrapolation to the 428-page book `style_typeset.py` mentions:
about 70 s warm.

### Q4: fonts

Probe draft: `CO₂ 𝑡 ℝ ≤ α 𝒶 H₂O 5 µm m² ½ Ⅳ ①`, `తెలుగు`, `王小明`,
`हिन्दी`, the same in math, bold and italic, and in code.

| Pair (text + math) | Missing | Where Ubuntu 24.04 has it |
| --- | --- | --- |
| Latin Modern + LM Math | `₂`, `𝒶` | `fonts-lmodern` |
| New Computer Modern + NewCM Math | `₂` | `texlive-fonts-extra` only |
| **STIX Two Text + STIX Two Math** | **none** | `texlive-fonts-extra` only, or the 2.0 MiB OTF release |
| STIX (1.1) + STIX Math | `₂`, math `𝒶` | `fonts-stix` |
| Noto Serif + Noto Sans Math | math `𝒶` | `fonts-noto-core` |

The STIX Two render, checked by eye at 150 dpi: `CO₂` has a real
subscript in text, heading and bold. తెలుగు is shaped (HarfBuzz),
हिन्दी has its `ि` reordered, 王小明 is Noto Serif CJK SC, and
`pdftotext` returns every line as written. Limit: bold or italic Telugu
and CJK fall back to the regular weight, because a fallback is one font,
not a family.

**Installer size** (apt `Installed-Size`, MiB): `texlive-luatex` 43.8,
`fonts-noto-core` 41.6, `fonts-noto-cjk` 88.9, `fonts-unifont` 31.8,
STIX Two 2.0 by download: **208 MiB**, plus `fonts-dejavu-core` (2.2)
where it is not already present.

## 🔁 Regression proof: drafts that rendered before still render

**Every draft in the repository**, rendered by origin/main's code
(pdflatex) and by this branch (LuaLaTeX), compared on `pdftotext`:

- the seven drafts of the three example projects (`docs/examples/sample-project`,
  `codex`, `opencode`), through the real `chitragupta draft render`
  after a real `corpus sync` of each project's committed `.bib` and
  PDFs: citations, reference lists, tables, a fenced code block with
  fvextra wrapping, inline math and a LaTeX (`.tex`) draft;
- the repository's own four drafts in `content/drafts/`, which have no
  ledger or `.bib` in a checkout, so `render()` refuses their citekeys
  on both sides. They were compared at the pandoc level, each side
  through its own `_pandoc_command` with an empty `.bib`.

All 11 compile on both. Compared as character streams, with only
engine-dependent differences normalised (NFKC, so unicode-math's
Mathematical Italic `𝑚` equals the ASCII `m` pdflatex extracts;
hyphen variants and whitespace removed, because line breaks move with
the font and LuaLaTeX extracts an ASCII hyphen as U+2010; page numbers;
fvextra's continuation mark, `,→` under pdflatex and `↪` under
LuaLaTeX), **7 of 11 are identical**. The other four contain exactly
the same characters in a different order: a float caption or a citation
marker lands on the other side of a page break, and a table cell is
extracted in another order. In two of those, LuaLaTeX additionally
prints an over-long unresolved citekey in full where pdflatex clipped it
at the margin (unresolved only because those drafts have no `.bib`
here). Page counts match in 9 of 11; one draft grows from 2 to 3 pages.

**Every one of the 1,873 characters** of `chitragupta-unicode.sty`
renders through `render()` with `\tracinglostchars=3`
(`tests/test_render_output_fonts.py`). With Unifont removed from the
chain, the same test fails naming U+A7F2, so it has teeth.

TikZ figures, wide tables, long code lines and the caption tests run on
LuaLaTeX in the suite (`tests/test_render_output.py`'s real-render
classes), as does #823's read test: TeX's own `\input` of an absolute
path is refused with `openin_any`.

## 🗺 What changed, by file

| File | Change |
| --- | --- |
| `chitragupta/pdf_fonts.py` (new) | font names and the fallback chain, standard library only, so `doctor` can read them |
| `chitragupta/pdf_fonts.py` | the font names, the fallback chain, and `latex_fonts()`, which writes the `\setmainfont`/`add_fallback` block the header embeds -- written out rather than passed as pandoc `mainfontfallback` variables, because apt's pandoc 3.1.3 on Ubuntu 24.04 (CI's) has no such template variable and dropped the chain silently |
| `chitragupta/render_output/_pandoc.py` | `--pdf-engine lualatex`, the strict-glyph-and-fonts header last, the `.bib` filter right after `--citeproc` (before the breakable filter), `_require_pdf_toolchain`; the `.sty` directory off `TEXINPUTS` |
| `chitragupta/render_output/_unicode.py` | no `.sty` for `pdf`; the overlay behind the `\DeclareUnicodeCharacter` shim |
| `chitragupta/render_output/_cli.py` | `[unicode]` hint parses the LuaLaTeX message and gives fixes that work there |
| `chitragupta/render_output/__init__.py` | `_require_pdf_toolchain()` for `pdf` |
| `chitragupta/doctor.py` | `lualatex` in `BINARIES`; a check per font family |
| `assets/latex/chitragupta-lualatex.tex` (new), `assets/pandoc/bib_raw_tex_as_text.lua` (new), both READMEs | the header and the filter |
| `scripts/install_full_pipeline.sh` | `texlive-luatex`, `fonts-noto-core`, `fonts-noto-cjk`, `fonts-dejavu-core`, `fonts-unifont`; `install_stix_two` and a `stix-two` stage |
| `docs/SECURITY.md`, `docs/RENDERING-FLOW.md`, `docs/CLI.md`, `docs/ARCHITECTURE.md`, the book-assembler and thesis-chapter-writer skills (three harness copies each) | engine, fonts, residual, and "LuaLaTeX is recommended but the user's engine is theirs" |
| tests | `test_render_output_bib_raw_tex.py`, `test_render_output_fonts.py` (new); real-render gates moved to `lualatex_available`; #823's `.bib` test now asserts the text is printed, and a new one asserts TeX's own absolute `\input` is still refused; `_unicode`, CLI and `doctor` tests updated |

CI needs no workflow change: the Linux leg runs
`install_full_pipeline.sh all`, which now installs the engine and
fonts. The Windows leg installs no `os-deps`, and its render tests skip
on `lualatex_available` exactly as they skipped on `pdflatex_available`.

## 🚧 Out of scope, and why it is safe

- **The figure-layout probe stays on pdflatex.** It measures TikZ node
  boxes in Latin Modern, a few percent narrower than STIX Two, so its
  overlap verdict is approximate for a STIX Two render. It keeps
  `openin_any=p` and `-no-shell-escape`, and pdflatex runs no Lua.
- **`tex` output and `--fragment`** are compiled by someone else's
  engine. The `.bib` filter still applies to a `tex` output's reference
  list, so a `.bib` command reaches it as visible text.
- **Lua confinement and Landlock**: see "The accepted residual".

## 🔁 Reproducing

Everything ran in `/tmp/s996` without root: `apt-get download` and
`dpkg -x` for the TeX and font packages, `TEXMFAUXTREES` pointing at
the unpacked trees, a scratch `TEXMFVAR`, and `FONTCONFIG_FILE` adding
the font tree. origin/main's code ran from a `git archive` extract on
`PYTHONPATH`, from a working directory outside the worktree (inside it,
`python -c` puts the worktree's own package first and silently runs the
branch instead, which an early benchmark run did). The scratch scripts
are not committed; every number they produced is above.
