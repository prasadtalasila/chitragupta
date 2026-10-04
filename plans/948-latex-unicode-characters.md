# #948: print Unicode characters in LaTeX instead of rewriting them

Status: **implemented** on branch `issue-948-nfkc-only-math-alphanumerics`
(the PR that says "Fixes #948"), 2026-10-04. Changed on the way:
`main` was already 6.130.0, so the bump is to 6.131.0;
`render()` sat at exactly 25 statements and `render_output/__init__.py`
at 250 code lines, so the `_unicode.preamble_files(...)` call is an
argument of the existing `_pandoc_command(...)` call rather than its
own statement, and the module docstring sentence Task 1 rewrites was
shortened by two lines to leave room; the two harness copies of each
edited skill (`.agents/`, `.opencode/`) carry the same text, as
`tests/test_skill_harness_copies.py` requires; the book-assembler text
points an unmapped character at the book's own `preamble.tex`, since
`content/unicode-extra.tex` reaches standalone renders only; and
`tests/test_render_output_unicode.py` adds one pandoc-free test of the
`--include-in-header` loop so CI's Windows leg reaches it. Written
2026-10-04 for
[#948](https://github.com/prasadtalasila/chitragupta/issues/948)
(parent #993). The engine move this plan deliberately does not make is
[#996](https://github.com/prasadtalasila/chitragupta/issues/996); see
"Not covered here".

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Written for** whoever implements #948: someone who can read Python
and basic LaTeX but has not seen `chitragupta/render_output/`.

**Assumed:** the worktree setup in DEVELOPER-AGENTS.md (`.venv-full`,
pandoc, TeX Live from `scripts/install_full_pipeline.sh os-deps`), and
that a render test self-skips without pandoc/pdflatex, as every other
one in `tests/test_render_output*.py` does.

**Not covered here:**

- Moving our own PDF renders to LuaLaTeX or XeLaTeX: #996, which
  also compares the two engines. This plan keeps pdflatex, and
  everything it adds is still needed after that move, for thesis
  fragments `\input` into a pdflatex document.
- Applying the same rule when PDFs are first parsed
  (`chitragupta/pdf_text/__init__.py:267`). Once LaTeX can print the
  characters, a 𝑡 in `content/parsed/` no longer breaks anything.
- Telling the drafting skills to write `$_2$` rather than `₂`.
  Optional prose; this plan makes both spellings build.

**Goal:** a draft's text reaches pandoc exactly as written (except
control characters and canonical accent joining), and pdflatex prints
the characters it could not, from a generated style file.

**Architecture:** `_sanitize_for_latex` drops NFKC for NFC, so it
stops rewriting `m²`, `µm`, `H₂O`. A generated
`assets/latex/chitragupta-unicode.sty` maps about 1,300 code points to
the LaTeX commands amsmath and amssymb already provide, via the
kernel's `\DeclareUnicodeCharacter`, guarded so a character LaTeX
already prints keeps its own glyph. A render loads the `.sty` only
when the draft contains a character it maps. A fragment gets the file
copied beside it and a one-line notice, the way TikZ libraries already
work. A character in none of the tables still stops the build, and the
CLI then adds a repair hint naming the character.

**Tech stack:** Python `unicodedata`; pdflatex with
`\DeclareUnicodeCharacter` (LaTeX kernel), `iftex` (texlive-base),
`amsmath`/`amssymb` (already loaded by pandoc's default template). No
new Python or TeX dependency.

**Spec:** issue #948, as narrowed in the 2026-10-02..04 discussion
summarised under "Decisions" below.

## 🧭 Decisions this plan rests on

Each was measured in this container (pandoc + TeX Live 2023) before it
was written down. Recorded so a reviewer can tell a decision from an
accident.

| Decision | Why |
| --- | --- |
| Drop NFKC; keep NFC | NFKC rewrites `m²`→`m2`, `H₂O`→`H2O`, and turns `µ` (U+00B5, which pdflatex prints) into `μ` (U+03BC, which it cannot, exit 43). NFC changes no meaning, and it is what makes a decomposed `e`+U+0301 compile today, so dropping it would regress `pdftotext` quotes |
| Print, don't fold | Folding `₂` to `2` still changes what the draft says. `\DeclareUnicodeCharacter{2082}{\textsubscript{2}}` prints a real subscript. Italic 𝑡 stays italic, which the #389 fold lost |
| Generated, not hand-kept | ~1,250 of the ~1,330 entries are derived from `unicodedata` names and decompositions. Only the math operators (`≤`, `∈`, …) need a hand table, because no Unicode name spells `\leq` |
| `\DeclareUnicodeCharacter`, not `newunicodechar` | Kernel command. `newunicodechar` is texlive-latex-extra, and a smaller TeX must not lose renders that work today (the reason `fvextra` loads conditionally in `_pandoc.py`) |
| Guarded by the kernel's `u8:` entry | A thesis that already prints `×`, `µ` or `→`, or that declares its own glyph for `≤` *before* loading this, keeps it. Measured: a document with `\DeclareUnicodeCharacter{2264}{LEQ}` before `\usepackage{chitragupta-unicode}` prints `LEQ` |
| No-op under XeTeX/LuaTeX (`\ifPDFTeX`) | Those engines read Unicode with real fonts; redefining 1,300 characters there would replace font glyphs with math approximations |
| Loaded only when needed | Same rule as `tikz` and `fvextra` in `_pandoc_command`: a draft with none of these characters renders exactly as it does today, and its `.tex` output does not gain a `\usepackage` it cannot resolve |
| Unmapped stays loud | `☃` still fails with `! LaTeX Error: Unicode character ☃ (U+2603)`. The CLI adds a hint: rewrite it in the draft, or add a line to `content/unicode-extra.tex` |
| Per-project overlay file, no skill | A pip-installed user cannot edit the shipped `.sty`. `content/unicode-extra.tex`, if present, is appended to the preamble after it. A recurring character gets a generator rule in a normal PR; no skill edits `chitragupta/` or `assets/` (CLAUDE.md routing) |

## Global Constraints

- pdflatex stays the PDF engine: `cmd += ["--pdf-engine", "pdflatex"]`
  in `_pandoc.py` is unchanged.
- `openin_any=p` (#823) stays set; the `.sty` is found through
  `TEXINPUTS`, not by absolute path. Measured to work from a dotted
  directory (`/tmp/.hid/latex`), which is what a `.venv` install path
  looks like.
- No new runtime or dev dependency; `poetry.lock` is not touched.
  hypothesis is out for now (the user's call); the property test
  enumerates code points instead.
- 100% line and branch coverage holds; pdflatex-only lines carry
  `# pragma: no cover-windows` like their neighbours.
- No citekey appears in any fixture this plan adds.
- Version: MINOR bump (new script, new shipped asset, new optional
  project file). 6.130.0 if `main` is still 6.129.1 when you branch.

## Review Focus

Inputs the issue never names that a real draft will contain. Each has
its test in the task that owns the code.

1. **A mapped character in a heading** (`# CO₂ budget`): hyperref
   writes headings into PDF bookmarks, where `\textsubscript` is not
   allowed. The build must still succeed (a warning is fine). Task 3.
2. **A mapped character in inline code or a fenced block** (`` `x ≤ y` ``,
   a Python block with `α = 1`): `fvextra`'s `Verbatim` still runs
   inputenc. Measured to build; pinned in Task 3.
3. **A mapped character already inside math** (`$α ≤ β$`): every math
   entry is `\ensuremath{…}`, so it works in both modes. Task 3.
4. **The user's own LaTeX already prints the character**: their glyph
   wins (the guard). Task 2 compiles that case.
5. **html/docx renders**: browsers and Word print all of these, so the
   text must arrive unchanged and no `.sty` is involved. Task 3.

## File map

| File | Change | Responsibility |
| --- | --- | --- |
| `chitragupta/render_output/_citeproc.py` | modify `_sanitize_for_latex` and the two docstrings that describe it | text: controls stripped, NFC, nothing else |
| `chitragupta/render_output/__init__.py` | modify the module docstring (line 21) and `render()` | call `_unicode.preamble_files` and pass its result on |
| `scripts/generate_unicode_sty.py` | create | builds the `.sty` from `unicodedata` plus the symbol table |
| `assets/latex/chitragupta-unicode.sty` | create (generated) | what pdflatex loads |
| `assets/latex/README.md` | create | what the file is, how to regenerate it, why it is guarded |
| `chitragupta/render_output/_unicode.py` | create | which drafts need the `.sty`; header file, fragment copy, overlay |
| `chitragupta/render_output/_pandoc.py` | modify `_pandoc_command` | `--include-in-header` per file; `.sty` dir on `TEXINPUTS` |
| `chitragupta/render_output/_cli.py` | modify the `CalledProcessError` branch | `[unicode]` repair hint |
| `tests/test_render_output_citeproc.py` | modify `TestSanitizeForLatex` | issue table, every-code-point property, NFC |
| `tests/test_unicode_sty.py` | create | drift pin, coverage of the groups, one pdflatex compile of every entry |
| `tests/test_render_output_unicode.py` | create | `_unicode` unit tests, real pdf/tex/html renders |
| `tests/test_render_output_cli.py` | modify | the hint |
| `.claude/skills/book-assembler/SKILL.md`, `.claude/skills/thesis-chapter-writer/SKILL.md`, `docs/CLI.md` | modify | tell the author what to load, and where the overlay goes |
| `pyproject.toml` | modify | version |

---

### Task 0: Branch

- [ ] **Step 1: Start from the current tip of `main`**

```bash
git fetch origin main
git checkout -B <your-branch> origin/main
grep -m1 '^version' pyproject.toml
```

Note the version; Task 5 bumps its MINOR.

---

### Task 1: Stop rewriting the draft's text

**Files:**

- Modify: `chitragupta/render_output/_citeproc.py:14-44` and the
  bullet at `:86-90` in `_safe_render_inputs`'s docstring
- Modify: `chitragupta/render_output/__init__.py:21` (module
  docstring sentence about `_sanitize_for_latex`)
- Test: `tests/test_render_output_citeproc.py` (`TestSanitizeForLatex`)

**Interfaces:**

- Produces: `_sanitize_for_latex(text: str) -> str` with the same name
  and signature. Kept on purpose: tests and `render_output/__init__.py`
  import it by name, and renaming it is churn this issue does not need.
- Produces: `_UNSAFE_CONTROL_RE` (unchanged), imported by the new test.

- [ ] **Step 1: Write the failing tests**

Replace `test_math_italic_is_folded_to_its_ascii_letter` (it pins the
behaviour this issue removes) and add the rest to
`TestSanitizeForLatex`:

```python
import unicodedata

from chitragupta.render_output._citeproc import _UNSAFE_CONTROL_RE

# Every rewrite #948 found, plus #389's own 𝑡: printing them is
# chitragupta-unicode.sty's job now, and the text must reach it as written.
_WRITTEN_AS_IS = [
    "5 µm", "10 m²", "H₂O", "½", "Brand™", "Phase Ⅳ", "Step ①",
    "the 𝑡 statistic", "Planck ℎ", "R² = 0.94", "10\u00a0kg", "wait…", "ﬁle",
]  # fmt: skip


class TestSanitizeForLatex:
    # ... keep test_a_nul_byte_is_stripped, test_other_c0_controls_...,
    # test_ordinary_unicode_is_left_alone, test_idempotent_on_already_clean_text

    @pytest.mark.parametrize("text", _WRITTEN_AS_IS)
    def test_a_character_948_found_rewritten_is_left_as_written(self, text):
        assert render_output._sanitize_for_latex(text) == text

    def test_a_decomposed_accent_is_joined(self):
        # pdftotext can emit é as e + U+0301; pdflatex rejects the bare
        # combining mark (exit 43) and accepts the composed letter. NFC is
        # canonical equivalence, so this changes how é is stored, not what
        # the text says.
        assert render_output._sanitize_for_latex("cafe\u0301") == "caf\u00e9"

    def test_no_other_code_point_is_changed(self):
        # The class #948 names: a transform over a whole draft is identity
        # outside its stated domain. The domain is the C0 controls the
        # regex names, plus NFC; every other assigned code point must come
        # back as itself. Exhaustive rather than sampled, because the
        # transform is per character: ~150k assigned code points, about a
        # second.
        changed = [
            f"U+{cp:04X}"
            for cp in range(0x110000)
            if not 0xD800 <= cp <= 0xDFFF
            and unicodedata.category(chr(cp)) != "Cn"
            and not _UNSAFE_CONTROL_RE.match(chr(cp))
            and unicodedata.is_normalized("NFC", chr(cp))
            and render_output._sanitize_for_latex(chr(cp)) != chr(cp)
        ]
        assert changed == []
```

- [ ] **Step 2: Run them to see them fail**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_render_output_citeproc.py -k SanitizeForLatex -q
```

Expected: FAIL. `10 m²` comes back as `10 m2`, and the
every-code-point test lists thousands of code points.

- [ ] **Step 3: Implement**

In `_citeproc.py`, replace the function and its docstring:

```python
def _sanitize_for_latex(text: str) -> str:
    r"""`text` with control characters stripped and accents stored as one
    code point -- the two things no output format wants, and nothing else.

    A NUL byte reaches a draft through a quoted passage from
    `content/parsed/<citekey>.txt`, which is `pdftotext` output (#389);
    pdflatex rejects it outright, and no rendered document wants one.
    `pdftotext` can also store `é` as `e` plus U+0301; pdflatex rejects
    the bare combining mark, and NFC joins it back. NFC is canonical
    equivalence, so it changes how a letter is stored, never what it is.

    It used to be NFKC, for #389's math-italic 𝑡, and NFKC rewrote far
    more than that across the whole draft: `m²` to `m2`, `H₂O` to `H2O`,
    and `µm` to a `μ` pdflatex cannot print (#948). Printing those
    characters is now `assets/latex/chitragupta-unicode.sty`'s job (see
    `_unicode.py`), so the text reaches pandoc as the author wrote it.
    """
    return _UNSAFE_CONTROL_RE.sub("", unicodedata.normalize("NFC", text))
```

In `_safe_render_inputs`'s docstring, replace the third bullet with:

```text
      - a control character -- never legitimate content, most often
        reached by a quoted passage straight from `content/parsed/` -- is
        stripped, and a decomposed accent joined, so pdflatex doesn't
        reject the whole render over it (see _sanitize_for_latex).
```

In `render_output/__init__.py:21`, change the sentence that says the
sanitiser folds math-alphanumeric characters so that it says it strips
control characters and joins decomposed accents (read the surrounding
lines first; keep their wording style).

- [ ] **Step 4: Run them to see them pass**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_render_output_citeproc.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/render_output/_citeproc.py chitragupta/render_output/__init__.py tests/test_render_output_citeproc.py
git commit -m "Stop NFKC from rewriting a draft's characters before render (#948)"
```

Between this commit and Task 3, a draft with `𝑡` fails its PDF render
again (#389's case). That is expected mid-branch; do not merge before
Task 3.

---

### Task 2: Generate `chitragupta-unicode.sty`

**Files:**

- Create: `scripts/generate_unicode_sty.py`
- Create (generated): `assets/latex/chitragupta-unicode.sty`
- Create: `assets/latex/README.md`
- Test: `tests/test_unicode_sty.py`

**Interfaces:**

- Produces: `scripts.generate_unicode_sty.STY_PATH: Path`,
  `entries() -> dict[int, str]`, `render() -> str`, `main() -> int`,
  and the tables `HOLES`, `SYMBOLS`.
- Produces: the `.sty` line format Task 3 parses, one entry per line:
  `\chitragupta@char{<char>}{<HEX>}{<LaTeX>}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_unicode_sty.py`:

```python
"""assets/latex/chitragupta-unicode.sty against the script that writes it (#948).

The `.sty` is generated output. This file pins it to its generator, so
a hand edit fails here, and checks that what the generator emits
compiles: every entry, in one pdflatex run.
"""

import subprocess
import unicodedata

import pytest

from scripts import generate_unicode_sty as gen
from tests.conftest import pdflatex_available


def test_the_committed_sty_is_what_the_generator_writes():
    assert gen.STY_PATH.read_text(encoding="utf-8") == gen.render(), (
        "assets/latex/chitragupta-unicode.sty is stale or hand-edited. "
        "Run `python -m scripts.generate_unicode_sty` and commit the result."
    )


@pytest.mark.parametrize("char", ["𝑡", "𝐀", "ℎ", "ℝ", "₂", "Ⅳ", "①", "≤", "α", "Ω"])
def test_the_characters_948_named_are_mapped(char):
    assert ord(char) in gen.entries()


def test_the_holes_are_exactly_the_math_block_s_reserved_letter_slots():
    # Unicode left 24 slots of U+1D400-U+1D6A3 empty because those
    # letters already existed in Letterlike Symbols. HOLES must name one
    # character per empty slot, each the plain letter it stands for.
    empty = [cp for cp in range(0x1D400, 0x1D6A4) if not unicodedata.name(chr(cp), "")]
    assert len(empty) == len(gen.HOLES) == 24
    for cp, (_, letter) in gen.HOLES.items():
        assert unicodedata.normalize("NFKC", chr(cp)) == letter


def test_only_capital_digamma_in_the_math_block_is_left_unmapped():
    # No pdflatex font has a capital digamma. Left unmapped on purpose,
    # so it fails loudly rather than printing as something else.
    unmapped = [
        cp
        for cp in range(0x1D400, 0x1D800)
        if unicodedata.name(chr(cp), "") and cp not in gen.entries()
    ]
    assert unmapped == [0x1D7CA]


def test_a_style_pdflatex_lacks_keeps_the_letter():
    # Lowercase double-struck has no amssymb glyph: the letter is kept
    # and only the style is lost.
    assert gen.entries()[0x1D552] == r"\ensuremath{a}"  # MATHEMATICAL DOUBLE-STRUCK SMALL A


def test_main_writes_the_file(tmp_path, monkeypatch, capsys):
    target = tmp_path / "latex" / "chitragupta-unicode.sty"
    monkeypatch.setattr(gen, "STY_PATH", target)
    assert gen.main() == 0
    assert target.read_text(encoding="utf-8") == gen.render()
    assert "characters" in capsys.readouterr().out


def _compile_every_entry(tmp_path):
    """One pdflatex run over every entry, with a user glyph for ≤ declared
    before the package loads. Returns the finished process."""
    body = " ".join(chr(cp) for cp in sorted(gen.entries()))
    (tmp_path / "chitragupta-unicode.sty").write_text(gen.render(), encoding="utf-8")
    (tmp_path / "all.tex").write_text(
        "\\documentclass{article}\\usepackage[T1]{fontenc}\\usepackage{lmodern}\n"
        "\\DeclareUnicodeCharacter{2264}{USERLEQ}\n"
        "\\usepackage{chitragupta-unicode}\n"
        f"\\begin{{document}}\n{body}\n\\end{{document}}\n",
        encoding="utf-8",
    )
    return subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "all.tex"],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )  # fmt: skip


@pytest.mark.skipif(not pdflatex_available, reason="pdflatex not installed")
def test_every_entry_compiles_with_no_missing_glyph(tmp_path):
    result = _compile_every_entry(tmp_path)
    assert result.returncode == 0, result.stdout[-2000:]
    log = (tmp_path / "all.log").read_text(encoding="utf-8", errors="replace")
    assert "Missing character" not in log


@pytest.mark.skipif(
    not (pdflatex_available and pdftotext_available), reason="pdflatex/pdftotext not installed"
)
def test_a_glyph_the_user_declared_first_is_kept(tmp_path):
    # Review Focus 4: the guard. The user declared ≤ before loading the
    # package, so their glyph must survive it.
    assert _compile_every_entry(tmp_path).returncode == 0
    text = subprocess.run(
        ["pdftotext", "all.pdf", "-"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout
    assert "USERLEQ" in text
```

Import `pdftotext_available` from `tests.conftest` alongside
`pdflatex_available` (both are defined there).

- [ ] **Step 2: Run them to see them fail**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_unicode_sty.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.generate_unicode_sty'`.

- [ ] **Step 3: Write the generator**

`scripts/generate_unicode_sty.py`. This is the version measured in
the container: 1,333 entries, all compiling in one pdflatex run.

```python
"""Writes `assets/latex/chitragupta-unicode.sty`: how pdflatex prints the
Unicode characters a draft carries but its default fonts cannot (#948).

Run it, never edit its output: `python -m scripts.generate_unicode_sty`.
`tests/test_unicode_sty.py` fails when the committed file differs from
what this writes, so a hand edit to the `.sty` is reverted by the next
person to run it, and a change here without a rerun fails CI.

Every line maps one code point to the LaTeX command that draws it, and
nothing here changes the text of a draft: the draft keeps the character,
LaTeX decides how to print it. Five generated groups, derived from
Python's own `unicodedata` tables rather than typed out, plus one short
hand table (`SYMBOLS`) for the math operators no Unicode name spells as a
LaTeX command.

A character LaTeX already prints is never redefined: the `.sty` guards
each line with the kernel's own `u8:` lookup, so `²`, `µ`, `×` and `½`
keep the glyphs the user's LaTeX gives them. A character in none of the
groups is not mapped at all, and pdflatex still stops on it, naming it.
"""

import sys
import unicodedata
from pathlib import Path

STY_PATH = Path(__file__).resolve().parent.parent / "assets" / "latex" / "chitragupta-unicode.sty"

# Greek letter names as `unicodedata` spells them (note LAMDA), to the
# math command amsmath/amssymb draw them with. U+03C6 GREEK SMALL LETTER
# PHI is the loopy form, which LaTeX calls \varphi; U+03D5 PHI SYMBOL is
# the straight one, \phi. Epsilon is the same swap.
GREEK_SMALL = {
    "ALPHA": r"\alpha", "BETA": r"\beta", "GAMMA": r"\gamma", "DELTA": r"\delta",
    "EPSILON": r"\varepsilon", "ZETA": r"\zeta", "ETA": r"\eta", "THETA": r"\theta",
    "IOTA": r"\iota", "KAPPA": r"\kappa", "LAMDA": r"\lambda", "MU": r"\mu", "NU": r"\nu",
    "XI": r"\xi", "OMICRON": "o", "PI": r"\pi", "RHO": r"\rho", "FINAL SIGMA": r"\varsigma",
    "SIGMA": r"\sigma", "TAU": r"\tau", "UPSILON": r"\upsilon", "PHI": r"\varphi",
    "CHI": r"\chi", "PSI": r"\psi", "OMEGA": r"\omega",
    "EPSILON SYMBOL": r"\epsilon", "LUNATE EPSILON SYMBOL": r"\epsilon",
    "THETA SYMBOL": r"\vartheta", "KAPPA SYMBOL": r"\varkappa", "PHI SYMBOL": r"\phi",
    "RHO SYMBOL": r"\varrho", "PI SYMBOL": r"\varpi", "NABLA": r"\nabla",
    "PARTIAL DIFFERENTIAL": r"\partial", "DIGAMMA": r"\digamma",
}  # fmt: skip
# Capitals with no command of their own are the Latin letter they look
# like, which is how every LaTeX math font draws them anyway.
GREEK_CAPITAL = {
    "GAMMA": r"\Gamma", "DELTA": r"\Delta", "THETA": r"\Theta", "LAMDA": r"\Lambda",
    "XI": r"\Xi", "PI": r"\Pi", "SIGMA": r"\Sigma", "UPSILON": r"\Upsilon", "PHI": r"\Phi",
    "PSI": r"\Psi", "OMEGA": r"\Omega", "THETA SYMBOL": r"\Theta",
    "ALPHA": "A", "BETA": "B", "EPSILON": "E", "ZETA": "Z", "ETA": "H", "IOTA": "I",
    "KAPPA": "K", "MU": "M", "NU": "N", "OMICRON": "O", "RHO": "P", "TAU": "T", "CHI": "X",
}  # fmt: skip
DIGIT_NAMES = "ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE".split()

# Longest first: "SANS-SERIF BOLD ITALIC" must match before "SANS-SERIF".
STYLES = (
    "SANS-SERIF BOLD ITALIC", "SANS-SERIF BOLD", "SANS-SERIF ITALIC", "SANS-SERIF",
    "BOLD ITALIC", "BOLD SCRIPT", "BOLD FRAKTUR", "BOLD", "ITALIC", "SCRIPT", "FRAKTUR",
    "DOUBLE-STRUCK", "MONOSPACE",
)  # fmt: skip

# The 24 reserved slots in U+1D400-U+1D7FF. Their letters were encoded in
# Letterlike Symbols before the math block existed, so Unicode points the
# block's gap at the older character: a math-italic h is U+210E PLANCK
# CONSTANT, not U+1D455. Same style rule as the block.
HOLES = {
    0x210E: ("ITALIC", "h"),
    0x212C: ("SCRIPT", "B"), 0x2130: ("SCRIPT", "E"), 0x2131: ("SCRIPT", "F"),
    0x210B: ("SCRIPT", "H"), 0x2110: ("SCRIPT", "I"), 0x2112: ("SCRIPT", "L"),
    0x2133: ("SCRIPT", "M"), 0x211B: ("SCRIPT", "R"), 0x212F: ("SCRIPT", "e"),
    0x210A: ("SCRIPT", "g"), 0x2134: ("SCRIPT", "o"),
    0x212D: ("FRAKTUR", "C"), 0x210C: ("FRAKTUR", "H"), 0x2111: ("FRAKTUR", "I"),
    0x211C: ("FRAKTUR", "R"), 0x2128: ("FRAKTUR", "Z"),
    0x2102: ("DOUBLE-STRUCK", "C"), 0x210D: ("DOUBLE-STRUCK", "H"),
    0x2115: ("DOUBLE-STRUCK", "N"), 0x2119: ("DOUBLE-STRUCK", "P"),
    0x211A: ("DOUBLE-STRUCK", "Q"), 0x211D: ("DOUBLE-STRUCK", "R"),
    0x2124: ("DOUBLE-STRUCK", "Z"),
}  # fmt: skip

# Math operators an LLM writes as a character. No Unicode name spells the
# LaTeX command, so these are the one hand-kept table; each is the command
# in amsmath/amssymb, which pandoc's template and this .sty both load.
# Some (→, ←, ⟨, …) are already printed by recent kernels; the guard then
# skips them, and an older TeX Live still gets them.
SYMBOLS = {
    0x2264: r"\leq", 0x2265: r"\geq", 0x2260: r"\neq", 0x2248: r"\approx",
    0x2261: r"\equiv", 0x223C: r"\sim", 0x2243: r"\simeq", 0x2245: r"\cong",
    0x221D: r"\propto", 0x226A: r"\ll", 0x226B: r"\gg", 0x227A: r"\prec",
    0x227B: r"\succ", 0x2208: r"\in", 0x2209: r"\notin", 0x220B: r"\ni",
    0x2282: r"\subset", 0x2283: r"\supset", 0x2286: r"\subseteq", 0x2287: r"\supseteq",
    0x222A: r"\cup", 0x2229: r"\cap", 0x2205: r"\emptyset", 0x2216: r"\setminus",
    0x2200: r"\forall", 0x2203: r"\exists", 0x2204: r"\nexists", 0x2227: r"\wedge",
    0x2228: r"\vee", 0x22A4: r"\top", 0x22A5: r"\perp", 0x22A2: r"\vdash",
    0x22A8: r"\models", 0x2234: r"\therefore", 0x2235: r"\because",
    0x2192: r"\rightarrow", 0x2190: r"\leftarrow", 0x2194: r"\leftrightarrow",
    0x21A6: r"\mapsto", 0x21D2: r"\Rightarrow", 0x21D0: r"\Leftarrow",
    0x21D4: r"\Leftrightarrow", 0x2191: r"\uparrow", 0x2193: r"\downarrow",
    0x27F6: r"\longrightarrow", 0x221E: r"\infty", 0x2211: r"\sum", 0x220F: r"\prod",
    0x222B: r"\int", 0x222E: r"\oint", 0x221A: r"\surd", 0x2213: r"\mp",
    0x22C5: r"\cdot", 0x2218: r"\circ", 0x2217: r"\ast", 0x2295: r"\oplus",
    0x2297: r"\otimes", 0x2225: r"\parallel", 0x2223: r"\mid", 0x2220: r"\angle",
    0x2032: r"{}^{\prime}", 0x2033: r"{}^{\prime\prime}", 0x2212: "-",
    0x210F: r"\hbar", 0x2113: r"\ell", 0x2118: r"\wp", 0x2135: r"\aleph",
    0x27E8: r"\langle", 0x27E9: r"\rangle", 0x2308: r"\lceil", 0x2309: r"\rceil",
    0x230A: r"\lfloor", 0x230B: r"\rfloor", 0x220E: r"\blacksquare",
    0x25A1: r"\square", 0x22EF: r"\cdots",
}  # fmt: skip

_HEADER = r"""%% Generated by scripts/generate_unicode_sty.py -- do not edit (#948).
%% How pdflatex prints Unicode characters its default fonts cannot.
%% A thesis or book that \input-s a chitragupta fragment loads this with
%% \usepackage{chitragupta-unicode}. Under XeLaTeX or LuaLaTeX it does
%% nothing: those engines read Unicode themselves.
\NeedsTeXFormat{LaTeX2e}
\ProvidesPackage{chitragupta-unicode}[2026/10/04 chitragupta, issue 948]
\RequirePackage{iftex}
\ifPDFTeX\else\expandafter\endinput\fi
\RequirePackage{amsmath,amssymb}
%% Never redefine a character LaTeX already prints: the kernel's own
%% u8: entry wins, so a user's existing glyph for it is untouched.
\newcommand\chitragupta@char[3]{%
  \ifcsname u8:\detokenize{#1}\endcsname\else\DeclareUnicodeCharacter{#2}{#3}\fi}
"""


def _styled(style: str, base: str, *, latin_capital: bool, greek: bool) -> str:
    """`base` in `style`, with the commands pdflatex's default math fonts
    have. Where a style has no pdflatex font for this letter (lowercase
    script or double-struck), the letter is kept and only the style is
    lost -- the same trade #389 made, now limited to these two cases."""
    bold = "BOLD" in style
    if "SANS-SERIF" in style:
        inner = base if greek else rf"\mathsf{{{base}}}"
    elif style == "MONOSPACE":
        return rf"\mathtt{{{base}}}"
    elif "FRAKTUR" in style:
        inner = rf"\mathfrak{{{base}}}"
    elif "SCRIPT" in style:
        inner = rf"\mathcal{{{base}}}" if latin_capital else base
    elif style == "DOUBLE-STRUCK":
        return rf"\mathbb{{{base}}}" if latin_capital else base
    elif style == "BOLD":
        return rf"\boldsymbol{{{base}}}" if greek else rf"\mathbf{{{base}}}"
    elif style == "BOLD ITALIC":
        return rf"\boldsymbol{{{base}}}"
    else:  # ITALIC: math mode is italic already, except upright Greek capitals
        return rf"\mathit{{{base}}}" if greek and base[1].isupper() else base
    return rf"\boldsymbol{{{inner}}}" if bold else inner


def _greek(key: str, capital: bool) -> tuple[str, bool] | None:
    """(command, is_a_greek_command) for a Greek letter name, or None."""
    command = (GREEK_CAPITAL if capital else GREEK_SMALL).get(key)
    return None if command is None else (command, command.startswith("\\"))


def _math_alphanumeric(style: str, rest: str) -> str | None:
    """The command for one MATHEMATICAL <style> <rest> character."""
    if rest in ("SMALL DOTLESS I", "SMALL DOTLESS J"):
        return r"\imath" if rest.endswith("I") else r"\jmath"
    if rest.startswith("DIGIT "):
        digit = str(DIGIT_NAMES.index(rest.removeprefix("DIGIT ")))
        return _styled(style, digit, latin_capital=False, greek=False)
    case, _, letter = rest.partition(" ")
    if len(letter) == 1:
        capital = case == "CAPITAL"
        base = letter if capital else letter.lower()
        return _styled(style, base, latin_capital=capital, greek=False)
    capital = case == "CAPITAL"
    found = _greek(letter if case in ("CAPITAL", "SMALL") else rest, capital)
    if found is None:
        return None
    command, greek = found
    return _styled(style, command, latin_capital=False, greek=greek)


def _math_block() -> dict[int, str]:
    out = {}
    for cp in range(0x1D400, 0x1D800):
        name = unicodedata.name(chr(cp), "").removeprefix("MATHEMATICAL ")
        style = next((s for s in STYLES if name.startswith(s + " ")), None)
        command = _math_alphanumeric(style, name[len(style) + 1 :]) if style else None
        if command is not None:
            out[cp] = rf"\ensuremath{{{command}}}"
    for cp, (style, letter) in HOLES.items():
        command = _styled(style, letter, latin_capital=letter.isupper(), greek=False)
        out[cp] = rf"\ensuremath{{{command}}}"
    return out


def _greek_block() -> dict[int, str]:
    out = {}
    codepoints = [*range(0x0391, 0x03AA), *range(0x03B1, 0x03CA), 0x03D1, 0x03D5, 0x03D6]
    for cp in [*codepoints, 0x03F0, 0x03F1, 0x03F5]:
        name = unicodedata.name(chr(cp), "").removeprefix("GREEK ")
        capital = name.startswith("CAPITAL LETTER ")
        key = name.removeprefix("CAPITAL LETTER ").removeprefix("SMALL LETTER ")
        found = _greek(key, capital)
        if found is not None:
            command, greek = found
            out[cp] = rf"\ensuremath{{{command}}}" if greek else rf"\textup{{{command}}}"
    return out


def _decomposed(cp: int) -> tuple[str, str]:
    """(tag, the characters it decomposes to) -- ("<sub>", "2") for ₂."""
    tag, *rest = unicodedata.decomposition(chr(cp)).split() or [""]
    return tag, "".join(chr(int(h, 16)) for h in rest)


def _scripts_numerals_circles() -> dict[int, str]:
    out = {}
    for cp in [*range(0x2070, 0x20A0), *range(0x1D2C, 0x1D6B), 0xB2, 0xB3, 0xB9]:
        tag, text = _decomposed(cp)
        command = {"<sub>": "textsubscript", "<super>": "textsuperscript"}.get(tag)
        arg = r"\textminus" if text == "\u2212" else text
        if command and (arg == r"\textminus" or (arg.isascii() and (arg.isalnum() or arg in "+=()"))):
            out[cp] = rf"\{command}{{{arg}}}"
    for cp in range(0x2160, 0x2180):
        out[cp] = rf"\textup{{{_decomposed(cp)[1]}}}"
    for cp in [*range(0x2460, 0x2474), *range(0x24B6, 0x24EB)]:
        tag, text = _decomposed(cp)
        if tag == "<circle>":
            out[cp] = rf"\textcircled{{\scriptsize {text}}}"
    return out


def entries() -> dict[int, str]:
    """Every mapped code point to the LaTeX that prints it."""
    symbols = {cp: rf"\ensuremath{{{command}}}" for cp, command in SYMBOLS.items()}
    return {**_math_block(), **_greek_block(), **_scripts_numerals_circles(), **symbols}


def render() -> str:
    """The whole `.sty`, one line per code point, in code-point order."""
    lines = [
        rf"\chitragupta@char{{{chr(cp)}}}{{{cp:04X}}}{{{tex}}}"
        for cp, tex in sorted(entries().items())
    ]
    return _HEADER + "\n".join(lines) + "\n\\endinput\n"


def main() -> int:
    STY_PATH.parent.mkdir(parents=True, exist_ok=True)
    STY_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {len(entries())} characters to {STY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Two lint notes the prototype did not face:

- `ruff format` reflows the big tables; the `# fmt: skip` comments
  keep them as written. If pylint's `C1`-style complexity checks flag
  `_styled` (eight branches), split the bold wrapping into its own
  helper rather than suppressing the check.
- The `if __name__ == "__main__"` line needs the same coverage
  treatment as the other `scripts/*.py` entry points; copy whatever
  `scripts/render_diagrams.py` does.

- [ ] **Step 4: Generate the file and write its README**

```bash
.venv-full/bin/python -m scripts.generate_unicode_sty
# expect: wrote 1333 characters to .../assets/latex/chitragupta-unicode.sty
```

`assets/latex/README.md`:

```markdown
# LaTeX assets

`chitragupta-unicode.sty` tells pdflatex how to print about 1,300
Unicode characters its default fonts cannot: math-style letters (𝑡 𝐀 ℝ),
Greek, sub- and superscript digits (₂), Roman numerals (Ⅳ), circled
numbers (①) and the common math operators (≤ ∈ →). It is
**generated**: run `python -m scripts.generate_unicode_sty`, never edit
it by hand. `tests/test_unicode_sty.py` fails when the two disagree.

`chitragupta draft render` loads it for a draft that contains one of
these characters (`chitragupta/render_output/_unicode.py`). A `.tex`
output or `--fragment` render gets a copy beside it; the document that
`\input`s a fragment loads it with `\usepackage{chitragupta-unicode}`.

Three properties a change must keep (#948):

- **It never changes the text.** Each line says how to *draw* a
  character; the draft keeps it.
- **It never overrides LaTeX.** A character the kernel, or the user's own
  preamble, already prints keeps that glyph.
- **It does nothing under XeLaTeX or LuaLaTeX,** which read Unicode
  themselves.

A character in none of its tables still stops a pdflatex build, naming
the character. A project can add its own in `content/unicode-extra.tex`,
for example `\DeclareUnicodeCharacter{2603}{\ensuremath{\ast}}`.
```

- [ ] **Step 5: Run the tests**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_unicode_sty.py -q
```

Expected: PASS, including the pdflatex compile.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_unicode_sty.py assets/latex tests/test_unicode_sty.py
git commit -m "Generate chitragupta-unicode.sty so pdflatex prints what NFKC used to fold (#948)"
```

---

### Task 3: Load the `.sty` for the drafts that need it

**Files:**

- Create: `chitragupta/render_output/_unicode.py`
- Modify: `chitragupta/render_output/_pandoc.py` (`_pandoc_command`
  signature and body; the `TEXINPUTS` line near `:261`)
- Modify: `chitragupta/render_output/__init__.py` (`render()`, inside
  the `with tempfile.TemporaryDirectory() as tmp:` block near `:285`)
- Test: `tests/test_render_output_unicode.py`

**Interfaces:**

- Consumes: the `.sty` line format from Task 2
  (`\chitragupta@char{<char>}{<HEX>}{<LaTeX>}`).
- Produces, in `_unicode.py`:
  - `STY_NAME = "chitragupta-unicode"`, `EXTRA_NAME = "unicode-extra.tex"`
  - `sty_path() -> Path`
  - `mapped_characters() -> frozenset[str]` (cached)
  - `needs_sty(text: str) -> bool`
  - `preamble_files(text, output_format, fragment, tmp_dir, out_dir) -> list[Path]`,
    with `text: str`, `output_format: str`, `fragment: bool`,
    `tmp_dir: Path`, `out_dir: Path`
- Produces: a new last parameter on `_pandoc_command`:
  `preamble_files: list[Path] | None = None`

- [ ] **Step 1: Write the failing tests**

`tests/test_render_output_unicode.py`:

```python
"""chitragupta/render_output/_unicode.py: which renders load
chitragupta-unicode.sty, and what a fragment is told (#948)."""

import subprocess

import pytest

from chitragupta import render_output
from chitragupta.render_output import _unicode
from tests.conftest import content_draft, pandoc_available, pdflatex_available


class TestMappedCharacters:
    def test_reads_the_shipped_sty(self):
        assert {"𝑡", "₂", "≤", "ℎ"} <= _unicode.mapped_characters()

    def test_ascii_is_never_mapped(self):
        assert not _unicode.needs_sty("Plain ASCII, R2 and H2O.")

    def test_a_mapped_character_is_noticed(self):
        assert _unicode.needs_sty("the 𝑡 statistic")


class TestPreambleFiles:
    def test_a_pdf_with_a_mapped_character_gets_a_usepackage(self, tmp_path):
        files = _unicode.preamble_files("CO₂", "pdf", False, tmp_path, tmp_path / "out")
        assert [f.read_text(encoding="utf-8") for f in files] == [
            "\\usepackage{chitragupta-unicode}\n"
        ]

    def test_a_draft_without_one_gets_nothing(self, tmp_path):
        assert _unicode.preamble_files("CO2", "pdf", False, tmp_path, tmp_path / "out") == []

    @pytest.mark.parametrize("fmt", ["html", "docx", "md"])
    def test_a_format_that_is_not_latex_gets_nothing(self, tmp_path, fmt):
        assert _unicode.preamble_files("CO₂", fmt, False, tmp_path, tmp_path / "out") == []

    def test_a_tex_output_gets_the_sty_beside_it(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        files = _unicode.preamble_files("CO₂", "tex", False, tmp_path, out)
        assert (out / "chitragupta-unicode.sty").read_bytes() == _unicode.sty_path().read_bytes()
        assert len(files) == 1

    def test_a_fragment_gets_the_sty_and_a_notice_but_no_preamble(self, tmp_path, capsys):
        out = tmp_path / "out"
        out.mkdir()
        assert _unicode.preamble_files("CO₂", "tex", True, tmp_path, out) == []
        assert (out / "chitragupta-unicode.sty").is_file()
        err = capsys.readouterr().err
        assert err.startswith("[unicode] ")
        assert "\\usepackage{chitragupta-unicode}" in err

    def test_a_fragment_without_a_mapped_character_is_silent(self, tmp_path, capsys):
        out = tmp_path / "out"
        out.mkdir()
        assert _unicode.preamble_files("CO2", "tex", True, tmp_path, out) == []
        assert capsys.readouterr().err == ""
        assert not (out / "chitragupta-unicode.sty").exists()

    def test_the_project_s_own_extra_file_comes_last(self, isolated_config, tmp_path):
        extra = isolated_config.CONTENT_DIR / "unicode-extra.tex"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_text("\\DeclareUnicodeCharacter{2603}{*}\n", encoding="utf-8")
        files = _unicode.preamble_files("CO₂ ☃", "pdf", False, tmp_path, tmp_path / "out")
        assert files[-1] == extra
        # Loaded even when the draft has nothing the shipped .sty maps:
        # the user's own characters are the reason the file exists.
        assert _unicode.preamble_files("☃", "pdf", False, tmp_path, tmp_path / "out") == [extra]


@pytest.mark.skipif(
    not (pandoc_available and pdflatex_available), reason="pandoc/pdflatex not installed"
)
class TestRenderReal:
    _DRAFT = (
        "# CO₂ budget for 𝑡\n\n"  # Review Focus 1: a heading goes into PDF bookmarks
        "Phase Ⅳ, step ①, R², 5 µm, ½, the 𝑡 statistic, Planck ℎ, $α ≤ β$, café.\n\n"
        "Inline `x ≤ y`.\n\n"  # Review Focus 2: code
        "```python\nα = 1  # ≤\n```\n"
    )

    def test_948_s_characters_render_to_pdf(self, isolated_config):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(self._DRAFT, encoding="utf-8")
        assert render_output.render(str(draft), output_format="pdf").exists()

    def test_an_unmapped_character_still_fails_naming_itself(self, isolated_config):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("A snowman ☃ here.\n", encoding="utf-8")
        with pytest.raises(subprocess.CalledProcessError) as exc:
            render_output.render(str(draft), output_format="pdf")
        assert "U+2603" in exc.value.stderr

    def test_a_tex_render_loads_the_sty_it_ships_beside_itself(self, isolated_config):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("CO₂\n", encoding="utf-8")
        out = render_output.render(str(draft), output_format="tex")
        assert "\\usepackage{chitragupta-unicode}" in out.read_text(encoding="utf-8")
        assert (out.parent / "chitragupta-unicode.sty").is_file()


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_an_html_render_keeps_every_character_as_written(isolated_config):
    # Review Focus 5: a browser prints all of these; nothing may change them.
    isolated_config.BIB_FILE_PATH.write_text("")
    draft = content_draft(isolated_config, "draft.md")
    draft.write_text("R² H₂O 5 µm 𝑡 Ⅳ ①\n", encoding="utf-8")
    html = render_output.render(str(draft), output_format="html").read_text(encoding="utf-8")
    assert "R² H₂O 5 µm 𝑡 Ⅳ ①" in html
```

Check `content_draft`'s and `isolated_config`'s real signatures in
`tests/conftest.py` before running; the shapes above follow
`tests/test_render_output.py:211-226`.

- [ ] **Step 2: Run them to see them fail**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_render_output_unicode.py -q
```

Expected: FAIL with `ImportError: cannot import name '_unicode'`.

- [ ] **Step 3: Write `_unicode.py`**

```python
"""Which renders load `assets/latex/chitragupta-unicode.sty` (#948).

`_sanitize_for_latex` no longer folds a draft's characters into ones
pdflatex can print; this `.sty` teaches pdflatex to print them instead.
Loaded only for a LaTeX-bound render of a draft that contains one, the
same rule `_pandoc_command` applies to `tikz` and `fvextra`: a draft
without one renders exactly as before, and its `.tex` output does not
gain a `\\usepackage` it cannot resolve.

A fragment has no preamble, so it gets the file copied beside it and
one stderr line naming what the assembling document must load -- the
shape `[tikz-libraries]` already prints, for a skill reading the
render's output.
"""

import shutil
import sys
from functools import cache
from pathlib import Path

import re

from chitragupta import config

STY_NAME = "chitragupta-unicode"
EXTRA_NAME = "unicode-extra.tex"
_LATEX_BOUND = {"tex", "latex", "pdf"}
_ENTRY_RE = re.compile(r"^\\chitragupta@char\{(.)\}", re.MULTILINE)


def sty_path() -> Path:
    """The shipped `.sty`; its directory goes on `TEXINPUTS`."""
    return config.shipped("assets", "latex", f"{STY_NAME}.sty")


@cache
def mapped_characters() -> frozenset[str]:
    """Every character the shipped `.sty` maps, read from the file itself
    so the generator's output is the one runtime truth."""
    return frozenset(_ENTRY_RE.findall(sty_path().read_text(encoding="utf-8")))


def needs_sty(text: str) -> bool:
    return not mapped_characters().isdisjoint(text)


def _extra_path() -> Path | None:
    """The project's own additions, `content/unicode-extra.tex`, if any."""
    path = config.CONTENT_DIR / EXTRA_NAME
    return path if path.is_file() else None


def preamble_files(
    text: str, output_format: str, fragment: bool, tmp_dir: Path, out_dir: Path
) -> list[Path]:
    """Files for pandoc's `--include-in-header`, in order. Copies the
    `.sty` beside a `.tex` output, and prints the fragment notice."""
    if output_format not in _LATEX_BOUND:
        return []
    needed = needs_sty(text)
    if needed and output_format != "pdf":
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sty_path(), out_dir / f"{STY_NAME}.sty")
    if fragment:
        # pandoc's -H implies --standalone, so a fragment must get none.
        if needed:
            print(
                f"[unicode] {STY_NAME}.sty copied beside the fragment -- a fragment has "
                f"no preamble; load it in the assembling document: \\usepackage{{{STY_NAME}}}",
                file=sys.stderr,
            )
        return []
    files = []
    if needed:
        header = tmp_dir / f"{STY_NAME}-header.tex"
        header.write_text(f"\\usepackage{{{STY_NAME}}}\n", encoding="utf-8")
        files.append(header)
    extra = _extra_path()
    if extra is not None:
        files.append(extra)
    return files
```

Sort the imports the way ruff wants (`re` with the other stdlib
imports); the block above is grouped for reading.

- [ ] **Step 4: Thread it through `_pandoc_command` and `render()`**

In `_pandoc.py`, add the parameter and pass each file:

```python
def _pandoc_command(
    ...,
    fragment: bool = False,
    has_code_block: bool = False,
    preamble_files: list[Path] | None = None,
) -> tuple[list[str], dict[str, str] | None]:
```

After the `fvextra` block and before `if output_format in _LATEX_BOUND:`:

```python
    # chitragupta-unicode.sty, and the project's own unicode-extra.tex,
    # for a draft carrying a character pdflatex cannot print alone (#948).
    # A file per -H rather than a third header-includes string: pandoc
    # keeps both, include-in-header after the variable, which is the
    # order the .sty wants (after amssymb, which the template loads).
    for path in preamble_files or []:
        cmd += ["--include-in-header", str(path)]
```

And on the `TEXINPUTS` line, put the `.sty`'s directory after the
draft's own, so a draft's sibling file still wins:

```python
            "TEXINPUTS": f"{input_path.resolve().parent}:{_unicode.sty_path().parent}:",
```

(import `_unicode` at the top of `_pandoc.py`; extend the comment above
the line with one sentence saying why the second directory is there).

In `render()`, inside the `with tempfile.TemporaryDirectory() as tmp:`
block, compute the files before `_pandoc_command` and pass them:

```python
        preamble = _unicode.preamble_files(  # pragma: no cover-windows
            draft_text, output_format, fragment, Path(tmp), out_dir
        )
        ...
            _has_code_block(draft_text),
            preamble,
        )
```

- [ ] **Step 5: Run the tests**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_render_output_unicode.py tests/test_render_output*.py -q
```

Expected: PASS. Existing render tests must not change: none of their
drafts contains a mapped character, so their commands are unchanged.

- [ ] **Step 6: Commit**

```bash
git add chitragupta/render_output/_unicode.py chitragupta/render_output/_pandoc.py chitragupta/render_output/__init__.py tests/test_render_output_unicode.py
git commit -m "Load chitragupta-unicode.sty for a draft that needs it, and ship it beside a fragment (#948)"
```

---

### Task 4: Say how to fix an unmapped character

**Files:**

- Modify: `chitragupta/render_output/_cli.py` (new
  `_unicode_repair_hint`, used at `:185`)
- Test: `tests/test_render_output_cli.py`

**Interfaces:**

- Produces: `_unicode_repair_hint(stderr: str | None) -> str`

- [ ] **Step 1: Write the failing tests**

```python
from chitragupta.render_output._cli import _unicode_repair_hint


class TestUnicodeRepairHint:
    def test_names_the_character_and_both_fixes(self):
        hint = _unicode_repair_hint(
            "! LaTeX Error: Unicode character ☃ (U+2603)\n               not set up"
        )
        assert hint.startswith("\n[unicode] ")
        assert "☃ (U+2603)" in hint
        assert "unicode-extra.tex" in hint
        assert "\\DeclareUnicodeCharacter{2603}" in hint

    @pytest.mark.parametrize("stderr", [None, "", "! Undefined control sequence."])
    def test_says_nothing_about_another_failure(self, stderr):
        assert _unicode_repair_hint(stderr) == ""
```

- [ ] **Step 2: Run them to see them fail**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_render_output_cli.py -k UnicodeRepairHint -q
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement**

In `_cli.py` (add `import re`):

```python
_UNICODE_ERROR_RE = re.compile(r"Unicode character (.) \(U\+([0-9A-F]{4,6})\)")


def _unicode_repair_hint(stderr: str | None) -> str:
    r"""The fix for a character pdflatex cannot print, or "".

    chitragupta-unicode.sty prints about 1,300 characters (#948); one
    outside it still fails the build, which is deliberate: the
    alternative is changing the text. LaTeX's own message names the
    character but not what to do, and the author has two choices.
    """
    match = _UNICODE_ERROR_RE.search(stderr or "")
    if match is None:
        return ""
    char, code = match.groups()
    extra = config.CONTENT_DIR / "unicode-extra.tex"
    return (
        f"\n[unicode] pdflatex cannot print {char} (U+{code}). Either write it as LaTeX "
        f"in the draft (for a symbol, its math command, e.g. $\\aleph$), or teach this "
        f"project to print it: add \\DeclareUnicodeCharacter{{{code}}}{{...}} to {extra}."
    )
```

and at `:185`:

```python
        print(
            f"[error] pandoc failed: {exc.stderr or exc}"
            f"{_figure_repair_hint(args.input)}{_unicode_repair_hint(exc.stderr)}"
        )
```

- [ ] **Step 4: Run the tests**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_render_output_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/render_output/_cli.py tests/test_render_output_cli.py
git commit -m "Name the two fixes when pdflatex cannot print a character (#948)"
```

---

### Task 5: Tell the people who assemble documents, bump, verify

**Files:**

- Modify: `.claude/skills/book-assembler/SKILL.md` (the preamble
  skeleton near `:55`, plus a short "Unicode characters" subsection
  beside "TikZ libraries")
- Modify: `.claude/skills/thesis-chapter-writer/SKILL.md` (beside the
  "Tell the user what their thesis preamble must load" step near `:418`)
- Modify: `docs/CLI.md` (the `draft render` section: what is loaded,
  the overlay file, the `[unicode]` lines)
- Modify: `pyproject.toml` (version, MINOR)
- Modify: this file (status line)

- [ ] **Step 1: book-assembler.** Add to the skeleton, after `amssymb`
  is available (pandoc's units need it anyway) and before `hyperref`:

```latex
\usepackage{amsmath,amssymb}
\usepackage{chitragupta-unicode}             % see "Unicode characters" below
```

and the subsection, in the file's own voice: every unit rendered with
`--fragment` that contains such a character prints a `[unicode]` line
and gets the `.sty` copied into `content/rendered/<book>/`; load it
once in the book preamble; under XeLaTeX or LuaLaTeX it is a no-op.

- [ ] **Step 2: thesis-chapter-writer.** Next to the `[tikz-libraries]`
  instruction: when the render prints a `[unicode]` line, quote it and
  tell the user to copy `chitragupta-unicode.sty` next to their thesis
  and add `\usepackage{chitragupta-unicode}` to its preamble. Never
  suggest rewriting the characters in the fragment to get the build
  through.

- [ ] **Step 3: docs/CLI.md.** Three short paragraphs: the sanitiser
  no longer rewrites text (#948); a pdf/tex render loads
  `chitragupta-unicode.sty` when the draft needs it, and a fragment
  gets it beside the output; `content/unicode-extra.tex`, if present,
  is added to every standalone LaTeX/PDF render's preamble.

- [ ] **Step 4: Version.** Bump `pyproject.toml`'s `version` by MINOR
  from what Task 0 recorded (6.129.1 → 6.130.0 if unchanged).

- [ ] **Step 5: Full verification** (DEVELOPER-AGENTS.md, "Before
  claiming a task complete")

```bash
.venv-full/bin/python -m pytest --cov --cov-report=term-missing
bash scripts/check_local.sh
```

Expected: all pass, coverage 100%. Then render a draft that has every
example from #948 to PDF by hand and open it:

```bash
.venv-full/bin/python -m chitragupta.draft render content/drafts/<a-scratch-draft>.md --format pdf
```

Check by eye: `H₂O` has a real subscript, `𝑡` is italic, `5 µm` and
`R²` are as written.

- [ ] **Step 6: Record the outcome and commit**

Change this file's `Status:` line to say which PR closed it and
anything that changed on the way.

```bash
git add .claude/skills docs/CLI.md pyproject.toml plans/948-latex-unicode-characters.md
git commit -m "Document chitragupta-unicode.sty for book and thesis authors; bump to 6.130.0 (#948)"
```

## Self-review notes

- **Issue coverage.** "Leave everything else as written": Task 1.
  "Pin `µm`, `m²`, `H₂O`": Task 1's table and Task 3's pdf render. The
  property test: Task 1, exhaustive in place of hypothesis. The
  pdflatex round trip of `5 µm`: Task 3. The issue's own fix said "fold
  only U+1D400–U+1D7FF"; this plan folds nothing and prints the block
  instead, a superset agreed in the discussion.
- **Mid-branch regression.** After Task 1 alone, #389's `𝑡` fails a
  PDF again. Tasks 1–3 merge together.
- **Unicode version drift.** The generator reads `unicodedata`, whose
  version follows Python's. The blocks it reads have not changed since
  Unicode 6.0, so CI's 3.13 and a local 3.12 produce the same file. If
  that ever changes, the drift test says so on the newer Python, and
  the fix is to pin the ranges, not to skip the test.
