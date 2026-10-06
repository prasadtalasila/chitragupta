"""Which dialect a draft's prose is checked against (§8 of
docs/WRITING-STANDARDS.md), for `chitragupta.style_check`.

Split out of style_check.py (#1022), which sat over the 250-code-line
limit on the debt register: deciding the dialect reads the dossier and
config and never runs Vale, so it is a seam with nothing on the other
side of it but a tag and where it came from.
"""

from pathlib import Path

from chitragupta import config, dossier
from chitragupta.style_rules import _ALL_DIALECT_RULES, DIALECT_RULES


def language_of(draft: Path) -> str | None:
    """The BCP-47 tag in this draft's dossier `scope.md`, or None.

    None covers three different situations that all want the same
    treatment -- no dossier, no `language:` line (every dossier written
    before 5.12.0), and the "not settled" placeholder `init` ships. Each
    means *nobody has chosen a dialect*, and the honest response to that
    is to skip the dialect rules and say so.
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
        # "not settled -- a BCP-47 tag (`en-GB`, ...)" is the shipped
        # placeholder, and it *contains* real tags, so the whole value
        # cannot be trusted. Matched by prefix rather than by tag shape,
        # because "not" is itself three lowercase letters and passes for a
        # BCP-47 primary subtag.
        if value.lower().startswith("not settled"):
            return None
        tag = value.split()[0] if value else ""
        # Returned even when this style has no rules for it. "Recorded
        # fr-FR, nothing to check it with" and "nobody chose one" are
        # different states, and only the second is worth prompting about.
        return tag or None
    return None


def resolve_language(draft: Path, override: str | None = None) -> tuple[str | None, str]:
    """The dialect to check `draft` against, and where it came from.

    Three sources, most specific first, because that is the order in which
    someone's intent gets more specific: a flag typed for this run, the
    draft's own recorded property, then a standing preference for this
    machine. The source travels with the tag so the report can name it --
    a draft checked against a host-wide default must not look like a draft
    that declared one.
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

    Expressed as exclusions rather than inclusions so that a rule added to
    assets/vale/ later is enabled by default: forgetting to list a new
    rule here would otherwise silently disable it, which is the failure
    mode that is invisible in a report of zero findings.
    """
    wanted = DIALECT_RULES.get(language or "", ())
    if isinstance(wanted, str):
        wanted = (wanted,)
    excluded = [rule for rule in _ALL_DIALECT_RULES if rule not in wanted]
    return " and ".join(f'.Name != "{rule}"' for rule in excluded)
