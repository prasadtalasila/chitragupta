"""The package's single front door: `chitragupta <layer> <verb> ...`.

Four layers, each already a complete entry point of its own:

    chitragupta corpus <verb> ...   the deterministic corpus run
    chitragupta draft  <verb> ...   work on one draft
    chitragupta review <aid>  ...   read-only aids, never a gate
    chitragupta enrich        ...   the optional enrichment layer

**This adds a front door, not a command surface.** Every verb, flag and
exit code below belongs to the layer it dispatches to, unchanged. Like
`chitragupta/draft.py`, this file parses exactly one thing -- the layer
name -- and forwards everything after it verbatim, because restating a
layer's flags here would be a second place for them to drift out of sync
with what the layer actually does.

**The module form keeps working, and that is a decision rather than an
accident.** `python -m chitragupta.<layer> <verb>` is what
`.claude/hooks/` and the genre skills invoke. A console script lives in
one venv's `bin/`; the module form resolves from any interpreter that can
import the package. docs/CLI.md records why tier 1 exists at all -- the
gate chain must not be blockable by a broken venv -- and
`chitragupta/hook_launchers.py` records the measurement behind it: a hook
launcher that does not resolve produces *nothing at all*, no error and no
log line. Routing the citation gate through a PATH lookup that can
silently miss would be the worst change available in this series. So the
console script is for humans, the module form is for machines, and both
are supported on purpose.

On the command-depth invariant (#144): it is unchanged, only restated.
The rule forbids reaching *into* a layer's package from the command line
-- `python -m chitragupta.a.b` -- and `chitragupta review verbatim scan`
does no such thing. It is one layer, one aid, and one aid-subcommand
owned by that aid's own parser, exactly as `python -m chitragupta.review
verbatim scan` already was. docs/ARCHITECTURE.md states the invariant in
its restated form; docs/PACKAGING.md carries the command surface.
"""

import argparse
import importlib
import sys

from chitragupta.progname import prog_for

# Imported lazily, by name, for the reason `chitragupta/corpus.py` gives
# for the same trick: asking for `draft gate` -- the one command that must
# run on a bare interpreter with no venv -- should never pay for
# `enrich`'s imports, several of which are absent unless the optional
# group is installed.
LAYERS = {
    "corpus": ("chitragupta.corpus",
               "bring the ledger up to date, or read what it recorded"),
    "draft": ("chitragupta.draft",
              "work on one draft -- gate it, cite it, render it"),
    "review": ("chitragupta.review.__main__",
               "three read-only aids over a finished draft; never a gate"),
    "enrich": ("chitragupta.enrich.__main__",
               "Docling -> embeddings/Chroma -> BERTopic, over the whole corpus"),
}

DESCRIPTION = ("Turn a curated bibliography into grounded drafts, "
               "with every citekey verified against a real parse.")


def _version() -> str:
    """The installed distribution's version.

    `importlib.metadata`, not `pyproject.toml`: an installed package has
    no `pyproject.toml` beside it, so reading the file would report
    "unknown" for every user who did not clone the repository. Falls back
    rather than raising, because `--version` failing is a worse answer
    than an imprecise one.
    """
    try:
        from importlib.metadata import PackageNotFoundError, version
        return version("chitragupta-cli")
    except (ImportError, PackageNotFoundError):  # pragma: no cover - see tests
        return "unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog_for(""), description=DESCRIPTION)
    parser.add_argument("--version", action="version", version=_version())
    parser.add_argument(
        "layer", choices=sorted(LAYERS), nargs="?",
        help=" / ".join(f"{name} -- {help_text}"
                        for name, (_, help_text) in LAYERS.items()),
    )
    # REMAINDER, so a layer can take its own `-h`/`--help` and this parser
    # never sees it -- the same contract chitragupta/draft.py uses for its
    # verbs.
    parser.add_argument("rest", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    return parser


def main(argv=None) -> int:
    """No layer at all prints the usage and exits 0.

    That is a "tell me how to use this" request, not an error -- the same
    rule every layer in this package already applies to a missing verb.
    """
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.layer is None:
        parser.print_help()
        return 0
    module = importlib.import_module(LAYERS[args.layer][0])
    # `enrich` reads sys.argv itself rather than taking an argv argument,
    # so it is handed a rewritten one instead of being special-cased into
    # a different calling convention. Restored afterwards because a test
    # calling main() twice must not inherit the first call's arguments.
    if args.layer == "enrich":
        saved, sys.argv = sys.argv, [prog_for("enrich"), *args.rest]
        try:
            return module.main()
        finally:
            sys.argv = saved
    return module.main(args.rest)


if __name__ == "__main__":
    raise SystemExit(main())
