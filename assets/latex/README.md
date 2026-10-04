# LaTeX assets

## `chitragupta-lualatex.tex`

What chitragupta's own `pdf` render adds to its preamble (#996). A pdf
render runs LuaLaTeX with the fonts in `chitragupta/pdf_fonts.py`; this
file makes a character no font in that chain has a build error that
names the character, instead of a silent gap in the PDF:
`\tracinglostchars=3`, plus a `glyph_not_found` callback whose message
(`! Missing character: There is no X (U+XXXX) ...`) is the one line
pandoc shows. `chitragupta/render_output/_cli.py` reads that message
for its `[unicode]` hint. A `tex` or `--fragment` output never gets this
file: whoever compiles those chooses their own engine.

## `chitragupta-unicode.sty`

Tells pdflatex how to print about 1,900 Unicode characters its default
fonts cannot: math-style letters (𝑡 𝐀 ℝ), Greek, sub- and superscript
digits (₂), Roman numerals (Ⅳ), circled numbers (①) and the common math
operators (≤ ∈ →). The rest are the characters the pre-#948 NFKC fold
used to turn into plain text (a thin space, `（`, `⑴`, `‼`, `⅓`), printed
as that text so a draft that compiled before still does. It is
**generated**: run `python -m scripts.generate_unicode_sty`, never edit
it by hand. `tests/test_unicode_sty.py` fails when the two disagree.

**Who it is for, since #996.** chitragupta's own `pdf` renders run
LuaLaTeX, which prints these characters from its font chain
(`tests/test_render_output_fonts.py` renders all 1,873), so a pdf render
no longer loads this file. It is kept because a `.tex` output or a
`--fragment` is compiled later by someone else's document, and most
university thesis templates are pdflatex.
`chitragupta draft render` copies it beside such an output when the
draft contains one of these characters
(`chitragupta/render_output/_unicode.py`); the document that `\input`s a
fragment loads it with `\usepackage{chitragupta-unicode}`. It costs
nothing to keep: under LuaLaTeX or XeLaTeX it ends at its `\ifPDFTeX`
guard.

Three properties a change must keep (#948):

- **It never changes the text.** Each line says how to *draw* a
  character; the draft keeps it.
- **It never overrides LaTeX.** A character the kernel, or the user's own
  preamble, already prints keeps that glyph.
- **It does nothing under XeLaTeX or LuaLaTeX,** which read Unicode
  themselves.

A character in none of its tables still stops a pdflatex build, naming
the character. A project can add its own in `content/unicode-extra.tex`,
for example `\DeclareUnicodeCharacter{2603}{\ensuremath{\ast}}`. That
file reaches a render behind a shim that defines
`\DeclareUnicodeCharacter` on `newunicodechar` where the engine lacks it,
so the same line also works in chitragupta's own LuaLaTeX pdf render.
