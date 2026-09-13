"""One context window, divided into named budgets. Pure, and in one table.

`docs/TOKENS.md` analyses where a run's tokens go; until this module it
handed the genre skills nothing to call. Every skill in `.claude/skills/`
that retrieves described its own budget in its own prose, which meant a
set of budgets that could not be compared against each other, could not
be tested, and drifted as the skills were edited independently.

**Why the weights are a module-level table and not per-skill
frontmatter.** A table in code is the thing that makes the budgets
comparable in a single diff: changing what a survey may spend on
retrieved passages relative to what a thesis chapter may spend is one
edit, in one place, reviewable as a unit. Per-skill frontmatter would
reintroduce exactly the drift this module exists to remove -- it is the
prose budget again, wearing YAML.

**Why the window size is an argument and not read from `config.toml`
here.** This function is pure and does no I/O, so it can be tested
exhaustively and cannot behave differently on two machines. The window
itself is genuinely a property of the *host*, not of the pipeline -- a
user on a smaller or larger model has to retune it -- so it lives in
`[tokens] window_size` and is read by the **caller**
(`chitragupta.config.TOKENS_WINDOW_SIZE`) and passed in. Those two
choices are the same choice: the part that varies per machine is
configuration, the part that must be comparable across skills is code.

Concept adapted from llm_wiki, which has the same idea as a pure
function. Nothing was copied: that project is GPL-3.0 and this one is
MIT, so the section names and the reserve fraction here were chosen for
this pipeline rather than taken. Its sections are index, pages, history
and a response reserve; these are the dossier, the retrieved passages,
the draft under edit, and a reserve. See `docs/INSPIRATION.md`.

This is a planning aid, not a new lever on residency. It says how much a
skill may *deliberately* put in front of the model; it does not change
what a turn re-sends, which is the multiplier `docs/TOKENS.md` is about,
and it promotes no new check into a gate.
"""

from types import MappingProxyType

# The three sections a skill actually fills, in the order a run fills
# them. The numbers are parts per hundred of the whole window, not of the
# spendable remainder, so that `passages` at a given window means one
# number whichever skill asked -- see `allocate` on why a named subset
# does not reshare what it left behind.
WORKING_WEIGHTS = MappingProxyType({"dossier": 15, "passages": 45, "draft": 25})

# Never selectable, always returned, and taken off the top. This is what
# the model needs left over to answer with; a skill that could decline it
# would be a skill that could fill the window and then have nowhere to
# write, which is the failure the reserve exists to prevent.
RESERVE_SECTION = "reserve"
RESERVE_WEIGHT = 15

# Below roughly 6,827 tokens the proportional reserve is smaller than any
# usable answer, so a floor takes over and the working sections get what
# is left rather than the reserve being shaved to keep them whole. That
# direction is the whole point: a tiny window is a window that can pay
# for an answer or for context, and an unanswerable run is worse than a
# thinly grounded one.
RESERVE_FLOOR = 1024

_WHOLE = 100
_WORKING_TOTAL = _WHOLE - RESERVE_WEIGHT


def _checked_window(window_size: int) -> int:
    """`window_size` as a non-negative `int`, or the reason it is not.

    `bool` is rejected explicitly, for the reason `config._get_bool`'s
    neighbours reject it: `bool` is an `int` in Python, so `allocate(True)`
    would otherwise quietly mean a one-token window, and a caller who
    wrote that meant something else entirely.
    """
    if isinstance(window_size, bool) or not isinstance(window_size, int):
        raise TypeError(f"window_size must be an int, not {type(window_size).__name__}")
    if window_size < 0:
        raise ValueError(f"window_size must not be negative, got {window_size}")
    return window_size


def _checked_sections(sections) -> tuple:
    """The requested section names, each one known and none of them the
    reserve. Unknown names are rejected rather than ignored: a typo that
    silently allocated nothing would show up as a skill retrieving far
    less than it meant to, with nothing saying why."""
    if sections is None:
        return tuple(WORKING_WEIGHTS)
    requested = tuple(sections)
    for name in requested:
        if name == RESERVE_SECTION:
            raise ValueError(
                f"{RESERVE_SECTION!r} is always allocated and cannot be requested as a section"
            )
        if name not in WORKING_WEIGHTS:
            raise ValueError(
                f"unknown section {name!r}; known sections are {sorted(WORKING_WEIGHTS)}"
            )
    return requested


def allocate(window_size: int, sections=None) -> dict:
    """Per-section token budgets for a window of `window_size` tokens.

    `sections` names which working sections to size, defaulting to all of
    them; `RESERVE_SECTION` is always present in the result and may not
    be named. The budgets are floored integers and always sum to no more
    than `window_size`.

    **A named subset does not reshare what it left behind.** Asking for
    `("passages",)` alone gives `passages` the same number the full set
    would have, and simply leaves the rest of the window unallocated.
    Resharing would make a section's budget depend on which *other*
    sections the caller happened to want, and then two skills' budgets
    could not be compared without also comparing their section sets --
    which is the drift this module was written to end.

    Degenerate inputs are defined rather than incidental: an empty
    `sections` returns the reserve alone, a `window_size` of zero returns
    zero for every section, and a window too small to pay the reserve
    floor spends all of itself on the reserve.
    """
    window_size = _checked_window(window_size)
    requested = _checked_sections(sections)
    reserve = min(window_size, max(RESERVE_FLOOR, window_size * RESERVE_WEIGHT // _WHOLE))
    spendable = window_size - reserve
    budgets = {name: spendable * WORKING_WEIGHTS[name] // _WORKING_TOTAL for name in requested}
    budgets[RESERVE_SECTION] = reserve
    return budgets
