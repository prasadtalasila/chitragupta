-- Print raw TeX that came out of a `.bib` field as the text it is,
-- never as TeX the PDF engine runs (#996).
--
-- pandoc's BibTeX reader is its LaTeX reader. A command it understands
-- (`\emph`, `\"u`, `\textsubscript`) becomes ordinary AST nodes; one it
-- does not becomes a RawInline in format `latex`; and `$...$`,
-- `\(...\)`, `\ensuremath{...}` become a Math node that keeps its source
-- verbatim. citeproc carries all of these into the reference list and
-- the citations unchanged. pdflatex rejected most unknown commands.
-- LuaLaTeX runs `\directlua{...}` -- measured: a shared `.bib` whose
-- title held `\directlua{tex.print(io.open("/abs/secret"):read("*l"))}`,
-- in text or inside `$...$`, typeset the secret into the PDF, under the
-- `openin_any=p` and `-no-shell-escape` #823 set, because those fence
-- TeX's own reads and not Lua's. See plans/996-unicode-pdf-engine.md.
--
-- So this runs straight after `--citeproc` (argv order is filter order)
-- and rewrites, inside citeproc's output only -- the `refs` Div and each
-- Cite:
--   * every raw TeX node, into Code, which the LaTeX writer escapes;
--   * any Math node whose source contains one of the few primitives that
--     run code or touch files (the rest of math -- `\alpha`, `\leq`,
--     `x^2` -- is left exactly as written, so ordinary mathematics in a
--     title still typesets).
-- The reader sees what their `.bib` says. A normal entry has no such
-- node after the reader, so its LaTeX is byte-identical with and without
-- this filter (pinned in tests/test_render_output_bib_raw_tex.py).
--
-- A draft's own raw LaTeX (an `\input` of a figure, a display equation)
-- lives outside both and is untouched: that text is the author's, and
-- the draft is theirs to run.

local function is_tex(el)
  return el.format == "latex" or el.format == "tex"
end

-- A denylist, not an allowlist, is used here on purpose. A math field in
-- a real bibliography (a chemistry or physics title) carries arbitrary
-- math commands, and an allowlist would have to name every one or render
-- legitimate math as verbatim source; the danger, by contrast, is a
-- small closed set. Under `-no-shell-escape` the only primitives that run
-- Lua are `\directlua` and `\latelua`, and the only way to invoke a
-- control sequence whose name is not spelled out in the source (so that
-- it would be caught here) is `\csname ...\endcsname`. Both, and the two
-- that invoke an already-registered Lua function (`\luafunction`,
-- `\luafunctioncall` -- inert in a `.bib` field, since only `\directlua`
-- could have registered one, and that is blocked, but listed for depth),
-- are here. The rest are TeX's own file and state primitives, already
-- bounded by `openin_any=p`/`openout_any=p` but refused here too.
-- Verified: six crafted titles (plain, `\csname`-built, `\latelua`,
-- `\let`-aliased, `\uccode`/`\lowercase`, and the `^^5c` input escape
-- handled above) all failed to read a file through a real lualatex
-- compile. A control word matches on a word boundary, so `\read` matches
-- but `\readable` does not.
local DANGEROUS = {
  "directlua", "latelua", "luafunction", "luafunctioncall", "csname",
  "input", "include", "openin", "read", "write", "immediate", "special",
  "catcode", "endlinechar", "usepackage", "RequirePackage", "openout",
}

local function runs_code(text)
  -- `^^` is TeX's input-level escape: `^^5c` becomes a backslash before
  -- any control word is formed, so `^^5cdirectlua{...}` reaches the engine
  -- as `\directlua` and the name-match below never sees it (measured: it
  -- ran). No legitimate math title uses the notation, so any `^^` is
  -- treated as code.
  if text:find("%^%^") then
    return true
  end
  for _, name in ipairs(DANGEROUS) do
    if text:find("\\" .. name .. "%f[^%a]") then
      return true
    end
  end
  return false
end

local as_text = {
  RawInline = function(el)
    if is_tex(el) then
      return pandoc.Code(el.text)
    end
  end,
  RawBlock = function(el)
    if is_tex(el) then
      return pandoc.CodeBlock(el.text)
    end
  end,
  Math = function(el)
    if runs_code(el.text) then
      return pandoc.Code(el.text)
    end
  end,
}

function Pandoc(doc)
  return doc:walk({
    Div = function(div)
      if div.identifier == "refs" then
        return div:walk(as_text)
      end
    end,
    Cite = function(cite)
      return cite:walk(as_text)
    end,
  })
end
