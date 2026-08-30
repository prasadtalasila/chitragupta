-- Give an inline Markdown code span (`` `like/this` ``) somewhere to
-- break when it renders to LaTeX/PDF.
--
-- Pandoc's own LaTeX writer turns inline `Code` into \texttt{...}. A
-- long, space-free span (a URL, a REST path, a file path) inside it has
-- no legal TeX break point at all once it hits the width -- typewriter
-- text has no hyphenation patterns -- so pdflatex reports an Overfull
-- \hbox and lets it bleed past the right margin instead of wrapping.
-- Measured against a real 428-page book: 23 of the largest Overfull
-- \hbox warnings (up to 235pt) were exactly this.
--
-- This filter splits a Code span into several separate Code inlines --
-- one per delimiter-bounded chunk -- joined by a raw \penalty0 (a
-- legal, hyphen-free break point), rather than re-escaping the text
-- itself into one RawInline. That distinction matters twice over: each
-- chunk still passes through pandoc's own LaTeX writer, so its
-- code-context escaping (an inline `'`/`` ` ``, a bare `_`/`{`, all
-- resolved the way pandoc already gets right) keeps applying instead of
-- being reimplemented and risking drift; and a heading's PDF-bookmark
-- text -- built by stringifying the AST -- still reads a Code inline's
-- real characters, where it would read nothing at all from an opaque
-- RawInline.
--
-- Splits after every `/` and `_`, the two delimiters that cover every
-- case seen in this project's rendered books -- deliberately not `-` or
-- `.`, where splitting `--fragment` or `1.5` mid-token would
-- misrepresent the code itself. A literal space splits too, but the
-- other way round -- ending the chunk *before* the space rather than
-- after it, so a break taken there leaves the space to open the next
-- line rather than trail the one that just ended.

local function split_code(text)
  local pieces = {}
  local current = ""
  -- By codepoint, not by byte: a code span is almost always pure ASCII
  -- (a path, a URL, an identifier), but a byte-wise split would cut a
  -- multi-byte UTF-8 character in half on the rare one that isn't.
  for _, cp in utf8.codes(text) do
    local ch = utf8.char(cp)
    if ch == " " and current ~= "" then
      table.insert(pieces, pandoc.Code(current))
      table.insert(pieces, pandoc.RawInline("latex", "\\penalty0"))
      current = ch
    elseif ch == "/" or ch == "_" then
      current = current .. ch
      table.insert(pieces, pandoc.Code(current))
      table.insert(pieces, pandoc.RawInline("latex", "\\penalty0"))
      current = ""
    else
      current = current .. ch
    end
  end
  if current ~= "" then
    table.insert(pieces, pandoc.Code(current))
  end
  return pieces
end

function Code(elem)
  if FORMAT ~= "latex" then
    return nil
  end
  -- A classed span (`` `x = 1`{.python} ``) takes pandoc's syntax-
  -- highlighting path (\VERB\NormalTok{...}...), not plain \texttt{...}
  -- -- rebuilding it as N plain Code chunks would silently drop the
  -- highlighting. Genre drafts don't classify inline code, but leaving
  -- one untouched here is cheaper than replicating its attributes onto
  -- every chunk, which would just re-run the same highlighting N times.
  if elem.attr.identifier ~= "" or #elem.attr.classes > 0 or #elem.attr.attributes > 0 then
    return nil
  end
  local pieces = split_code(elem.text)
  -- A span ending in `/` or `_` (a directory path with no trailing
  -- filename) would otherwise leave a dangling \penalty0 with nothing
  -- after it -- a legal break point pandoc's own writer could still
  -- take, stranding whatever follows in the sentence at a line start.
  if #pieces > 0 and pieces[#pieces].t == "RawInline" then
    table.remove(pieces)
  end
  return pieces
end
