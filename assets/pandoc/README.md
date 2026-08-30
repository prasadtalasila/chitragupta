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
