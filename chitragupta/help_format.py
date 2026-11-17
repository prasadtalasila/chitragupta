"""Click-style `--help` for the command dispatchers (#1230).

The front door and the corpus and draft layers each list their commands.
argparse would wrap that list into one paragraph; this module prints it
the way Python's click does instead: one command per line, its help cut to
one line, the full text one level down in that command's own `--help`.

Standard library only. `draft gate` must run on a bare interpreter, and
the top-level tree must never pay for a layer's imports.
"""


def truncate(text: str, limit: int) -> str:
    """The first sentence or ` -- ` clause if it fits, else a word cut
    marked `...`. Never edits the source string, only what is printed."""
    text = text.strip()
    breaks = [i for i in (text.find(". "), text.find(" -- ")) if i > 0]
    if breaks and min(breaks) <= limit:
        out = text[: min(breaks)]
    elif len(text) <= limit:
        out = text.rstrip(".")
    else:
        head = text[: limit - 3]
        out = (head.rsplit(" ", 1)[0] if " " in head else head).rstrip(",:;") + "..."
    return out[:1].upper() + out[1:]


def commands_block(rows: list[tuple[str, str]], width: int) -> str:
    """One aligned row per command. A name's leading spaces nest it under
    the row above, which is how the top-level tree shows a layer's verbs.

    The limit is click's: what the terminal leaves after the name column,
    never below 45 so a narrow terminal still gets a readable line."""
    widest = max(len(name) for name, _ in rows)
    limit = max(width - 6 - widest, 45)
    return "\n".join(f"  {name.ljust(widest)}  {truncate(text, limit)}" for name, text in rows)
