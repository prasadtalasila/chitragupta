"""The user-facing half of this pipeline's acronym vocabulary: proposing
new entries from a draft's glossary and its own prose, and -- on
request -- writing them.
"""

import tomllib
from pathlib import Path

from chitragupta import acronyms, config
from chitragupta.dossier._glossary import glossary_terms


def suggest_acronyms(draft: Path) -> dict[str, str]:
    """Acronyms that look like a candidate and aren't in the vocabulary
    yet -- from two sources, merged.

    The glossary wins on a shared acronym; the draft's prose is the
    fallback, since terms expanded inline but never glossaried are the
    lapse this exists to catch (three of seven in the 15-chapter book).
    Never writes: #190's rule is that this proposes and a human accepts
    with an explicit `--apply`, never inside an unattended pass.
    """
    body = draft.read_text(encoding="utf-8") if draft.is_file() else ""
    merged = {**acronyms.body_candidates(body), **glossary_terms(draft)}
    return acronyms.suggest(merged)


class NoUserAcronymsFile(RuntimeError):
    """`[style].acronyms` is unset, so the target would be the vendored,
    git-tracked `assets/style/acronyms.toml`, committing one user's
    vocabulary for every clone (#190). Raised instead of writing."""


def _toml_escape(value: str) -> str:
    """`value` as a TOML basic-string body -- the two characters a basic
    string cannot contain unescaped."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def apply_suggestions(draft: Path) -> dict[str, str]:
    """Write `suggest_acronyms(draft)`'s candidates into
    `config.ACRONYMS_PATH`, creating it if needed; return what was
    written (`{}` if nothing new).

    Recomputes the candidates, so re-running is idempotent. Raises
    `NoUserAcronymsFile` if `[style].acronyms` is unset. No TOML writer:
    entries are flat pairs, hand-formatted and validated with `tomllib`
    before touching disk.
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
    # Validate before touching disk: nothing here could undo a bad write.
    tomllib.loads(existing + "".join(lines))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.writelines(lines)
    return candidates


_CASE_REMINDER = (
    "\n  Case is authoritative: write a common noun in lower case (WRITING-STANDARDS.md §9)."
)


def _cmd_acronyms_suggest(args) -> int:
    """Always 0, deliberately: only a person at a terminal reads this
    (docs/CONFIG.md), and stdout says it all. SonarCloud S3516 flags it;
    branches are tested by their output (TestSuggestAcronyms).
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
        print(
            f"  Wrote {len(written)} new entr{'y' if len(written) == 1 else 'ies'} "
            f"to {config.ACRONYMS_PATH}:\n"
        )
        for term, definition in sorted(written.items()):
            print(f'  {term} = "{definition}"')
        print(_CASE_REMINDER)
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
    print(_CASE_REMINDER)
    return 0
