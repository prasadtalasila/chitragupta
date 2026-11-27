import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


_NESTED = re.compile(r"-m\s+chitragupta(?:\.\w+){2,}")

_GUARDS = (
    "no `__main__` block",
    "imports a module",
    "imports the module",
)

_GUARD_WINDOW = 120


def _doc_files():
    return sorted(
        set(
            list((REPO_ROOT / "docs").glob("**/*.md"))
            + list(REPO_ROOT.glob("*.md"))
            + list((REPO_ROOT / ".claude").glob("**/*.md"))
            + list((REPO_ROOT / "scripts").glob("*.sh"))
            + [REPO_ROOT / "config.toml.example"]
        )
    )


def _normalised(path):
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


_SNIPPET_CHARS = 90


def unguarded(text):
    found = []
    for match in _NESTED.finditer(text):
        window = text[max(0, match.start() - _GUARD_WINDOW) : match.start()]
        if any(guard in window for guard in _GUARDS):
            continue
        start = max(0, match.start() - _SNIPPET_CHARS)
        end = min(len(text), match.end() + _SNIPPET_CHARS)
        snippet = ("..." if start else "") + text[start:end] + ("..." if end < len(text) else "")
        found.append((match.start(), match.group(0).strip(), snippet))
    return found


def test_no_doc_or_skill_hands_a_reader_a_two_level_command():
    report = []
    for path in _doc_files():
        for offset, command, snippet in unguarded(_normalised(path)):
            report.append(
                f"\n  {path.relative_to(REPO_ROOT)} (offset {offset})"
                f"\n    command: {command}"
                f"\n    context: {snippet}"
            )

    assert not report, (
        "Nested `python -m chitragupta.a.b` invocations with nothing saying they do "
        "nothing:" + "".join(report) + "\n\n"
        "The command surface is one level deep -- no submodule of a layer "
        "carries a `__main__` block, so what a reader who types this gets is "
        "exit 0 and empty stdout, and for the gate that is a silent pass on "
        "an unchecked draft. Use the layer's own entry point "
        "(`python -m chitragupta.corpus <verb>`, `python -m chitragupta.draft <verb>`, "
        "`python -m chitragupta.review <aid>`), or say in the same sentence that the "
        "nested form does nothing. See docs/ARCHITECTURE.md."
    )


def test_the_scan_reaches_the_documentation_tree():
    files = _doc_files()
    assert len(files) > 20, f"only {len(files)} Markdown files found"
    names = {p.name for p in files}
    assert "ARCHITECTURE.md" in names
    assert "CLI.md" in names
    assert "README.md" in names


def test_the_invariant_is_still_stated_where_it_is_enforced_from():
    text = _normalised(REPO_ROOT / "docs" / "ARCHITECTURE.md")
    assert "**One entry point per layer, one level deep.**" in text


def test_a_guarded_mention_is_what_keeps_the_architecture_doc_legal():
    text = _normalised(REPO_ROOT / "docs" / "ARCHITECTURE.md")
    assert _NESTED.search(text), (
        "docs/ARCHITECTURE.md no longer names the nested form at all. The "
        "invariant is worth stating with the trap it forbids -- a reader who "
        "has never seen `python -m chitragupta.enrich.docling_parse` cannot be warned "
        "off it."
    )
    assert not unguarded(text)


def test_an_unguarded_nested_invocation_is_flagged():
    assert unguarded("Run `python -m chitragupta.draft.dossier init` to begin.")


def test_a_nested_invocation_is_allowed_when_the_prose_disarms_it():
    assert not unguarded(
        "`chitragupta/draft/dossier.py` carries no `__main__` block, so "
        "`python -m chitragupta.draft.dossier` imports the module and exits 0."
    )


def test_a_guard_does_not_license_a_real_invocation_after_it():
    assert unguarded(
        "Submodules carry no `__main__` block, so "
        "`python -m chitragupta.enrich.docling_parse` imports the module and exits 0. "
        + "x" * 80
        + " For a one-off run, try `python -m chitragupta.draft.dossier init` instead."
    )


def test_two_mentions_sharing_one_guard_are_both_allowed():
    assert not unguarded(
        "The submodules inside `chitragupta/enrich/` and `chitragupta/review/` carry no "
        "`__main__` block, so `python -m chitragupta.enrich.docling_parse` or "
        "`python -m chitragupta.review.verbatim_check` imports a module and exits 0."
    )


def test_a_deeper_path_is_flagged_and_reported_in_full():
    found = unguarded("Run `python -m chitragupta.layer.sub1.sub2 init` to begin.")
    assert found
    assert found[0][1] == "-m chitragupta.layer.sub1.sub2"


def test_an_offender_is_reported_with_enough_context_to_find_it():
    ((_, _, snippet),) = unguarded(
        "The dossier is the working state behind a draft. "
        "Run `python -m chitragupta.draft.dossier init` to create one."
    )
    assert "working state behind a draft" in snippet
    assert "to create one" in snippet


def test_a_dotted_python_api_reference_is_not_flagged():
    assert not unguarded(
        "Search the corpus with `chitragupta.retrieval.search()`, or "
        "`chitragupta.enrich.embed_index.search()` when content/chroma/ exists."
    )


def test_a_one_level_command_is_not_flagged():
    assert not unguarded(
        "Run `python -m chitragupta.draft gate content/drafts/survey.md`, then "
        "`python -m chitragupta.review verbatim scan <draft>` and `python -m chitragupta.enrich`."
    )
