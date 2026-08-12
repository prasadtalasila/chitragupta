"""No doc and no skill may hand a reader a two-level command.

docs/ARCHITECTURE.md states the invariant: **one entry point per layer,
one level deep**. Every layer is reached through a single
`python -m src.<layer>`; a package may nest as deep as its code wants,
its *command surface* may not.

tests/test_review_entrypoint.py and tests/test_draft_entrypoint.py pin
the code half -- no submodule of a layer carries a `__main__` block, so
a nested command cannot be made to work. This file pins the half those
two cannot see. A doc or a skill can *print* `python -m src.a.b` at a
reader whether or not it runs, and the reader will type it. Since no
submodule has a `__main__` block, what they get is exit 0 and empty
stdout -- a silent no-op. For `src.draft gate` that failure mode is
worse than an error: an automated caller gets an unconditional pass on a
draft nothing ever checked.

Anchored on `-m ` specifically, which is what separates an *invocation*
from an *API reference*. `src.retrieval.search()` and
`src.enrich.embed_index.search()` are dotted, legitimate, and appear
throughout the skills; they name Python callables, not commands, and
must never be flagged.

Three occurrences in the tree are deliberate and must stay legal: the
paragraphs in docs/ARCHITECTURE.md that name the nested form *in order
to warn against it*. Rather than allowlist them by path -- which would
go stale the moment either paragraph moved -- this reads the sentence
around each match and asks whether it is disarming the command. That
keeps the rule about what the prose says rather than about where it
lives.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every read below passes encoding="utf-8" explicitly. Without it
# read_text() uses the locale codec, which is cp1252 on the Windows CI
# leg, and these files are full of em dashes and curly quotes -- so the
# check would die with a UnicodeDecodeError there while passing on
# Linux. Same reason tests/test_review_entrypoint.py and
# tests/test_skill_verbatim_scan_offer.py pin it.

# A nested invocation: `src` plus *two or more* dotted segments. `-m`
# with any whitespace after it, because these files are hand-wrapped and
# the module can land on the next line.
#
# `{2,}` rather than a fixed two segments so the whole path is reported.
# A fixed pattern still *detects* `-m src.a.b.c` -- it matches the
# `src.a.b` prefix -- but it reports the offender truncated, which sends
# whoever reads the failure looking for a module path that isn't the one
# they wrote.
_NESTED = re.compile(r"-m\s+src(?:\.\w+){2,}")

# What makes a mention legal: prose saying, in the same breath, that the
# command does nothing. Deliberately narrow. Looser phrases that occur
# in these paragraphs -- "a trap", "does nothing", "exits 0" -- are
# common enough in ordinary technical prose to disarm a real violation
# by coincidence, so they are not accepted on their own.
_GUARDS = (
    "no `__main__` block",
    "imports a module",
    "imports the module",
)

# How far *back* from a match to look for a guard. Measured against
# every occurrence in the tree: the furthest a guard sits before its
# match is 72 characters. 120 is headroom without spanning a sentence.
#
# Backwards only, and that is the whole point. The construction this
# accepts always puts the guard first -- "X carries no `__main__` block,
# so `python -m X.y` does nothing" -- so looking forward buys nothing and
# costs the check its teeth: with a symmetric window, a warned-about
# mention licenses any *real* invocation that lands within the window
# after it, which is exactly how someone appending an example to that
# paragraph would slip one through. There is a test for it below.
_GUARD_WINDOW = 120


def _doc_files():
    """Everything a reader copies a command out of.

    Not only Markdown: `config.toml.example` is shipped as the file you
    copy to `config.toml` and is read as documentation, and
    `scripts/install_full_pipeline.sh` is the install path whose header
    comment lists commands. Both carry invocations, so both are in
    scope; restricting this to `*.md` would leave the two non-Markdown
    files anyone actually runs unchecked.

    Roots are enumerated rather than swept with a recursive glob from
    the repository root. `.gitignore` lists `content/drafts/`,
    `content/dossiers/` and `content/review/` as per-host data, so
    `REPO_ROOT.glob("**/*.md")` would pull in whatever drafts the
    developer happens to have locally -- making the result depend on the
    machine and invisible to CI, which has none of them.
    """
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
    """Whitespace collapsed, because these files are hand-wrapped.

    Without it the check becomes a check on where someone's editor broke
    the line: a guard split as ``no `__main__`\\n    block`` is the same
    sentence as the unwrapped form and must not read as a missing guard.

    The cost is line numbers, so each offender is reported with the
    surrounding sentence instead -- see `unguarded`. A character offset
    into collapsed text is not something anyone can act on from a CI log.
    """
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


# How much text around an offender to quote back. Enough to recognise
# the sentence and grep for it in the source file, short enough that a
# handful of offenders stay readable in CI output.
_SNIPPET_CHARS = 90


def unguarded(text):
    """Every nested invocation in `text` with no guard before it.

    Returns `(offset, command, snippet)` per offender. The snippet is
    what makes a CI failure actionable: offsets are into the *collapsed*
    text, so they match nothing you could search for in the file itself.

    Module-level and named without an underscore because the tests below
    exercise it directly on synthetic strings -- that is what makes this
    file falsifiable rather than merely green.
    """
    found = []
    for match in _NESTED.finditer(text):
        window = text[max(0, match.start() - _GUARD_WINDOW): match.start()]
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
        "Nested `python -m src.a.b` invocations with nothing saying they do "
        "nothing:" + "".join(report) + "\n\n"
        "The command surface is one level deep -- no submodule of a layer "
        "carries a `__main__` block, so what a reader who types this gets is "
        "exit 0 and empty stdout, and for the gate that is a silent pass on "
        "an unchecked draft. Use the layer's own entry point "
        "(`python -m src.corpus <verb>`, `python -m src.draft <verb>`, "
        "`python -m src.review <aid>`), or say in the same sentence that the "
        "nested form does nothing. See docs/ARCHITECTURE.md."
    )


def test_the_scan_reaches_the_documentation_tree():
    """Non-vacuity: a glob that silently matched nothing would make the
    assertion above pass for the wrong reason, forever."""
    files = _doc_files()
    assert len(files) > 20, f"only {len(files)} Markdown files found"
    names = {p.name for p in files}
    assert "ARCHITECTURE.md" in names
    assert "CLI.md" in names
    assert "README.md" in names


def test_the_invariant_is_still_stated_where_it_is_enforced_from():
    """The documentation half of the rule.

    A test that only forbids the nested form would leave the *reason*
    unpinned, and the reason is the thing a future reader needs in order
    to not re-litigate this. Anchored on the bolded heading rather than
    the prose around it, which gets edited.
    """
    text = _normalised(REPO_ROOT / "docs" / "ARCHITECTURE.md")
    assert "**One entry point per layer, one level deep.**" in text


def test_a_guarded_mention_is_what_keeps_the_architecture_doc_legal():
    """Non-vacuity for the guard logic specifically.

    The three legal mentions all live in docs/ARCHITECTURE.md. If they
    were reworded to drop their guards, the first test would fail and
    this one says why. If they were deleted outright, the first test
    would pass vacuously and only this one would notice.
    """
    text = _normalised(REPO_ROOT / "docs" / "ARCHITECTURE.md")
    assert _NESTED.search(text), (
        "docs/ARCHITECTURE.md no longer names the nested form at all. The "
        "invariant is worth stating with the trap it forbids -- a reader who "
        "has never seen `python -m src.enrich.docling_parse` cannot be warned "
        "off it."
    )
    assert not unguarded(text)


def test_an_unguarded_nested_invocation_is_flagged():
    assert unguarded("Run `python -m src.draft.dossier init` to begin.")


def test_a_nested_invocation_is_allowed_when_the_prose_disarms_it():
    assert not unguarded(
        "`src/draft/dossier.py` carries no `__main__` block, so "
        "`python -m src.draft.dossier` imports the module and exits 0."
    )


def test_a_guard_does_not_license_a_real_invocation_after_it():
    """The failure this check would otherwise have.

    A symmetric window makes any warned-about mention a shelter: append
    a genuine example to the paragraph that disarms the nested form, and
    it inherits that paragraph's guard. Since the guarded paragraphs are
    exactly where someone editing this topic is already typing, that is
    the likeliest way a real violation would ever land.
    """
    assert unguarded(
        "Submodules carry no `__main__` block, so "
        "`python -m src.enrich.docling_parse` imports the module and exits 0. "
        + "x" * 80
        + " For a one-off run, try `python -m src.draft.dossier init` instead."
    )


def test_two_mentions_sharing_one_guard_are_both_allowed():
    """The converse, and why the window is not zero: one sentence
    legitimately disarms two spellings at once, which is what
    docs/ARCHITECTURE.md actually does."""
    assert not unguarded(
        "The submodules inside `src/enrich/` and `src/review/` carry no "
        "`__main__` block, so `python -m src.enrich.docling_parse` or "
        "`python -m src.review.verbatim_check` imports a module and exits 0."
    )


def test_a_deeper_path_is_flagged_and_reported_in_full():
    """Three segments or more, not just two.

    A fixed two-segment pattern would still catch this -- it matches the
    `src.a.b` prefix -- but would report the command truncated, sending
    whoever reads the failure looking for a path they never wrote.
    """
    found = unguarded("Run `python -m src.layer.sub1.sub2 init` to begin.")
    assert found
    assert found[0][1] == "-m src.layer.sub1.sub2"


def test_an_offender_is_reported_with_enough_context_to_find_it():
    """Offsets are into the collapsed text and match nothing greppable,
    so the snippet is the part that makes a CI failure actionable."""
    (_, _, snippet), = unguarded(
        "The dossier is the working state behind a draft. "
        "Run `python -m src.draft.dossier init` to create one."
    )
    assert "working state behind a draft" in snippet
    assert "to create one" in snippet


def test_a_dotted_python_api_reference_is_not_flagged():
    """The carve-out the whole regex is shaped around: these name
    callables, not commands, and appear all over the skills."""
    assert not unguarded(
        "Search the corpus with `src.retrieval.search()`, or "
        "`src.enrich.embed_index.search()` when content/chroma/ exists."
    )


def test_a_one_level_command_is_not_flagged():
    assert not unguarded(
        "Run `python -m src.draft gate content/drafts/survey.md`, then "
        "`python -m src.review verbatim scan <draft>` and `python -m src.sync`."
    )
