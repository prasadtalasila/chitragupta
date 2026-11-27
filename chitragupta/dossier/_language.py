"""`dossier set-language`: recording a draft's dialect tag so
`chitragupta.draft style` can check prose against it.
"""

import re
import sys
from pathlib import Path

from chitragupta import config
from chitragupta.dossier import SCOPE_MD, dossier_dir

# A BCP-47 tag's shape, not the checker's list: a true declaration must
# be recordable before any style rule exists for it.
_LANGUAGE_TAG = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


_LANGUAGE_LINE = re.compile(r"^- language:.*$", re.MULTILINE)


def set_language(draft: Path, tag: str) -> Path:
    """Record `tag` as the draft's dialect in its dossier `scope.md`.

    Replaces the line (including `init`'s placeholder), else inserts it
    after `- genre:`; older dossiers lack it, so the insert is common.
    """
    if not _LANGUAGE_TAG.match(tag):
        raise ValueError(
            f"{tag!r} is not a BCP-47 language tag. Expected a form like en-GB, en-US or en-IN."
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
        text = (
            text.replace("- genre:", f"{line}\n- genre:", 1)
            if "- genre:" in text
            else text.replace("# Scope\n", f"# Scope\n\n{line}\n", 1)
        )
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
