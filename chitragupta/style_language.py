"""Which dialect a draft's prose is checked against (§8 of
docs/WRITING-STANDARDS.md), for `chitragupta.style_check` (#1022).
"""

from pathlib import Path

from chitragupta import config, dossier
from chitragupta.style_rules import _ALL_DIALECT_RULES, DIALECT_RULES


def language_of(draft: Path) -> str | None:
    """The BCP-47 tag in this draft's dossier `scope.md`, or None.

    None covers no dossier, no `language:` line, and `init`'s "not
    settled" placeholder: each means nobody chose a dialect, so the
    dialect rules are skipped and the report says so.
    """
    try:
        scope = dossier.dossier_dir(draft) / dossier.SCOPE_MD
    except dossier.DossierError:
        return None  # a draft outside content/ has no dossier path to compute
    if not scope.is_file():
        return None
    for line in scope.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("- language:"):
            continue
        value = stripped.split(":", 1)[1].strip()
        # The shipped placeholder contains real tags, so it is matched by
        # prefix: "not" itself passes for a BCP-47 primary subtag.
        if value.lower().startswith("not settled"):
            return None
        tag = value.split()[0] if value else ""
        # Returned even with no rules for it: "recorded, nothing to check
        # it with" differs from "nobody chose one".
        return tag or None
    return None


def resolve_language(draft: Path, override: str | None = None) -> tuple[str | None, str]:
    """The dialect to check `draft` against, and where it came from.

    Flag, then the draft's recorded property, then the host default. The
    source travels with the tag so a host-wide default never looks like a
    dialect the draft declared.
    """
    if override:
        return override, "--language"
    recorded = language_of(draft)
    if recorded:
        return recorded, "scope.md"
    if config.STYLE_LANGUAGE:
        return config.STYLE_LANGUAGE, "config.toml"
    return None, "nothing"


def rule_filter(language: str | None) -> str:
    """A Vale `--filter` expression keeping every rule except the dialect
    rules that do not apply to `language`.

    Written as exclusions so a rule added to assets/vale/ later is on by
    default; an inclusion list would silently disable a forgotten one.
    """
    wanted = DIALECT_RULES.get(language or "", ())
    if isinstance(wanted, str):
        wanted = (wanted,)
    excluded = [rule for rule in _ALL_DIALECT_RULES if rule not in wanted]
    return " and ".join(f'.Name != "{rule}"' for rule in excluded)
