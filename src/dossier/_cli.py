"""`python -m src.draft dossier`'s argparse tree: wiring every
subcommand to the `_cmd_*` handler that now lives beside the data it
handles, and nothing else.

Split out of src/dossier.py (#219), mirroring the one rule
`src/review/__main__.py` already follows for the same reason: "This
file only wires them together: it never restates a flag, so there is
no second place for one to drift out of sync." Every `_cmd_*` handler
moved to the submodule that owns the state it prints or writes; this
file only imports each by name and hands it to `set_defaults(func=...)`.

Deliberately named `_cli.py`, not `__main__.py`: this package has no
`__main__` block on purpose, the same way `src/dossier.py` had none
before this split. `python -m src.dossier` stays the same silent no-op
`docs/ARCHITECTURE.md` documents for the other four drafting-layer
modules -- `python -m src.draft dossier` is this layer's one front
door, and a package `__main__.py` would quietly open a second one.
"""

import argparse
import sys

from src.dossier._archive import _cmd_export, _cmd_restore
from src.dossier._brief import _cmd_brief
from src.dossier._acronyms import _cmd_acronyms_suggest
from src.dossier import DossierError, _cmd_list
from src.dossier._create import _cmd_init
from src.dossier._language import _cmd_set_language
from src.dossier._retrieval import _cmd_mark_revision
from src.dossier._sections import _cmd_sections
from src.dossier._status import _cmd_status

_DRAFT_PATH_HELP = "Path to the draft under content/drafts/"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.draft dossier",
        description="The working state behind a draft: create it, inspect it, "
                    "back it up, restore it. Stdlib only; never writes to the "
                    "corpus layer.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a dossier skeleton for a draft")
    p_init.add_argument("draft", help=_DRAFT_PATH_HELP)
    p_init.add_argument("--genre", required=True,
                        help="survey, thesis-chapter, textbook-chapter, tutorial, deep-research")
    p_init.set_defaults(func=_cmd_init)

    p_status = sub.add_parser("status", help="What a dossier holds, and corpus drift since")
    p_status.add_argument("draft", nargs="?",
                          help="Draft path, or the dossier directory itself")
    p_status.add_argument("--all", action="store_true",
                          help="One drift report over every dossier instead")
    p_status.add_argument("--json", action="store_true",
                          help="Machine-readable drift report (for draft-reviser)")
    p_status.set_defaults(func=_cmd_status)

    p_mark_revision = sub.add_parser(
        "mark-revision",
        help="Record a revision-session boundary, so retrieval cost totals per revision")
    p_mark_revision.add_argument("draft", help=_DRAFT_PATH_HELP)
    p_mark_revision.add_argument(
        "--label", default="",
        help="Short name for this revision (the date is already recorded)")
    p_mark_revision.set_defaults(func=_cmd_mark_revision)

    p_sections = sub.add_parser(
        "sections", help="Heading -> line range, for reading and editing one section")
    p_sections.add_argument("draft", help="Path to the draft")
    p_sections.add_argument(
        "--citekeys", action="store_true",
        help="Print the dossier's sections.md table -- heading -> the citekeys "
             "cited under it -- derived from the draft instead of by hand")
    p_sections.add_argument(
        "--write", action="store_true",
        help="With --citekeys: write the table to the dossier's sections.md")
    p_sections.set_defaults(func=_cmd_sections)

    p_brief = sub.add_parser(
        "brief", help="The kept evidence for one section, for a subagent to read")
    p_brief.add_argument("draft", help="Draft path, or the dossier directory itself")
    p_brief.add_argument("citekeys", nargs="*", help="Citekeys to print the blocks for")
    p_brief.add_argument("--section",
                         help="Take the citekeys from this sections.md row instead")
    p_brief.add_argument("--check", action="store_true",
                         help="Report what resolves without printing the blocks")
    p_brief.set_defaults(func=_cmd_brief)

    p_set_language = sub.add_parser(
        "set-language",
        help="Record the draft's dialect, so `src.draft style` can check it",
    )
    p_set_language.add_argument("draft", help=_DRAFT_PATH_HELP)
    p_set_language.add_argument("language", help="a BCP-47 tag: en-GB, en-US, en-IN")
    p_set_language.set_defaults(func=_cmd_set_language)

    p_suggest = sub.add_parser(
        "acronyms-suggest",
        help="Acronyms this draft's glossary defines that aren't in your vocabulary yet",
    )
    p_suggest.add_argument("draft", help=_DRAFT_PATH_HELP)
    p_suggest.add_argument(
        "--apply", action="store_true",
        help="write the suggestions to your [style].acronyms file (fails if "
             "that key is unset -- see docs/CONFIG.md)",
    )
    p_suggest.set_defaults(func=_cmd_acronyms_suggest)

    p_list = sub.add_parser("list", help="Every dossier on this machine")
    p_list.set_defaults(func=_cmd_list)

    p_export = sub.add_parser("export", help="Back up drafts and dossiers to a tar.gz")
    p_export.add_argument("names", nargs="*",
                          help="Draft names to include (default: everything)")
    p_export.add_argument("--out", help="Archive path (default: drafts-<name>-<date>.tar.gz)")
    p_export.add_argument("--with-rendered", action="store_true",
                          help="Include content/rendered/, and the .tex/.pdf renders "
                               "of content/review/'s reports (large: PDFs)")
    p_export.set_defaults(func=_cmd_export)

    p_restore = sub.add_parser("restore", help="Unpack a bundle (dry run unless --force)")
    p_restore.add_argument("archive", help="Path to a tar.gz written by `export`")
    p_restore.add_argument("--force", action="store_true",
                           help="Actually write, overwriting what is already there")
    p_restore.set_defaults(func=_cmd_restore)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except DossierError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
