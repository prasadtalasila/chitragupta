"""Click-style `--help` for every command in this package (#1230).

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
    """The whole line if it fits; else its first ` -- ` clause if that
    fits; else a word cut marked `...`. Never edits the source string,
    only what is printed.

    No sentence cuts: a full stop is as often `e.g.` or `vs.` as the end
    of a sentence, and cutting there printed "E.g". A word cut that would
    keep less than half the line is a hard cut instead."""
    text = text.strip()
    if len(text) <= limit:
        out = text.rstrip(".")
    elif 0 < text.find(" -- ") <= limit:
        out = text[: text.find(" -- ")]
    else:
        head = text[: limit - 3]
        word = head.rsplit(" ", 1)[0]
        out = (word if len(word) >= len(head) // 2 else head).rstrip(",:;. ") + "..."
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
    """`Usage:` rather than `usage:`, the usage line collapsed to
    `[OPTIONS]` and the positionals, the description indented two spaces
    under it, and every help line capitalised, as click prints them."""

    def add_usage(self, usage, actions, groups, prefix=None) -> None:
        # argparse passes prefix="" when it computes a subcommand's prog
        # from this one's usage; only the printed form gets the label.
        super().add_usage(usage, actions, groups, "Usage: " if prefix is None else prefix)

    def _format_usage(self, usage, actions, groups, prefix) -> str:
        if usage is None:
            usage = " ".join(["%(prog)s", *_usage_parts(actions)])
        return super()._format_usage(usage, actions, groups, prefix)

    def _get_default_metavar_for_positional(self, action) -> str:
        # Upper case, as the collapsed usage line names a positional; a
        # positional with `choices` still lists them here, as argparse does.
        return action.dest.upper()

    def _expand_help(self, action) -> str:
        """Capitalised like click's, unless the line opens with something
        the reader would type -- one of the argument's choices, or a token
        such as `enrich/gpu-torch` -- whose case is part of its value."""
        text = super()._expand_help(action)
        first = text.split(" ", 1)[0]
        word = first.replace("-", "").replace("'", "")
        if not word.isalpha() or first in (action.choices or ()):
            return text
        return text[:1].upper() + text[1:]

    def _fill_text(self, text, width, indent) -> str:
        pad = indent + "  "
        return textwrap.fill(
            " ".join(text.split()), width, initial_indent=pad, subsequent_indent=pad
        )


def _usage_parts(actions) -> list[str]:
    """`[OPTIONS]` when there is any option, `--help` included, then each
    positional by its metavar, shaped by its nargs; a subcommand group is
    `COMMAND [ARGS]...`. Click's usage line, which never lists flags."""
    options = any(a.option_strings and a.help != argparse.SUPPRESS for a in actions)
    parts = ["[OPTIONS]"] if options else []
    for action in actions:
        if isinstance(action, argparse._SubParsersAction):
            parts.append("COMMAND [ARGS]...")
        elif not action.option_strings and action.help != argparse.SUPPRESS:
            parts.append(_positional_usage(action))
    return parts


def _positional_usage(action) -> str:
    name = action.metavar if isinstance(action.metavar, str) else action.dest.upper()
    if action.nargs == "?":
        return f"[{name}]"
    if action.nargs == "*":
        return f"[{name}]..."
    if action.nargs == "+":
        return f"{name}..."
    if isinstance(action.nargs, int):
        return " ".join([name] * action.nargs)
    return name


class ClickParser(argparse.ArgumentParser):
    """The parser every command in this package is built from (#1230).

    Click's help -- `Usage:`, `Arguments:`, `Options:`, and a `Commands:`
    list for a parser with subcommands -- from the standard library, so
    nothing that must run on a bare interpreter gains a dependency.
    argparse builds a subcommand's parser with its parent's class, so a
    subcommand gets the same look without asking for it.

    `command_rows` replaces the list a subcommand group would give: a
    dispatcher forwards its command verbatim and has no group to read."""

    def __init__(
        self,
        *args,
        command_rows: list[tuple[str, str]] | None = None,
        command_hint: str | None = None,
        **kwargs,
    ) -> None:
        kwargs.setdefault("formatter_class", ClickFormatter)
        add_help = kwargs.pop("add_help", True)
        for key, value in parser_kwargs().items():
            kwargs.setdefault(key, value)
        super().__init__(*args, add_help=False, **kwargs)
        self.command_rows = command_rows
        self.command_hint = command_hint
        self._optionals.title = "Options"
        self._positionals.title = "Arguments"
        if add_help:
            self.add_argument("-h", "--help", action="help", help="Show this message and exit.")

    def add_subparsers(self, **kwargs) -> argparse._SubParsersAction:
        kwargs.setdefault("metavar", "COMMAND")
        kwargs.setdefault("help", argparse.SUPPRESS)
        return super().add_subparsers(**kwargs)

    def _rows(self) -> list[tuple[str, str]]:
        if self.command_rows is not None:
            return self.command_rows
        groups = [a for a in self._actions if isinstance(a, argparse._SubParsersAction)]
        return [(c.dest, c.help or "") for g in groups for c in g._choices_actions]

    def format_help(self) -> str:
        rows = self._rows()
        if not rows:
            return super().format_help()
        block = commands_block(rows, shutil.get_terminal_size().columns)
        hint = self.command_hint or f"Run '{self.prog} COMMAND --help' for a command's flags."
        return f"{super().format_help()}\nCommands:\n{block}\n\n  {hint}\n"


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
    parser = ClickParser(
        prog=prog,
        description=description,
        usage=USAGE,
        command_rows=rows,
        command_hint=hint,
    )
    parser.add_argument(
        dest,
        choices=choices if choices is not None else [name for name, _ in rows],
        nargs="?",
        metavar="COMMAND",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("rest", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    return parser
