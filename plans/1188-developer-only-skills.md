# #1188: developer-only skills, and the demo-recorder skill

Status: **plan.** Written 2026-11-11.

**Written for** whoever adds this repository's first developer-only
skill, or a second one later. **Assumed:** the three per-harness skill
copies (docs/HARNESS.md) and the three distributions (docs/PACKAGING.md).
**Not covered here:** what the demo should show; that is the skill's own
`SKILL.md`.

## The problem

A skill under `.claude/skills/`, `.agents/skills/` or `.opencode/skills/`
reaches users three ways, and each one needs its own fix:

| Route | How it ships today | Why that ships everything |
| --- | --- | --- |
| wheel and sdist | `pyproject.toml` `include`s `.claude`, `.agents`, `.opencode` as whole folders | Poetry's `exclude` cannot carve a path out of an `include`d folder: an explicit include wins. Measured with poetry-core 2.3.1, an `exclude` of one skill folder left it in both the wheel and the sdist |
| release zip | `scripts/release.py` ships every tracked file outside `EXCLUDE_TOP_LEVEL` | it filters by top-level name only |
| `chitragupta init` | copies `COPY_VERBATIM` and `AGENT_TREES` from `SOURCE_ROOT` | in an editable install `SOURCE_ROOT` is the checkout, so the wheel's exclusions do not reach it |

## Decisions

1. **The skill lives with the others.** It sits in all three harness
   folders, so a checkout or worktree picks it up with no setup, and
   `tests/test_skill_harness_copies.py` keeps its copies in step like any
   other skill. A separate top-level folder plus a script that links it
   into the harness folders was rejected: the skill would be missing in
   every fresh clone and worktree, and a local `poetry build` after
   linking would ship it anyway, since the explicit `include` also beats
   `.gitignore`.
2. **The skill marks itself.** Its frontmatter carries
   `metadata:` / `audience: developer`. `metadata` is an Agent Skills
   field, so every harness loads it. A list somewhere else would be a
   second place to keep in step.
3. **One helper reads the marker.** `chitragupta/developer_skills.py`
   is stdlib-only and imports nothing from the package, because
   `scripts/release.py` loads it by path (the `merge_pr.py` idiom).
   `init.scaffold` and `release.tracked_files` both skip what it finds.
   `init` also skips `.claude/worktrees/`: in an editable install it
   would otherwise copy every Claude Code worktree of the checkout, each
   with its own copy of the skill, which the marker scan of the three
   top-level trees does not reach. (Found in review. That copy predates
   this plan, but left alone it defeats the skip.)
4. **`pyproject.toml` names what ships.** Each harness folder's entries
   are listed one by one: its non-skill entries and every skill folder
   that is not developer-only. `tests/test_developer_skills.py` derives
   the expected list from `git ls-files` and the marker, so adding a
   user skill without its three `include` lines fails CI. As a side
   effect, a local `poetry build` no longer ships `.claude/worktrees/`.
5. **OpenCode's deny list names it.** `.opencode/opencode.json` gains
   `"demo-recorder": "deny"`, like every other skill. That file ships, so
   users get one deny rule for a skill they do not have. A deny rule for
   an absent name is inert, and `chitragupta doctor` reads only the names
   that exist, so this costs nothing.
6. **The recorder's code ships with the skill.** `tour.sh`,
   `retime_cast.py` and `capture_topic_map.js` live in
   `.claude/skills/demo-recorder/scripts/`, so the marker that drops the
   skill drops its code too. `retime_cast.py` merges the two original
   retiming scripts into one. It is tested, and its folder is added to
   the coverage `source`.

## Steps and their checks

1. Tests first: helper, `init` skip, `release.py` skip, include-list
   pin, `retime_cast.py`. All red.
2. Helper, `init`, `release.py`, `pyproject.toml`. Green.
3. The skill in three harness copies plus the deny rule;
   `tests/test_skill_*` green, with the skill counts the user-facing
   docs state left at eleven.
4. Build the wheel and sdist for real and list `demo-recorder` in
   neither.
