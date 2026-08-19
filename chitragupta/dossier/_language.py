"""`dossier set-language`: recording a draft's dialect tag so
`chitragupta.draft style` can check prose against it.

Split out of chitragupta/dossier.py (#219). The smallest submodule in the
package -- kept separate from `_cli` anyway, rather than folded in,
because every other command already gets its own module and a single
exception would just be a different inconsistency to explain later.
"""

import re
import sys
from pathlib import Path

from chitragupta import config
from chitragupta.dossier import SCOPE_MD, dossier_dir

# A BCP-47 tag's shape, not a list of the ones this repo can check. The
# dossier records what a human declared; `chitragupta.draft style` decides
# separately which declarations it has rules for, and says so when it has
# none. Validating against the checker's list here would stop someone
# recording a true fact about their draft merely because no rule exists
# for it yet.
_LANGUAGE_TAG = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


_LANGUAGE_LINE = re.compile(r"^- language:.*$", re.MULTILINE)


def set_language(draft: Path, tag: str) -> Path:
    """Record `tag` as the draft's dialect in its dossier `scope.md`.

    Replaces the line if one is there -- including the "not settled"
    placeholder `init` ships -- and inserts it after `- genre:` if not,
    which is where the template puts it and where a reader looks. Every
    dossier written before 5.12.0 lacks the line entirely, so the insert
    path is the common one rather than the edge.
    """
    if not _LANGUAGE_TAG.match(tag):
        raise ValueError(
            f"{tag!r} is not a BCP-47 language tag. Expected a form like "
            "en-GB, en-US or en-IN."
        )
    scope = dossier_dir(draft) / SCOPE_MD
    if not scope.is_file():
        raise FileNotFoundError(
            f"No scope.md for {draft}. Run `python -m chitragupta.draft dossier init "
            f"{draft} --genre <genre>` first."
        )
    text = scope.read_text(encoding="utf-8")
    line = f"- language: {tag}"
    if _LANGUAGE_LINE.search(text):
        text = _LANGUAGE_LINE.sub(line, text, count=1)
    else:
        text = text.replace("- genre:", f"{line}\n- genre:", 1) \
            if "- genre:" in text else text.replace("# Scope\n", f"# Scope\n\n{line}\n", 1)
    scope.write_text(text, encoding="utf-8")
    return scope


def _cmd_set_language(args) -> int:
    try:
        scope = set_language(Path(args.draft), args.language)
    except (ValueError, FileNotFoundError, config.OutsideContentDir) as exc:
        print(f"  {exc}", file=sys.stderr)
        return 1
    print(f"  language: {args.language}  ->  {scope}")
    return 0
