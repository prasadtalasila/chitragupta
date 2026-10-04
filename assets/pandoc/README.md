# Pandoc filters

`breakable_inline_code.lua` is loaded on every pandoc invocation that can
produce LaTeX/PDF output, via `--lua-filter` in
`chitragupta/render_output/_pandoc.py:_pandoc_command()`. It re-escapes
each inline Markdown code span (`` `like/this` ``) with a `\penalty0`
break point after every `/` and `_`, so a long, space-free span -- a URL,
a REST path, a file path -- can wrap instead of bleeding past the right
margin. See the file's own header comment for why pandoc's default
`\texttt{...}` output can't do this on its own.

The filter no-ops (`FORMAT ~= "latex"`) for every other pandoc writer, so
it is safe to pass unconditionally regardless of the render's requested
output format.

`bib_raw_tex_as_text.lua` (#996) is loaded on every render that runs
`--citeproc` (all but `--fragment`, which defers citations to the book's
`bibtex`), right **after** `--citeproc` on the command line and before
`breakable_inline_code.lua`: pandoc runs citeproc and filters in argv
order, this filter rewrites what citeproc produced, and running it after
the breakable filter would turn that filter's `\penalty0` break nodes
into visible text in a `.bib` title's `\texttt`. pandoc's BibTeX reader
turns a command it does not understand into raw LaTeX, and keeps `$...$`
as a math node whose source it prints verbatim; citeproc carries both
into the reference list and the citations, where under LuaLaTeX a
`\directlua{...}` would run. The filter turns every raw TeX node inside
the `refs` Div and each Cite into a code span, which every writer
escapes, and does the same for a math node that contains a code-running
or file-reaching primitive (`\directlua`, `\csname`, `\input`, `\write`
and the like); plain mathematics is left as math. A normal entry has no
such node after the reader, so its output is byte-identical with or
without the filter.
