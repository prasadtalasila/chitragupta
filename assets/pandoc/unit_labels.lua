-- Prefix a fragment's derived heading labels with its unit id (#1122).
--
-- pandoc labels a heading from its text when the author gave it no
-- `{#id}`, so two book units that each have a "Summary" section both
-- define `\label{summary}` and the assembled book defines it twice.
-- `chitragupta/render_output/_unit_labels.py` loads this filter on a
-- `--fragment` render only and passes the prefix (`<stem>-`) as
-- `chitragupta-label-prefix` metadata.
--
-- Three passes, in order. The first reads the prefix and the ids the
-- author wrote. The second renames every other heading id. The third
-- points in-unit links at the renamed ids, so `[see](#exercises)` still
-- reaches its section; a link to an id this unit did not rename is
-- another unit's anchor and is left alone.
--
-- An authored id is read from the source rather than the AST, because
-- once the reader has run a written `{#summary}` and a derived
-- `summary` look identical. Both spellings count: a Markdown attribute
-- `{#id ...}` and a LaTeX `\label{id}` (pandoc's LaTeX reader makes the
-- latter the heading's id). A match inside a code sample only keeps
-- that id unprefixed, which is how every id was before this filter.

local prefix = nil
local authored = {}
local renamed = {}

local function read_authored()
  for _, path in ipairs(PANDOC_STATE.input_files) do
    local file = io.open(path, "r")
    if file then
      local text = file:read("a")
      file:close()
      for id in text:gmatch("{%s*#([^%s}]+)") do
        authored[id] = true
      end
      for id in text:gmatch("\\label{([^}]+)}") do
        authored[id] = true
      end
    end
  end
end

return {
  {
    Meta = function(meta)
      local value = meta["chitragupta-label-prefix"]
      if value then
        prefix = pandoc.utils.stringify(value)
        read_authored()
      end
    end,
  },
  {
    Header = function(header)
      local id = header.identifier
      if prefix and id ~= "" and not authored[id] then
        renamed[id] = prefix .. id
        header.identifier = renamed[id]
        return header
      end
    end,
  },
  {
    Link = function(link)
      local id = link.target:match("^#(.+)$")
      if id and renamed[id] then
        link.target = "#" .. renamed[id]
        return link
      end
    end,
  },
}
