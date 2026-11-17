"""Click-style `--help` for the command dispatchers (#1230).

The front door and the corpus and draft layers each list their commands.
argparse would wrap that list into one paragraph; this module prints it
the way Python's click does instead: one command per line, its help cut to
one line, the full text one level down in that command's own `--help`.

Standard library only. `draft gate` must run on a bare interpreter, and
the top-level tree must never pay for a layer's imports.
"""

import argparse
import shutil
import sys
import textwrap

USAGE = "%(prog)s [OPTIONS] COMMAND [ARGS]..."


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


def parser_kwargs() -> dict:
    """`suggest_on_error` gives a mistyped command "did you mean" on 3.14
    and later. On 3.12 and 3.13 the keyword raises TypeError, and
    pyproject.toml still supports both."""
    if sys.version_info >= (3, 14):
        return {"suggest_on_error": True}
    return {}


class ClickFormatter(argparse.HelpFormatter):
    """`Usage:` rather than `usage:`, and the description indented two
    spaces under it, as click prints them."""

    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix="Usage: ")

    def _fill_text(self, text, width, indent):
        pad = indent + "  "
        return textwrap.fill(
            " ".join(text.split()), width, initial_indent=pad, subsequent_indent=pad
        )


class _Dispatcher(argparse.ArgumentParser):
    """An argparse parser whose help ends with a click-style `Commands:`
    list. The list is display only: what parses is `choices`."""

    def format_help(self) -> str:
        width = shutil.get_terminal_size().columns
        block = commands_block(self.command_rows, width)
        return f"{super().format_help()}\nCommands:\n{block}\n\n  {self.command_hint}\n"


def dispatcher_parser(
    prog: str,
    description: str,
    rows: list[tuple[str, str]],
    dest: str,
    choices: list[str] | None = None,
    hint: str | None = None,
) -> argparse.ArgumentParser:
    """The parser every dispatcher uses: one command, and everything after
    it forwarded verbatim to that command's own parser.

    REMAINDER, so a command can take its own `-h`/`--help` and this
    parser never sees it."""
    parser = _Dispatcher(
        prog=prog,
        description=description,
        usage=USAGE,
        formatter_class=ClickFormatter,
        add_help=False,
        **parser_kwargs(),
    )
    parser.command_rows = rows
    parser.command_hint = hint or f"Run '{prog} COMMAND --help' for a command's flags."
    parser._optionals.title = "Options"
    parser.add_argument("-h", "--help", action="help", help="Show this message and exit.")
    parser.add_argument(
        dest,
        choices=choices if choices is not None else [name for name, _ in rows],
        nargs="?",
        metavar="COMMAND",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("rest", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    return parser
