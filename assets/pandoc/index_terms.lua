-- Place one `\index{<id>}` per term per chapter, for the book's index (#1168).
--
-- `chitragupta/render_output/_index_terms.py` loads this filter only when
-- `draft render --index-terms` names the book's term table
-- (`index-terms.json`, written by `registry build --index`), and passes
-- three metadata values: that file, this chapter's unit id, and where to
-- write this chapter's sidecar.
--
-- This filter answers one question, "where is the term?", and nothing
-- about how the index prints it. It writes an opaque ASCII id, never the
-- term itself: an `\index{}` can land inside a `\footnote{}` whose
-- argument TeX has already tokenised, where a `%` or `#` in a printed
-- form would break. `registry index` (`chitragupta/registry/_index_finish.py`)
-- turns ids into printed entries once the book is typeset.
--
-- Two passes over the chapter. The first finds every match: prose is
-- flattened into words across emphasis, links and quotes, lowercased,
-- edge punctuation and a possessive dropped, a hyphen or dash splitting
-- a word; at each word the longest spelling wins, the last word may
-- differ by a plural `s` or `es` either way, and matches never overlap.
-- Headings, captions, code, maths, raw TeX, citations and the sections
-- `skip_sections` names are never read. The second pass places one entry, after the top-level
-- inline holding the term's first match, in a chapter that defines the
-- term (bold), lists it under `[always]`, or mentions it at least
-- `min_mentions` times. The sidecar records each term's count, whether it
-- was placed, the count per spelling and the casing of each mention that
-- is not sentence-initial, which `registry index` reads for the printed
-- form and the report.

local config = nil
local digest = nil
local unit = nil
local sidecar = nil
local by_first = {}
local skip_titles = {}
local found = {}

local QUOTES = { "“", "”", "‘", "’", "«", "»" }

