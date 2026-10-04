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
