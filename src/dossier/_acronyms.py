"""The user-facing half of this pipeline's acronym vocabulary: proposing
new entries from a draft's glossary and its own prose, and -- on
request -- writing them.

Split from src/dossier/_citekeys.py, which still owns glossary parsing
itself (`glossary_terms()`): this half grew past
docs/CODE-STANDARDS.md's C2 module-line limit once `--apply` and its
guard rail were added. The boundary follows the shape
src/style_report.py already uses for the same reason -- what a command
*does* is a separate concern from what it *reads*.
"""

import tomllib
from pathlib import Path

from src import acronyms, config
from src.dossier._citekeys import glossary_terms


def suggest_acronyms(draft: Path) -> dict[str, str]:
    """Acronyms that look like a candidate and aren't in the vocabulary
    yet -- from two sources, merged.

    The glossary is the deliberate record, written by the drafting skill
    on purpose, and wins on a shared acronym. The draft's own raw prose
    (`acronyms.body_candidates()`) is the fallback: a term coined and
    expanded inline but never added to the glossary is exactly the kind
    of lapse this command exists to catch, and measured against this
    project's own real 15-chapter book, three of the seven parenthetical
    acronyms it actually defines (DTP, DTI, DTA) are glossaried nowhere
    at all -- glossary-only discovery would never have surfaced them.

    Never writes anything. `python -m src.draft dossier acronyms-suggest`
    without `--apply` only prints these: #190's own rule is that this
    feature proposes and the human accepts. `--apply` (`apply_suggestions`
    below) is the explicit, second, human-invoked step that writes --
    still never automatic, still never inside an unattended pass. The
    matching itself is `acronyms.suggest()` -- this just merges the two
    sources and hands the result to it.
    """
    body = draft.read_text(encoding="utf-8") if draft.is_file() else ""
    merged = {**acronyms.body_candidates(body), **glossary_terms(draft)}
    return acronyms.suggest(merged)


class NoUserAcronymsFile(RuntimeError):
    """`[style].acronyms` is unset, so `config.ACRONYMS_PATH` is exactly
    `config.ACRONYMS_DEFAULT_PATH` -- the vendored, git-tracked
    `assets/style/acronyms.toml`. Writing there would commit one user's
    domain vocabulary into the file every clone shares, the outcome
    issue #190 built the override to avoid. Raised instead of writing;
    the CLI catches it and tells the user how to set one up."""


def _toml_escape(value: str) -> str:
    """`value` as a TOML basic-string body -- the two characters a basic
    string cannot contain unescaped."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def apply_suggestions(draft: Path) -> dict[str, str]:
    """Write `suggest_acronyms(draft)`'s candidates into
    `config.ACRONYMS_PATH`, creating the file (and its parent directory)
    if it doesn't exist yet, and return what was written -- `{}` if there
    was nothing new.

    Recomputes the candidates rather than trusting a cached dict, so a
    run an hour after the vocabulary last changed is still compared
    against it as it stands now. Every candidate `suggest()` returns is
    already confirmed absent from both the vendored floor and this file,
    so appending is always safe and re-running is idempotent -- a second
    `--apply` with nothing new to add writes nothing.

    Raises `NoUserAcronymsFile` if `[style].acronyms` is unset -- see
    that class. No TOML-writing dependency: entries here are always flat
    `KEY = "Value"` pairs (the shape `assets/style/acronyms.toml.example`
    documents), so this hand-formats each line -- and validates the
    combined text through `tomllib` *before* it touches disk, so a
    malformed write is refused rather than left corrupting the file with
    nothing here to undo it.
    """
    if config.ACRONYMS_PATH == config.ACRONYMS_DEFAULT_PATH:
        raise NoUserAcronymsFile(
            "[style].acronyms is not set, so there is no user file to "
            "write to -- only the vendored assets/style/acronyms.toml. "
            "Copy assets/style/acronyms.toml.example to "
            "content/acronyms.toml, point [style].acronyms at it in "
            "config.toml, and re-run with --apply."
        )
    candidates = suggest_acronyms(draft)
    if not candidates:
        return {}
    path = config.ACRONYMS_PATH
    is_new = not path.is_file()
    lines = []
    if is_new:
        lines.append(
            "# Your own acronym vocabulary -- merged over the vendored "
            "floor in assets/style/acronyms.toml. See "
            "assets/style/README.md.\n"
        )
    for acronym, expansion in sorted(candidates.items()):
        lines.append(f'{acronym} = "{_toml_escape(expansion)}"\n')
    existing = "" if is_new else path.read_text(encoding="utf-8")
    # Validate the combined text *before* touching disk -- a write that
    # turned out malformed would otherwise already be sitting in the file
    # by the time the round-trip check could catch it, with nothing here
    # to undo it.
    tomllib.loads(existing + "".join(lines))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.writelines(lines)
    return candidates


def _cmd_acronyms_suggest(args) -> int:
    """Always 0, deliberately -- unlike _cmd_brief's exit code, nothing
    downstream reads this one: `acronyms-suggest` has no caller but a
    person at a terminal (docs/CONFIG.md), and what they need is already
    in stdout. Flagged by SonarCloud (S3516, "always returns the same
    value"); every branch is tested separately by its printed output
    (tests/test_dossier.py::TestSuggestAcronyms), not by this return.
    """
    draft = Path(args.draft)
    if getattr(args, "apply", False):
        try:
            written = apply_suggestions(draft)
        except NoUserAcronymsFile as exc:
            print(f"  {exc}")
            return 0
        if not written:
            print("  No new acronyms to suggest.")
            return 0
        print(f"  Wrote {len(written)} new entr{'y' if len(written) == 1 else 'ies'} "
              f"to {config.ACRONYMS_PATH}:\n")
        for term, definition in sorted(written.items()):
            print(f'  {term} = "{definition}"')
        return 0
    candidates = suggest_acronyms(draft)
    if not candidates:
        print("  No new acronyms to suggest.")
        return 0
    print(
        "  New acronyms in this draft's glossary or its own prose, not "
        "yet in your vocabulary. Nothing is written -- re-run with "
        "--apply to add them to your own [style].acronyms file:\n"
    )
    for term, definition in sorted(candidates.items()):
        print(f'  {term} = "{definition}"')
    return 0
