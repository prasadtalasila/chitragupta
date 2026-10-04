# #996: render our own PDFs with a Unicode TeX engine

Status: **spike done, build not started.** Written 2026-10-04 against
`origin/main` @ 7ef6086 (6.130.0), for
[#996](https://github.com/prasadtalasila/chitragupta/issues/996). This
file records the measurements that answer the issue's four open
questions and the plan for the PR that makes the switch. That PR is
built **on top of #948's**
(`plans/948-latex-unicode-characters.md`, NFC instead of NFKC, the
generated `chitragupta-unicode.sty`, the `content/unicode-extra.tex`
overlay). #948 merges first.

**Written for** whoever implements #996: someone who can read Python
and LaTeX and has read `chitragupta/render_output/_pandoc.py` and the
plan for #823 (`plans/823-tex-read-hardening.md`).

**Assumed:** #948 has merged, so `_unicode.py`,
`assets/latex/chitragupta-unicode.sty` and the `[unicode]` hint in
`_cli.py` exist. The worktree setup and the shipping cycle in
`DEVELOPER-AGENTS.md` (TDD, 100% line and branch coverage, the
`check_local.sh` lint job, MINOR bump for a new config key).

**Not covered here:**

- `--fragment` output and the user's own thesis or book preamble. They
  pick their own engine. #948's `.sty` keeps serving pdflatex there.
- The figure-layout probe (`review/figure_layout/_probe.py`) and the
  bench compile. They stay on pdflatex in this PR. "Out of scope" below
  explains why that is safe and what it costs.
- Tagged (accessible) PDF. LuaLaTeX is where that work lands, but this
  PR does not turn it on.

## 🧾 The answers in one table

Measured in this container: Ubuntu 24.04.3, **TeX Live 2023/Debian**
(`texlive-binaries` 2023.20230311, `texlive-luatex` and `texlive-xetex`
2023.20240207-1), LuaHBTeX 1.17.0, XeTeX 0.999995, luaotfload 3.26
(2023-08-31), pandoc 3.6.4. CI's `ubuntu-latest` is the same Ubuntu
release, so it gets the same TeX Live. Nothing here was measured on TeX
Live 2024 or later.

| # | Question | Answer |
| --- | --- | --- |
| 0 | Why can `fontspec` not load Latin Modern under `lualatex` here? | `texlive-luatex` is not installed, so `luaotfload` is missing. The engine is in `texlive-binaries` and the format in `texlive-latex-base`; the font loader is not. Installing that one package fixes it. Nothing is wrong with `fonts-lmodern` |
| 1 | Does `\tracinglostchars=3` make a missing glyph fatal, through pandoc's template? | Yes on both engines, via `--variable header-includes=` and via `-H`: exit 43, no PDF. XeLaTeX's error names the character. LuaLaTeX's does too, but on a line pandoc drops, so the user sees only `Fatal error occurred`. A 6-line `glyph_not_found` callback makes LuaLaTeX name it. Glyphs found through a fallback font do not trip it |
| 2 | Can a document, or a `.bib` field, reach Lua `io` under `openin_any=p` and `-no-shell-escape`? | **Yes, both.** `io.open` and `io.lines` read any file the user can read, and `io.open(..., "w")` writes anywhere the user can write. kpathsea's `openin_any`/`openout_any` cover TeX's own `\input` and `\openout`, not Lua. Citeproc does **not** escape: a `.bib` title of `\directlua{...}` reaches LuaLaTeX as raw LaTeX and runs. `--safer` breaks `luaotfload` and still lets `io.lines` read. XeLaTeX has no Lua, but it has a smaller hole of its own: it embeds an image or PDF named by absolute path, which pdflatex and LuaLaTeX refuse. **This blocks LuaLaTeX until the two mitigations below ship with it** |
| 3 | Build time? | 170-page, 63k-word document built from the repo's four sample drafts ×10, same pandoc argv as `_pandoc.py`, two LaTeX passes, warm median of 3: pdflatex **5.3 s**, XeLaTeX **7.1 s**, LuaLaTeX **16.0 s** (cold cache 18.3 s). With the recommended fonts, fallback chain, strict glyphs and Lua confinement, LuaLaTeX takes **25.0 s** (cold 32.5 s), and XeLaTeX with STIX Two takes 7.7 s |
| 4 | Font pair? | **STIX Two Text + STIX Two Math**, falling back to Noto Serif Telugu, Noto Serif Devanagari and Noto Serif CJK SC. It is the only pair that rendered every probe character in text and math, including `₂` and math `𝒶`. Mono stays Latin Modern Mono, with a DejaVu Sans Mono fallback. Adds about **176 MiB** (apt `Installed-Size`): `texlive-luatex` 43.8 MiB, `fonts-noto-core` 41.6 MiB, `fonts-noto-cjk` 88.9 MiB, and 2.0 MiB of STIX Two OTF fetched by hand, because Ubuntu 24.04 ships STIX Two only inside the 1.65 GiB `texlive-fonts-extra` |

**Recommendation: LuaLaTeX, with STIX Two and a Noto fallback chain,
on the condition that two mitigations ship in the same PR**: a pandoc
filter that prints any raw TeX in the reference list as literal text,
and a Lua confinement that limits Lua's file and process access to what
TeX itself may touch. Both are prototyped and measured below. If review
does not accept the confinement, use XeLaTeX instead. It needs only
the reference-list filter plus a refusal of absolute image paths (see
"Images" under Q2), but measured here its per-script font switching
was fragile, so it gives up most of what #996 is for.

## 🔬 Q0: why `fontspec` could not load Latin Modern

```console
$ kpsewhich luaotfload.sty luaotfload-main.lua    # nothing
$ lualatex -halt-on-error t.tex   # \usepackage{fontspec}, "Hello"
[\directlua]:1: module 'luaotfload-main' not found:
Error in luaotfload: reverting to OT1
! Font \TU/lmr/m/n/10=[lmroman10-regular]:+tlig; at 10pt not loadable: metric d
```

`texlive-luatex` (Debian/Ubuntu) owns `luaotfload`, `luaotfload-tool`,
`lualatex-math` and `luacode`. `lualatex` itself is in `texlive-binaries`,
and its format in `texlive-latex-base`, which is why the issue saw a
working binary with no font loader. There was no root in this
container, so the package was unpacked into a scratch tree instead of
installed:

```bash
apt-get download texlive-luatex texlive-xetex      # 25.8 + 10.8 MB to download
dpkg -x texlive-luatex_*.deb root && dpkg -x texlive-xetex_*.deb root
export TEXMFAUXTREES=$PWD/root/usr/share/texlive/texmf-dist,  TEXMFVAR=$PWD/var
fmtutil-user --cnffile root/var/lib/tex-common/fmtutil-cnf/texlive/texlive-xetex.cnf \
  --byfmt xelatex                                  # xelatex.fmt; lualatex.fmt already existed
```

After that, the same file builds on both engines and embeds
`LMRoman10-Regular` (`pdffonts`). On the first run luaotfload builds its
font-name database:
`luaotfload | db : Font names database not found, generating new one.`
That took 1.8 s for 1,110 font files, CJK included
(`luaotfload-tool --update --force`).

**What the installer has to do:** add `texlive-luatex` to `os-deps`'
`apt-get install`. Do **not** run `luaotfload-tool --update` from the
installer. The database lives in the *invoking user's* `TEXMFVAR`
(`~/.texlive2023/texmf-var/luatex-cache`), and `os-deps` runs under
`sudo`, so it would build root's copy and leave the user's cold. The
first render builds it, at about 2 s on this font set.

The XeLaTeX check: `xetex` is in `texlive-binaries` and was present, but
`xelatex` is not. The `xelatex` symlink and `fontspec`'s XeTeX side
come with `texlive-xetex`, which pulls in `teckit` and `tipa` (21.2 MiB
installed in all).

One installer trap found on the way: `dpkg -l` here lists
`fonts-noto-core` as installed, but `/usr/share/fonts/truetype/noto/` is
empty. Whatever probes for fonts (the installer's post-check,
`chitragupta doctor`) must ask the font system, with
`luaotfload-tool --find="Noto Serif CJK SC"` or
`fc-list ':family=STIX Two Text'`. It must not trust `dpkg`.

## 🔬 Q1: `\tracinglostchars=3`

Fixture: one line, `Before snowman: ☃ after.`, which Latin Modern
lacks.

| Engine | Plain LaTeX, no setting | `\tracinglostchars=3` | Through pandoc (`--variable header-includes=` or `-H`) |
| --- | --- | --- | --- |
| XeLaTeX | exit 0, PDF written, log warning only | exit 1, `! Missing character: There is no ☃ (U+2603) in font [lmroman10-regular]:mapping=tex-text;.` at `l.5` | exit 43, the same message in pandoc's error |
| LuaLaTeX | exit 0, PDF written, log warning only | exit 1. The `Missing character ... (U+2603)` line is not `!`-prefixed and comes before `! ==> Fatal error occurred`, raised at shipout (`l.6 \end{document}`) | exit 43, **pandoc shows only `! ==> Fatal error occurred, no output PDF file produced!`**. The naming line is in `--verbose` output only |

pandoc's own run also shows that, without the setting, both engines
**succeed** with a hole in the PDF. pandoc surfaces only a `[WARNING]
Missing character` on stderr, and `_run_pandoc` forwards that as a
`[pandoc]` line. That is the silent gap #996 wants closed.

The naming fix for LuaLaTeX. Measured, pandoc then reports
`! Missing character U+2603 (☃) in font [lmroman12-regular]:+tlig;.`:

```latex
\directlua{
  luatexbase.add_to_callback("glyph_not_found", function(id, char)
    tex.error(string.format("Missing character U+\csstring\%04X (\csstring\%s) in font \csstring\%s",
      char, utf8.char(char), font.getfont(id) and font.getfont(id).name or id))
  end, "chitragupta.lostchar")
}
```

Further measurements:

- **With a fallback chain** (Q4's STIX Two + Noto), everything in the
  probe resolves and the build passes. Ogham `ᚁ` (U+1681) and `🦩`
  (U+1F9A9), which no installed font has, fail it. `☃` is *not* a good
  "missing" fixture once Noto CJK is installed, because Noto Serif CJK SC
  has it. Use U+1681 in tests.
- **No false positives** on the 170-page benchmark document, or on a
  draft with literal tabs in prose, an inline code span and a fenced
  block. pandoc expands tabs before LaTeX sees them.
- **Only the first** missing character is named, because the build
  stops there. The `[unicode]` hint must say "the first character".
- #948's hint regex (`Unicode character (.) \(U\+...\)`) matches
  pdflatex's wording only. The new engine needs the two shapes above.

## 🔬 Q2: Lua file access under `openin_any=p` and `-no-shell-escape`

Probe: a `.lua` file run from the document body, as `\directlua` would
run it inline. Secret at `/tmp/s996/outside/secret.txt`, outside the
working directory. `openin_any` defaults to `a` in this TeX Live, and
`openout_any` to `p`.

| Probe | Defaults | `openin_any=p` + `-no-shell-escape` (#823) | the same + `--safer` |
| --- | --- | --- | --- |
| `io.open("/abs/secret")` | **reads** | **reads** | refused |
| `io.open("../outside/secret")` | **reads** | **reads** | refused |
| `io.open(".dotfile")` | **reads** | **reads** | refused |
| `io.lines("/abs/secret")` | **reads** | **reads** | **reads** |
| `io.open("/etc/passwd")` | **reads** | **reads** | refused |
| `io.open("/abs/x", "w")` | **writes** | **writes** | refused |
| `io.popen`, `os.execute` | refused | refused | refused |
| `os.getenv("HOME")` | returned | returned | returned |
| `lfs.dir("/abs")` | lists | lists | lists |

For comparison, TeX's own
`\immediate\openout5=/tmp/s996/outside/texwrite.txt` under the same
settings is refused: `lualatex: Not writing to ... (openout_any = p)`.
So the hole is the Lua side only. It is wider than reading: an absolute
write is enough to plant `~/.bashrc` or anything else the user runs
later. `os.getenv` hands any secret in the environment (API keys,
tokens) to the document, which can typeset it into a PDF that then gets
shared.

**From a `.bib` field.** Measured with the existing `smith_2024` test
fixture key and a title of
`See \directlua{tex.print(io.open("/tmp/s996/outside/secret.txt"):read("*l"))} here`.
`pandoc x.md --citeproc --csl ieee.csl --bibliography lua.bib -t latex`
emits the command unescaped:

```latex
\CSLRightInline{{``See
\directlua{tex.print(io.open("/tmp/s996/outside/secret.txt"):read("*l"))}
here,''} 2024.}
```

So citeproc does **not** escape it. Through the `_pandoc.py` argv
(`openin_any=p`, `--pdf-engine-opt=-no-shell-escape`, `TEXINPUTS`):

| `.bib` title | pdflatex | XeLaTeX | LuaLaTeX |
| --- | --- | --- | --- |
| clean | exit 0 | exit 0 | exit 0 |
| `\directlua{... io.open(...):read ...}` | exit 43, `Undefined control sequence` | exit 43, same | **exit 0, secret in the PDF** |
| `\directlua{for l in io.lines(...) ...}` | exit 43 | exit 43 | **exit 0, secret in the PDF** |
| `\directlua{io.open("/abs/x","w") ...}` | exit 43 | exit 43 | **exit 0, file written outside** |

The draft body is the same channel. A draft paragraph containing
`\directlua{for l in io.lines("/abs/secret") do tex.print(l) end}`
renders with the secret in the PDF. So does a `figures/*.tex` file,
which is TeX by design and, in a shared tree, someone else's (#823's
threat model).

**Images: a separate hole, on XeLaTeX only.** A raw block
`\includegraphics[width=3cm]{/tmp/s996/outside/private.pdf}`, with
`graphicx` loaded, under the same settings:

| Engine | Result |
| --- | --- |
| pdflatex | exit 43, `File '/tmp/s996/outside/private.pdf' not found` |
| LuaLaTeX | exit 43, the same from `luatex.def` |
| XeLaTeX | **exit 0. The outside PDF's page is embedded in the output** (`pdftotext` shows its text). XeTeX's own probes print `Not reading from ... (openin_any = p)` and LaTeX warns `File ... not found`, but `xdvipdfmx`, a separate program, reads the file anyway |

So XeLaTeX is not free of regressions against #823 either. Any image
or PDF the user can read is reachable from a `.bib` field, the draft
or a figure file. The reference-list filter closes the `.bib` path.
The draft and figure paths would need a pre-render refusal of absolute
`\includegraphics` targets.

**A blocklist on the text does not work.**
`\csname tex_directlua:D\endcsname{...}` and
`\csname direct\string lua\endcsname{...}` both run Lua from the
document body. Measured: the first printed the secret.

### What closes it, measured

1. **Reference-list filter: done after citeproc, prints raw TeX as
   text.** An 18-line Lua filter placed after `--citeproc` on the pandoc
   command line walks `Div#refs` and turns every `RawInline`/`RawBlock`
   of format `latex`/`tex` into `Code`/`CodeBlock`. Measured:
   - the `\directlua` title prints literally as
     `\directlua{tex.print(...)}`, exit 0, no secret, no file written.
     The user sees what their `.bib` says.
   - a normal title,
     `{\"U}ber $\alpha$-stable \emph{Lévy} flights in H$_2$O and {CO}\textsubscript{2}`,
     produces **byte-identical** LaTeX with and without the filter,
     because pandoc's BibTeX reader has already parsed those into AST
     nodes, not raw TeX.
   - converting the `.bib` to CSL JSON first (`pandoc -t csljson`) also
     stops it, but silently drops the command (`"title": "See  here"`).
     That changes what the reference says, so it was rejected for the
     same reason #948 rejected NFKC.

   This also closes #823's "out of scope: `tex` output" item for the
   reference list. The same `\input{/abs}` title becomes literal text in
   a `.tex` output too.
2. **Lua confinement: installed from the header, before the body.** A
   prototype (91 lines of Lua) loaded through `-H` after the template's
   font setup. It wraps `io.open`, `io.lines`, `io.input`,
   `io.output`, `loadfile`, `dofile` and the `lfs` path functions to
   allow reads only under the working directory, `TEXINPUTS`, the TEXMF
   trees (`kpse.expand_path("$TEXMF")`), `TEXMFVAR` and the system font
   directories, and writes only under the working directory and the
   luaotfload cache. It refuses `..` and dot-components. It stubs
   `io.popen`, `os.execute`, `os.rename`, `package.loadlib` and
   `os.getenv` (allow-list), forces `load` to text mode (no bytecode),
   and removes `debug` (`debug = nil`, `package.loaded.debug = nil`).
   Measured:
   - every row of the probe table above is refused, `os.getenv("HOME")`
     returns `nil`, `debug.getupvalue(io.open, 1)` and `require("debug")`
     fail, and bytecode `load` returns `nil`.
   - both malicious `.bib` files now **fail closed** (exit 43, no PDF,
     no file written) even without the filter.
   - the full font setup still works with it: the STIX Two + Noto chain
     loads its fallback fonts lazily *in the body*, after the
     confinement, and the probe renders identically. That holds from a
     **cold** luaotfload cache (16.6 s), so cache writes still work, and
     warm (9.5 s).
   - residuals it does not cover: `kpse.readable_file("/abs")` still
     answers whether a file exists. `os.tmpdir()` still creates a
     directory under `/tmp`. `fontloader`/`img.scan` take absolute
     paths, but only parse fonts and images. `img.scan` of a non-image
     kills the build. `ffi` and `socket` are already unavailable
     without shell escape.

   This is defence in depth, not a sandbox. A blocklist inside one Lua
   state can be wrong in ways a test does not show, so it gets its own
   review focus and its own red-team tests (Task 3). A process sandbox
   was checked and is not available: `bwrap` exists here but fails with
   `No permissions to create new namespace`, as it does on any Ubuntu
   24.04 host with AppArmor's unprivileged-userns restriction.

## 🔬 Q3: build time

No book exists in this repository. A book is the user's own content and
needs their ledger. So the benchmark document is generated from the
repository's own four sample drafts
(`content/drafts/digital-twins-for-software-engineers/*.md`) repeated
×10, each copy under a `# Part k` heading: **63,050 words, 170 pages**.
The drafts' own citekeys pass through unchanged against an empty
`.bib`. citeproc warns and prints the key, which costs the same
two-pass build a resolved bibliography would. No key was added or
changed. Every run uses `_pandoc.py`'s argv: `--standalone`,
documentclass/fontsize/papersize/geometry, the breakable-inline-code
filter, the `LTcapwidth` header, the `fvextra` header (the drafts have
code blocks), `--citeproc --csl ieee.csl`,
`--pdf-engine-opt=-no-shell-escape`, `openin_any=p` and `TEXINPUTS`.
pandoc ran LaTeX twice in every case (`[makePDF] Rerun needed`). The
host has 48 cores, but each run is single-threaded.

| Configuration | Pages | Cold (s) | Warm median of 3 (s) |
| --- | --- | --- | --- |
| pdflatex, lmodern (today) | 170 | n/a | 5.25 (5.24, 5.27, 5.25) |
| XeLaTeX, Latin Modern via fontspec | 170 | n/a | 7.06 (6.97, 7.06, 7.21) |
| LuaLaTeX, Latin Modern via fontspec | 170 | 18.33 | 16.02 (15.98, 16.07, 16.02) |
| XeLaTeX, STIX Two | 170 | n/a | 7.66 (7.66, 7.64, 7.79) |
| LuaLaTeX, STIX Two + Noto chain + strict glyphs + confinement | 168 | 32.49 | 25.02 (24.94, 25.02, 25.23) |
| the same, plus one Unicode probe paragraph per chapter | 170 | 32.55 | 24.90 (24.95, 24.90, 24.33) |

"Cold" deletes `TEXMFVAR/luatex-cache` first. It covers the font-name
database and each font's first conversion. The issue expected minutes;
on this font set (1,110 files) it costs 2 to 8 s. A host with
`texlive-fonts-extra`'s thousands of fonts will take longer for its
first run. That was not measured. Linear extrapolation to the 428-page
book `style_typeset.py` mentions gives about 60 s warm on the
recommended configuration, against about 13 s on pdflatex today. That
is slower, but a render is a deliberate action, and the drafting
skills render once per draft.

## 🔬 Q4: fonts

Probe draft, rendered on LuaLaTeX through the `_pandoc.py` argv with
pandoc's own `mainfont`, `mathfont` and `mainfontfallback` variables
(pandoc 3.6's template emits `luaotfload.add_fallback` for the last):

```markdown
# Probe: CO₂ and తెలుగు
Text: CO₂ 𝑡 ℝ ≤ α 𝒶 H₂O 5 µm m² ½ Ⅳ ①.
Telugu word: తెలుగు. Chinese name: 王小明. Devanagari: हिन्दी.
Math: $𝑡 ≤ α$, $x ∈ ℝ$, $𝒶 + \mathbb{R}$, $\alpha_2$.
Bold **CO₂ తెలుగు 王小明** and italic *𝑡 ℝ α*.
Code `x ≤ y`.
```

Each fallback chain was the math font, then
`Noto Serif Telugu:mode=harf;script=telu`,
`Noto Serif Devanagari:mode=harf;script=dev2` and
`Noto Serif CJK SC:mode=harf`. Mono was Latin Modern Mono with a
`DejaVu Sans Mono:mode=node` fallback. Missing glyphs come from the
log:

| Pair (text + math) | Missing | Where the fonts come from on Ubuntu 24.04 |
| --- | --- | --- |
| Latin Modern Roman + Latin Modern Math | `₂` (text, regular and bold), `𝒶` (text and math) | `fonts-lmodern`, installed today |
| Latin Modern + LM Math, with STIX Two Text/Math first in the fallback chain | `𝒶` in math only (LM Math has no lowercase script) | as above, plus STIX Two |
| New Computer Modern Book + NewCM Math | `₂` | `texlive-fonts-extra` only (1.65 GiB) |
| **STIX Two Text + STIX Two Math** | **none** | `texlive-fonts-extra` only, or the 2.0 MiB OTF release |
| STIX (1.1) + STIX Math | `₂`, math `𝒶` | `fonts-stix`, 2.7 MiB |
| Noto Serif + Noto Sans Math | math `𝒶`: set in Latin Modern Math, which was still embedded. Not diagnosed | `fonts-noto-core` |

The STIX Two render, checked by eye at 150 dpi: `CO₂` has a real
subscript in text, heading and bold. తెలుగు is shaped correctly
(HarfBuzz, vowel signs attached), and हिन्दी has its `ि` reordered
before the consonant. 王小明 is set in Noto Serif CJK SC. Math is in
STIX Two Math. `pdftotext` gives every line back exactly as written
(`Text: CO₂ 𝑡 ℝ ≤ α 𝒶 H₂O 5 µm m² ½ Ⅳ ①.`), where pdflatex with #948's
`.sty` gives `CO2`. Three limits:

- **Bold or italic Telugu and CJK fall back to the regular weight.**
  A fallback is one font, not a family. Acceptable for author names and
  quoted titles. Adding the bold faces to a separate `RawFeature`
  chain for bold is a later refinement.
- **STIX Two Text lacks `≤`, `Ⅳ`, `①`.** STIX Two Math, which comes
  first in the chain, supplies them. The chain is part of the font
  choice, not an extra.
- **Mono stays Latin Modern Mono**, so `style_typeset.py`'s 79-column
  width model for fenced code is still correct. DejaVu Sans Mono only
  covers what LM Mono lacks (`≤` in `` `x ≤ y` `` was the measured
  case).

**XeLaTeX on the same probe.** XeLaTeX has no fallback chain, so the
fair attempt was `ucharclasses` (in `texlive-xetex`) switching to a
per-script `\newfontfamily` for Telugu, Devanagari, CJK Unified
Ideographs and Mathematical Alphanumeric Symbols. Three iterations:

1. With grouped transitions, Latin text after a Telugu word stayed in
   the Telugu font (`Missing character: There is no a ... in font
   Noto Serif Telugu`).
2. Without groups, the same.
3. With explicit transitions for nine more blocks, Latin came back,
   but Devanagari still fell to STIX Two Text. `≤`, `Ⅳ` and `①` were
   missing because each needs its own block mapped to the math font.

That is a hand-kept per-block table again, the thing #996 exists to
retire. It also confirms the issue's reason for LuaLaTeX.

**#948 interplay, measured with a stand-in that has the plan's `.sty`
header and two entries:**

- the `.sty` is a no-op under both engines: `≤` is not remapped, so
  the font has to supply it, and does through the chain.
- the `content/unicode-extra.tex` overlay **breaks** a LuaLaTeX or
  XeLaTeX render: `! Undefined control sequence. \DeclareUnicodeCharacter`.
  Wrapping its contents in `\ifPDFTeX ... \fi` at the point `_unicode.py`
  hands it to pandoc fixes both. Measured: lualatex exit 0 printing `☃`
  from the font, pdflatex exit 0 printing the overlay's `*`.

## 📐 Decisions this plan rests on

| Decision | Why |
| --- | --- |
| LuaLaTeX, not XeLaTeX | Fallback chains covered every probe character first time. XeLaTeX's per-script switching took three attempts and still dropped Devanagari and three symbols |
| …only with the reference-list filter **and** the Lua confinement in the same PR | Without them a `.bib` title, a draft paragraph or a figure file reads and writes any file the user can (Q2). #823 set the bar that a shared `.bib` cannot read outside the draft; switching engines must not lower it |
| XeLaTeX is the fallback decision, not a config option | If the confinement is not accepted in review, switch the default engine to XeLaTeX with STIX Two and no chain, plus the refs filter and an absolute-image refusal (Q2, "Images"). Do not ship LuaLaTeX unconfined |
| STIX Two Text + Math, Noto chain, LM Mono | The only pair with no missing probe glyph. It keeps code-width metrics as they are |
| STIX Two by pinned, checksummed download, not `texlive-fonts-extra` | 2.0 MiB against 1.65 GiB. Same pattern as Vale and actionlint in `install_full_pipeline.sh` |
| Fallback list in Python, passed as pandoc variables | pandoc 3.6's template already emits `luaotfload.add_fallback` from `mainfontfallback`. No custom template, and the list is testable as argv |
| `\tracinglostchars=3` plus the `glyph_not_found` callback, in one shipped header file | Fatal on both engines. The callback is what makes pandoc's message name the character on LuaLaTeX |
| `[render] pdf_engine = "lualatex"` (allowed: `lualatex`, `pdflatex`) for one release | The issue's escape hatch for a host whose TeX lacks the engine or fonts. `pdflatex` keeps #948's path exactly as it is |
| `--fragment` and the `.sty` unchanged | The user's document chooses its engine (issue item 2) |
| The overlay is wrapped in `\ifPDFTeX` | Measured to break both Unicode engines otherwise |

## 🧱 Global constraints

- Built on #948's merged code. Rebase onto `main` after #948 lands, and
  re-read `_unicode.py`'s real signatures before Task 2.
- `openin_any=p`, `-no-shell-escape`, `TEXINPUTS` and
  `_require_tex_readable_tmpdir` stay exactly as #823 left them, on
  every engine.
- No new Python dependency. New OS packages in `os-deps` only.
- Every line that needs a real TeX keeps `# pragma: no cover-windows`.
- Fixtures reuse `smith_2024`, the key `tests/test_render_output.py`
  already uses, or no citation at all. Never a new key.
- MINOR bump (new config key, new shipped assets).

## 🗺 File map

| File | Change |
| --- | --- |
| `chitragupta/config.py`, `config.toml.example` | `RENDER_PDF_ENGINE` from `[render] pdf_engine`, default `lualatex`, validated against the two allowed values |
| `chitragupta/render_output/_engine.py` (new) | engine name, font variables, fallback list, which header files to load. One module, so `_pandoc.py` stays argv assembly |
| `assets/latex/chitragupta-unicode-engine.tex` (new) | `\tracinglostchars=3` and the `glyph_not_found` callback |
| `assets/latex/chitragupta-lua-confine.lua` (new), loaded by a one-line `\directlua{dofile(kpse.find_file("chitragupta-lua-confine.lua", "lua"))}` header | the confinement, found through `TEXINPUTS` (the `.sty`'s directory, which #948 already adds), not by absolute path |
| `assets/pandoc/refs_raw_tex_as_text.lua` (new) | the reference-list filter, placed after `--citeproc` |
| `chitragupta/render_output/_pandoc.py` | `--pdf-engine` from config; font variables, headers and the refs filter on the `pdf` path; the comment block explains each, as its neighbours do |
| `chitragupta/render_output/_unicode.py` | wrap the overlay in `\ifPDFTeX ... \fi`; load `chitragupta-unicode.sty` only when the engine is pdflatex (it is a no-op otherwise, and loading it costs a lookup) |
| `chitragupta/render_output/__init__.py` | `_require(engine)` instead of `_require("pdflatex")` for `pdf` |
| `chitragupta/render_output/_cli.py` | `[unicode]` hint matches both missing-character shapes and says "first" |
| `chitragupta/doctor.py` | `BINARIES` gains the configured engine. A font check runs `luaotfload-tool --find` for each font in the chain |
| `scripts/install_full_pipeline.sh` | `texlive-luatex fonts-noto-core fonts-noto-cjk` in `os-deps`; `install_stix_two` (pinned release, SHA-256, into `/usr/local/share/fonts/stix-two/`) |
| `docs/SECURITY.md`, `docs/CLI.md`, `docs/RENDERING-FLOW.md` | the Lua surface and its two mitigations; the config key; the engine in the flow |
| `.claude/skills/thesis-chapter-writer/SKILL.md`, `book-assembler/SKILL.md` | one sentence: LuaLaTeX works for a document that `\input`s our fragments and is recommended. Nothing forced |
| tests, below | |

## 🛠 Tasks

Each task is TDD: write the test, see it fail for the stated reason,
implement, see it pass. Render tests skip when `lualatex`, or the
font, is missing (add `lualatex_available` and a `font_available(name)`
helper beside `pdflatex_available` in `tests/conftest.py`), so the
Windows leg's self-skips stay as they are.

### Task 1: the engine is a config value

- `tests/test_config.py`: `pdf_engine` defaults to `lualatex`, accepts
  `pdflatex`, and rejects `xelatex` and `tectonic` with a message naming
  the allowed values.
- `tests/test_render_output_cli.py::TestPdflatexHardening` →
  parametrise over both engines: `--pdf-engine` matches config,
  `-no-shell-escape` and `openin_any=p` are present on both, and no
  non-pdf format gets either.

### Task 2: fonts, strict glyphs, and #948 interplay

- argv test: on `lualatex` the command carries `mainfont=STIX Two Text`,
  `mathfont=STIX Two Math`, `monofont=Latin Modern Mono`, the four
  `mainfontfallback=` values in order, the `monofontfallback`, and
  `-H .../chitragupta-unicode-engine.tex`. On `pdflatex` it carries
  none of them.
- `_unicode` tests: on `lualatex` the overlay arrives wrapped in
  `\ifPDFTeX`, and `chitragupta-unicode.sty` is not loaded. On
  `pdflatex`, #948's behaviour is unchanged (its tests stay green and
  untouched).
- real render, **issue checklist item 1**: the Q4 probe draft renders,
  and `pdftotext` returns `CO₂ 𝑡 ℝ ≤ α 𝒶`, `తెలుగు`, `王小明` exactly.
  Skip if `luaotfload-tool --find` cannot find any chain font.
- real render, **item 2**: a draft with `ᚁ` (U+1681) fails with
  `CalledProcessError`, and `stderr` contains `U+1681`. The CLI prints
  the `[unicode]` hint naming it.
- real render: an overlay containing `\DeclareUnicodeCharacter{2603}{*}`
  does not break a `lualatex` render (the Q4 regression).

### Task 3: close the Lua channel (**issue item 3**)

Extend #823's `TestRenderReal` cases. Each has a pdflatex twin that
already passes:

- `.bib` title `\directlua{tex.print(io.open("<abs secret>"):read("*l"))}`:
  the render **succeeds**, the secret is not in `pdftotext`, and the
  literal `\directlua{` is (the filter).
- same with the filter disabled (monkeypatch the filter list empty):
  the render **fails closed**, and nothing is written outside
  `tmp_path` (the confinement on its own).
- `.bib` title with `io.open("<abs>", "w")`: file not created.
- draft body `\directlua{for l in io.lines("<abs>") do tex.print(l) end}`:
  fails closed.
- a `figures/x.tex` with `\csname tex_directlua:D\endcsname{...}`:
  fails closed. This pins that a primitive alias is covered too.
- `os.getenv("HOME")` typed into the body prints nothing.
- a raw `\includegraphics{<abs pdf>}` fails the render on the
  configured engine. This holds on LuaLaTeX and pdflatex today (Q2,
  "Images"), and the test is what stops a later move to XeLaTeX from
  dropping it silently.
- filter unit test on a normal title (accents, `$\alpha$`, `\emph`,
  `\textsubscript`): the LaTeX output is identical with and without
  the filter.
- argv: the refs filter comes **after** `--citeproc` in `cmd`. Order is
  behaviour here.

**Review focus for Task 3**, stated so a reviewer looks at it directly:
the allow-list roots, the `debug` removal, the text-only `load`, and
whether anything that loads after the confinement (lazy fonts, `hyperref`
at shipout, `microtype`) needs a root the list lacks. The Q2 residuals
(`kpse.readable_file` as an existence oracle, `os.tmpdir`) are known
and accepted, and the PR should say so.

### Task 4: installer, doctor, CI (**issue item 5**)

- `os-deps`: add `texlive-luatex fonts-noto-core fonts-noto-cjk`. Add
  `install_stix_two`, pinned and SHA-256-verified, following
  `install_vale`. Choose the STIX Two release (OFL) when building,
  record its version and digest beside `VALE_SHA256`, and install only
  the five OTFs (Text Regular/Bold/Italic/BoldItalic, Math), 2.0 MiB.
  Run `fc-cache` after.
- shellcheck stays clean. The post-install check uses
  `luaotfload-tool --find` (Q0's `dpkg` trap).
- `doctor`: reports a missing engine or chain font as a missing
  binary, with the `os-deps` remedy.
- CI: the Linux leg already runs `install_full_pipeline.sh all`, so it
  gets the packages with no workflow change. The Windows leg installs
  no `os-deps`, and its render tests self-skip on the new
  `lualatex_available` exactly as they do on `pdflatex_available`.
  Check that no workflow file needs editing. If one does, name why in
  the PR.

### Task 5: fragments, docs, numbers (**items 4 and 6**)

- existing `--fragment` tests stay green unchanged. Add one real
  pdflatex compile of a document that `\input`s a fragment with `CO₂`
  and loads `chitragupta-unicode.sty`.
- `docs/SECURITY.md`: the Lua surface (Q2's tables, short form), the
  two mitigations, the residuals, and that `pdf_engine = "pdflatex"`
  avoids the surface entirely.
- PR description: re-run Q3's benchmark on the branch, and the
  repository owner's real book if they will run it, and paste both
  tables. Item 6 asks for "the book". Do not claim the book was built
  if only the generated document was.

### Task 6: full checks

`.venv-full/bin/python -m pytest --cov --cov-report=term-missing`
(100% line and branch, **item 7**), `bash scripts/check_local.sh`,
`poetry check`, and a hand render of the Q4 probe opened and checked
by eye. Then mark this plan's Status line with the PR that closed it.

## 🚧 Out of scope, and why it is safe

- **The figure-layout probe stays on pdflatex.** It measures TikZ node
  boxes, and node text in Latin Modern is a few percent narrower than
  in STIX Two, so its overlap verdict is approximate for a STIX Two
  render. It already uses `openin_any=p` and `-no-shell-escape`, and it
  runs no Lua. Moving it is a follow-up once the engine has shipped.
- **`tex` output and `--fragment`** do not run our engine. The refs
  filter still applies to their reference lists. It is pandoc-side, so
  a `.bib` command reaches a `.tex` output as visible text instead of
  raw TeX, which is a strict improvement on #823's stated gap.
- **Tagged PDF**: later. LuaLaTeX is a prerequisite, not the feature.

## ❓ Open questions for the maintainer

1. Accept the in-process Lua confinement as the condition for LuaLaTeX,
   or go straight to XeLaTeX (no Lua, but it needs its own
   absolute-image refusal, and its script coverage is weaker)? This
   plan recommends the former, and Task 3 is the place to decide.
2. Keep `pdf_engine` after one release, as the issue asks? The
   confinement is the riskiest code here, so a permanent
   `pdflatex` setting is a reasonable thing to keep for cautious
   users.
3. Should the CJK fallback be SC only, or SC, then TC, then JP? Each
   extra `.ttc` face costs nothing to install (one `.ttc` holds all of
   them), but costs about 1 s of first-use font conversion.

## 🔁 Reproducing the spike

Everything ran in `/tmp/s996` without root. Download and unpack the
two TeX packages and the font packages (`apt-get download`, `dpkg -x`).
Point `TEXMFAUXTREES` at the unpacked `texmf-dist` and at a tree holding
the fonts, `TEXMFVAR` at a scratch directory, and `FONTCONFIG_FILE` at
a `fonts.conf` that adds the font tree. Then run pandoc with the
`_pandoc.py` argv, as `pd.py ENGINE in.md out.pdf [extra pandoc args]`
did. The scratch scripts were not committed: they are throwaway, and
every command and number they produced is in the sections above.
