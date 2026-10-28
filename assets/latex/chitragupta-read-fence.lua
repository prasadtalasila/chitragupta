-- chitragupta's TeX read fence (#823, #1037). Loaded with `--lua=` by
-- chitragupta/tex_engine.py into every TeX engine this codebase starts on
-- draft text: the pdf render and the figure-layout probe.
--
-- A draft, a figure file or a collaborator's .bib must not make TeX read
-- a file outside the draft, such as ~/.ssh/id_rsa or ../../secret. That
-- used to be kpathsea's `openin_any=p`. TeX Live 2024 changed it to
-- restrict absolute paths to TEXMFOUTPUT, which luaotfload trips over on
-- every LuaLaTeX run (it opens ScriptExtensions.txt by absolute path from
-- texmf-dist), and TeX Live 2026 drops the read check entirely. This
-- callback is engine-level, so it holds the same on all three.
--
-- It sees TeX's own reads, \input and \openin. Lua's io.open does not
-- pass through it, which is what lets the font loader work; \directlua
-- was already an accepted residual (docs/SECURITY.md).

local main_seen = false
-- The directory the main file is in, with a trailing separator. pandoc
-- compiles in its own `$TMPDIR/tex2pdf.*/`, copies the draft's images
-- there, and names them absolutely; `openin_any=p` admitted them because
-- pandoc points TEXMFOUTPUT at that directory, and this keeps the same
-- boundary: nothing but what the caller put there is in it.
local compile_dir = nil

local function is_absolute(name)
  return name:match("^[/\\]") or name:match("^%a:[/\\]")
end

-- A `..` component, or one starting with a dot (but `.` itself, which
-- names the working directory).
local function climbs_or_hides(name)
  for part in name:gmatch("[^/\\]+") do
    if part == ".." or (part ~= "." and part:sub(1, 1) == ".") then
      return true
    end
  end
  return false
end

local function outside_the_draft(name)
  if is_absolute(name) then
    if not (compile_dir and name:sub(1, #compile_dir) == compile_dir) then
      return true
    end
    return climbs_or_hides(name:sub(#compile_dir + 1))
  end
  return climbs_or_hides(name)
end

local function directory_of(path)
  if not is_absolute(path) then
    -- kpathsea answers `./probe.tex` for a main file named relatively.
    path = lfs.currentdir() .. "/" .. path:gsub("^%./", "")
  end
  return path:match("^(.*[/\\])")
end

callback.register("find_read_file", function(_, name)
  -- The main file comes first, and pandoc names it absolutely
  -- (`$TMPDIR/tex2pdf.*/input.tex`); everything after it is draft text.
  if not main_seen then
    main_seen = true
    local found = kpse.find_file(name, "tex", true) or name
    compile_dir = directory_of(found)
    return found
  end
  if outside_the_draft(name) then
    texio.write_nl("term and log", "chitragupta: refused TeX read of " .. name)
    return nil
  end
  return kpse.find_file(name, "tex", true)
end)