local function strip_edges(word)
  local changed = true
  while changed and word ~= "" do
    changed = false
    local trimmed = word:gsub("^%p+", ""):gsub("%p+$", "")
    if trimmed ~= word then
      word, changed = trimmed, true
    end
    for _, quote in ipairs(QUOTES) do
      if word:sub(1, #quote) == quote then
        word, changed = word:sub(#quote + 1), true
      end
      if #word >= #quote and word:sub(-#quote) == quote then
        word, changed = word:sub(1, -#quote - 1), true
      end
    end
  end
  return word
end

local function words_of(text)
  local words = {}
  for word in text:gmatch("%S+") do
    words[#words + 1] = word
  end
  return words
end

local function load_terms(path)
  local file = assert(io.open(path, "rb"))
  local raw = file:read("a")
  file:close()
  config = pandoc.json.decode(raw, false)
  digest = pandoc.utils.sha1(raw)
  for id, term in pairs(config.terms) do
    for _, spelling in ipairs(term.spellings) do
      local words = words_of(spelling)
      local list = by_first[words[1]] or {}
      list[#list + 1] = { id = id, words = words, spelling = spelling }
      by_first[words[1]] = list
    end
  end
  for _, list in pairs(by_first) do
    table.sort(list, function(a, b)
      if #a.words ~= #b.words then
        return #a.words > #b.words
      end
      return a.spelling < b.spelling
    end)
  end
  for _, title in ipairs(config.skip_sections) do
    skip_titles[pandoc.text.lower(title)] = true
  end
end

-- The words of one inline list, each pointing back at the top-level
-- inline it sits in. A barrier (code, maths, a citation) breaks a phrase.
local flatten

local function add_str(out, text, top, list)
  local ends_sentence = text:match("[%.!?][%p”’»]*$") ~= nil
  -- A possessive goes; `’` is three bytes, so it is no character class.
  text = text:gsub("’s$", ""):gsub("'s$", ""):gsub("–", "-"):gsub("—", "-")
  for part in text:gmatch("[^-]+") do
    local word = strip_edges(part)
    if word ~= "" then
      out[#out + 1] = {
        word = pandoc.text.lower(word),
        original = word,
        top = top,
        list = list,
        initial = out.sentence_end,
      }
      out.sentence_end = false
    end
  end
  if ends_sentence then
    out.sentence_end = true
  end
end

local CONTAINERS = {
  Emph = true, Strong = true, SmallCaps = true, Span = true, Quoted = true,
  Link = true, Underline = true, Strikeout = true, Superscript = true, Subscript = true,
}

local walk_blocks

flatten = function(inlines, out, top, list, notes)
  for index, inline in ipairs(inlines) do
    local here = top or index
    local owner = list or inlines
    if inline.t == "Str" then
      add_str(out, inline.text, here, owner)
    elseif CONTAINERS[inline.t] then
      flatten(inline.content, out, here, owner, notes)
    elseif inline.t == "Note" then
      notes[#notes + 1] = inline.content
      out[#out + 1] = { barrier = true }
    elseif inline.t ~= "Space" and inline.t ~= "SoftBreak" and inline.t ~= "LineBreak" then
      out[#out + 1] = { barrier = true }
    end
  end
  return out
end

-- The last word may differ by a plural `s` or `es` either way: the
-- glossary may name a term in the plural ("lifecycle phases") that the
-- prose uses in the singular, or the other way round.
local function word_matches(word, wanted, last)
  if word == wanted then
    return true
  end
  if not last then
    return false
  end
  return word == wanted .. "s" or word == wanted .. "es" or wanted == word .. "s" or wanted == word .. "es"
end

local function candidates(word)
  local list = by_first[word]
  if list then
    return list
  end
  -- A one-word term, its first word its last, in the other number.
  return by_first[(word:gsub("es$", ""))]
    or by_first[(word:gsub("s$", ""))]
    or by_first[word .. "s"]
    or by_first[word .. "es"]
    or {}
end

local function match_at(tokens, start)
  for _, candidate in ipairs(candidates(tokens[start].word)) do
    local ok = true
    for offset, wanted in ipairs(candidate.words) do
      local token = tokens[start + offset - 1]
      if not token or token.barrier or not word_matches(token.word, wanted, offset == #candidate.words) then
        ok = false
        break
      end
    end
    if ok then
      return candidate
    end
  end
  return nil
end

local function record(candidate, tokens, start)
  local entry = found[candidate.id] or { count = 0, spellings = {}, midsentence = {}, first = nil }
  found[candidate.id] = entry
  entry.count = entry.count + 1
  entry.spellings[candidate.spelling] = (entry.spellings[candidate.spelling] or 0) + 1
  entry.first = entry.first or tokens[start]
  if not tokens[start].initial then
    local surface = {}
    for offset = 1, #candidate.words do
      surface[offset] = tokens[start + offset - 1].original
    end
    local text = table.concat(surface, " ")
    entry.midsentence[text] = (entry.midsentence[text] or 0) + 1
  end
end

local function scan(inlines)
  local notes = {}
  local tokens = flatten(inlines, { sentence_end = true }, nil, nil, notes)
  local index = 1
  while index <= #tokens do
    local candidate = not tokens[index].barrier and match_at(tokens, index)
    if candidate then
      record(candidate, tokens, index)
      index = index + #candidate.words
    else
      index = index + 1
    end
  end
  for _, blocks in ipairs(notes) do
    walk_blocks(blocks, { level = nil })
  end
end

local function walk_rows(rows)
  for _, row in ipairs(rows) do
    for _, cell in ipairs(row.cells) do
      walk_blocks(cell.contents, { level = nil })
    end
  end
end

local function walk_table(tbl)
  walk_rows(tbl.head.rows)
  for _, body in ipairs(tbl.bodies) do
    walk_rows(body.head)
    walk_rows(body.body)
  end
  walk_rows(tbl.foot.rows)
end

local LISTS = { BulletList = true, OrderedList = true }
local NESTED = { BlockQuote = true, Div = true }

walk_blocks = function(blocks, skip)
  for _, block in ipairs(blocks) do
    if block.t == "Header" then
      if skip.level and block.level <= skip.level then
        skip.level = nil
      end
      if not skip.level and skip_titles[pandoc.text.lower(pandoc.utils.stringify(block.content))] then
        skip.level = block.level
      end
    elseif skip.level then
      -- Inside a skipped section: nothing here is read.
    elseif block.t == "Para" or block.t == "Plain" then
      scan(block.content)
    elseif block.t == "LineBlock" then
      for _, line in ipairs(block.content) do
        scan(line)
      end
    elseif LISTS[block.t] then
      for _, item in ipairs(block.content) do
        walk_blocks(item, skip)
      end
    elseif block.t == "DefinitionList" then
      for _, item in ipairs(block.content) do
        scan(item[1])
        for _, definition in ipairs(item[2]) do
          walk_blocks(definition, skip)
        end
      end
    elseif NESTED[block.t] then
      walk_blocks(block.content, skip)
    elseif block.t == "Table" then
      walk_table(block)
    end
  end
end

local function contains(list, value)
  for _, item in ipairs(list) do
    if item == value then
      return true
    end
  end
  return false
end

local function place()
  local inserts = {}
  for id, entry in pairs(found) do
    local term = config.terms[id]
    local defines = contains(term.defined_in, unit)
    entry.indexed = defines or contains(term.always, unit) or entry.count >= config.min_mentions
    if entry.indexed then
      local key = defines and (id .. "|textbf") or id
      inserts[#inserts + 1] = { list = entry.first.list, top = entry.first.top, key = key }
    end
  end
  -- Last position first, so an insertion never moves one still to come.
  table.sort(inserts, function(a, b)
    if a.top ~= b.top then
      return a.top > b.top
    end
    return a.key > b.key
  end)
  for _, insert in ipairs(inserts) do
    insert.list:insert(insert.top + 1, pandoc.RawInline("latex", "\\index{" .. insert.key .. "}"))
  end
end

local function write_sidecar()
  local terms = {}
  for id, entry in pairs(found) do
    terms[id] = {
      count = entry.count,
      indexed = entry.indexed,
      spellings = entry.spellings,
      midsentence = entry.midsentence,
    }
  end
  local file = assert(io.open(sidecar, "w"))
  file:write(pandoc.json.encode({ unit = unit, terms_digest = digest, terms = terms }), "\n")
  file:close()
end

function Pandoc(doc)
  local meta = doc.meta
  if not meta["chitragupta-index-terms"] then
    return nil
  end
  load_terms(pandoc.utils.stringify(meta["chitragupta-index-terms"]))
  unit = pandoc.utils.stringify(meta["chitragupta-index-unit"])
  sidecar = pandoc.utils.stringify(meta["chitragupta-index-sidecar"])
  walk_blocks(doc.blocks, { level = nil })
  place()
  write_sidecar()
  return doc
end
