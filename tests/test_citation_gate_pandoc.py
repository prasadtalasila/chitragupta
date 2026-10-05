"""#944's class: the gate's extractor must agree with pandoc on every input.

The gate exists to refuse a citekey pandoc would resolve, so the set it
extracts has to be the set pandoc resolves: `[@{fabricated_2026}]` passed
as 0 citations, a fence line inside an HTML comment hid every later
citation (#945), and a decorator under a numbered step read as an
unknown citekey (#946). Patching each construct as it was reported was
the pattern this replaces, so the test is differential rather than a
list of pins: every fragment below, and random compositions of them
inside lists and blockquotes, is run through `pandoc -f markdown -t json`
and the two sets compared. It skips where pandoc is absent.

Each fragment carries the ids pandoc resolved in it, so the corpus
also runs where pandoc is absent. The composition is a seeded
`random.Random` rather than a hypothesis strategy, because hypothesis
is not a dependency here; a fixed seed keeps a failure reproducible
from the test id alone.

Three disagreements are deliberate, and pinned as such at the end: a
LaTeX `\\cite` in Markdown (pandoc passes it through raw, and a LaTeX
render would resolve it), a doubled hyphen in a key (see `PANDOC_KEY`),
and `$math$` (a gap that can only over-report).
"""

import json
import random
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from chitragupta import _braced_keys, citation_gate

ROOT = Path(__file__).resolve().parent.parent
PANDOC = shutil.which("pandoc")
needs_pandoc = pytest.mark.skipif(PANDOC is None, reason="pandoc not installed")


def pandoc_citation_ids(text: str) -> set[str]:
    """Every citation id pandoc's markdown reader finds in `text`."""
    result = subprocess.run(
        [PANDOC, "-f", "markdown", "-t", "json"],
        input=text,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            if node.get("t") == "Cite":
                found.update(citation["citationId"] for citation in node["c"][0])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(result.stdout))
    return found


def gate_ids(text: str) -> set[str]:
    return {key for _, key in citation_gate.extract_citekeys(text)}


# Each fragment uses its own keys, so a composition still says which one
# disagreed, beside the ids pandoc 3.6 resolves in it. The recorded set
# is what runs where pandoc is absent (CI's Windows leg), and where it is
# present pandoc is checked against the record too, so a pandoc that
# changes its reading fails here rather than drifting silently. Grouped
# by the construct they exercise.
FRAGMENTS = [
    # Braced keys (#944).
    (
        "Shown by @{brace.one} and [@{brace_two}] and [@bare_one].",
        {"brace.one", "bare_one", "brace_two"},
    ),
    ("[@{multi_a}; @{multi_b}] and -@{suppressed.c}.", {"suppressed.c", "multi_a", "multi_b"}),
    ("@{nest{ed}key} @{} @{has space} @{}tail", {"", "nest{ed}key"}),
    # Fences: closers, unclosed, info strings, paragraph interruption.
    ("```\n@fence_in\n```\n@fence_after", {"fence_after"}),
    ("~~~ {.python}\n@tilde_in\n~~~\n@tilde_after", {"tilde_after"}),
    ("````\n```\n@long_in\n````\n@long_after", {"long_after"}),
    ("```\n@info_in\n```python\n@info_in2\n```\n@info_after", {"info_after"}),
    ("```python\n@unclosed_fence\n", {"unclosed_fence"}),
    ("Before\n```\n@interrupt_in\n```\n@interrupt_after", {"interrupt_after"}),
    ("Before\n~~~\n@tilde_lazy\n~~~\n@tilde_lazy2", {"tilde_lazy2", "tilde_lazy"}),
    ("``` bash -c ``` runs @span_after", {"span_after"}),
    # HTML comments (#945).
    (
        "<!--\nTODO e.g.\n```\n-->\n\nSee [@comment_after] and @comment_after2.",
        {"comment_after2", "comment_after"},
    ),
    ("text <!-- [@comment_hidden] --> after [@comment_visible]", {"comment_visible"}),
    ("Text <!--\n```\n--> more @comment_lazy", {"comment_lazy"}),
    ("<!-- unclosed\n@comment_unclosed", {"comment_unclosed"}),
    ("a <!-- spans\n\nb @comment_blank --> c @comment_tail", {"comment_tail"}),
    (
        "<!-->@after_empty_comment --> and <!--->@after_empty2 -->",
        {"after_empty_comment", "after_empty2"},
    ),
    # Indented code and containers (#946).
    ("    @indented_top", set()),
    ("para\n    @lazy_continuation", {"lazy_continuation"}),
    ("1. Install it:\n\n    ```python\n    @list_fence\n    ```\n", set()),
    ("> ```\n> @quote_fence\n> ```\n\n@quote_after", {"quote_after"}),
    ("- item\n\n      @list_code\n", set()),
    ("1. a\n2. b\n\n    @list_para", {"list_para"}),
    ("1. a\n\n   para\n\n       @list_deep_code", set()),
    ("- a\n  - b\n\n    ```\n    @nested_fence\n    ```\n", set()),
    ("> - a\n>\n>       @quote_list_code", set()),
    ("- a\n\n    > q\n    >\n    >     @list_quote_code", set()),
    ("* a\n\n\t@tab_in_item", {"tab_in_item"}),
    ("Term\n:   def\n\n    @definition_para", {"definition_para"}),
    ("(@) example\n\n    @example_para", {"example_para"}),
    ("@) example\n\n    @example_para2", {"example_para2"}),
    ("text\n- not a list\n\n    @after_fake_list", set()),
    ("-     wide\n\n      @wide_marker_code", set()),
    ("-   ---\n\n    @rule_then_code\n\n* * *\n\n    @rule_then_code2", set()),
    (
        "-----------\n First    row [@table_a]\n\n    Second  row [@table_b]\n"
        "-----------\n\n    @after_table",
        {"table_a", "table_b"},
    ),
    ("---\n\n```\n@between_rules\n```\n\n---\n", set()),
    # Inline code, links, reference definitions, raw HTML.
    ("a `` b ` @span_double `` d @span_double_after", {"span_double_after"}),
    ("a `x\n@span_multiline` b", set()),
    (
        "[t](http://x.org/@link_target) and [@link_text](http://x) and [u](and @link_spaced here)",
        {"link_text"},
    ),
    ("<http://x.org/@autolink> and @autolink_after", {"autolink_after"}),
    (
        '[label]: http://x/@refdef "title @refdef_title"\n\n[t][label] @refdef_after',
        {"refdef_after"},
    ),
    ("[@refdef_citation]: http://x", {"refdef_citation"}),
    (
        "[@bracket_cite](@bracket_target) and [^n](@after_footnote_ref)",
        {"bracket_cite", "after_footnote_ref"},
    ),
    ("<pre>\n@in_pre\n</pre>\n\n@pre_after", {"pre_after"}),
    ("<pre\n@open_tag_unclosed\n</pre>", {"open_tag_unclosed"}),
    ("<div>\n[@in_div]\n</div>", {"in_div"}),
    # Edges of the block rules: a rule that is not metadata, lazy lines,
    # an escaped backtick run, stray TeX ends, two comments, two tables.
    ("# Heading\n---\ntitle: x\n---\n\n    @yaml_not_after_heading", set()),
    ("---\n\n    @rule_then_blank_code", set()),
    ("---\ntitle: x\n\n@yaml_unclosed", {"yaml_unclosed"}),
    (
        "> quoted\n> more [@quote_cont]\nlazy [@quote_lazy]\n\n    @after_quote_code",
        {"quote_cont", "quote_lazy"},
    ),
    (
        "- item\n  continued [@item_cont]\nlazy [@item_lazy]\n\n    @after_item_para",
        {"item_cont", "item_lazy", "after_item_para"},
    ),
    ("\\```a`` @after_escaped_run", {"after_escaped_run"}),
    (
        "\\end{y} @stray_end and \\begin{a}\\begin{b}\\end{a} @after_mismatch",
        {"stray_end", "after_mismatch"},
    ),
    (
        "<!-- one --> @between_comments <!-- two --> @after_comments",
        {"between_comments", "after_comments"},
    ),
    ("[t](a\\)b) @after_escaped_paren", {"after_escaped_paren"}),
    (
        "-----\n row [@first_table]\n-----\n\nx\n\n-----\n row [@second_table]\n-----\n",
        {"first_table", "second_table"},
    ),
    (
        "\\begin{a}x\\end{a} @between_envs \\begin{b}y\\end{b} @after_envs",
        {"between_envs", "after_envs"},
    ),
    ("word) b [t](http://x/@stray_target) @after_stray_paren", {"after_stray_paren"}),
    # Metadata and footnotes, which pandoc reads as Markdown.
    (
        "---\ntitle: x\nnocite: |\n    @yaml_nocite\n---\n\n@yaml_after",
        {"yaml_nocite", "yaml_after"},
    ),
    (
        "Body[^n].\n\n[^n]: Note @footnote_first.\n\n    @footnote_para\n",
        {"footnote_para", "footnote_first"},
    ),
]


@pytest.mark.parametrize("fragment, resolved", FRAGMENTS)
def test_each_fragment_extracts_what_pandoc_resolves(fragment, resolved):
    assert gate_ids(fragment) == resolved


@needs_pandoc
@pytest.mark.parametrize("fragment, resolved", FRAGMENTS)
def test_pandoc_still_resolves_what_each_fragment_records(fragment, resolved):
    assert pandoc_citation_ids(fragment) == resolved


def _in_list(text: str, rng: random.Random) -> str:
    marker = rng.choice(["- ", "* ", "1. ", "10. ", "a) ", "-   "])
    pad = " " * len(marker)
    lines = text.split("\n")
    return "\n".join([marker + lines[0]] + [pad + line if line else line for line in lines[1:]])


def _in_quote(text: str, _rng: random.Random) -> str:
    return "\n".join("> " + line if line else ">" for line in text.split("\n"))


def _compose(rng: random.Random) -> str:
    parts = []
    for _ in range(rng.randint(2, 5)):
        part = rng.choice(FRAGMENTS)[0]
        for _ in range(rng.randint(0, 2)):
            part = rng.choice([_in_list, _in_quote])(part, rng)
        parts.append(part)
    return "\n\n".join(parts) + "\n"


@needs_pandoc
@pytest.mark.parametrize("seed", range(60))
def test_random_compositions_extract_what_pandoc_resolves(seed):
    text = _compose(random.Random(944_000 + seed))
    assert gate_ids(text) == pandoc_citation_ids(text), text


class TestDeliberateDisagreements:
    """Where the gate reports more than pandoc resolves, on purpose.

    Each is the safe direction: a citation the gate reports and pandoc
    would not resolve can only fail a sound draft, never pass a
    fabricated one."""

    @needs_pandoc
    def test_a_latex_cite_in_markdown_is_still_gated(self):
        # Pandoc keeps it raw, and a LaTeX render hands it to LaTeX.
        text = "Claimed \\citep{raw_cite} and \\nocite{raw_nocite}."
        assert pandoc_citation_ids(text) == set()
        assert gate_ids(text) == {"raw_cite", "raw_nocite"}

    @needs_pandoc
    def test_a_doubled_hyphen_keeps_the_whole_key(self):
        # `PANDOC_KEY` explains why: `_citeproc` aliases the run away.
        assert pandoc_citation_ids("[@twin--as-a-service]") == {"twin"}
        assert gate_ids("[@twin--as-a-service]") == {"twin--as-a-service"}

    @needs_pandoc
    def test_math_is_not_blanked(self):
        text = "$@math_token$ and @after_math"
        assert pandoc_citation_ids(text) == {"after_math"}
        assert gate_ids(text) == {"math_token", "after_math"}


class TestRawTexInMarkdown:
    """Pandoc passes a `\\begin{env}...\\end{env}` block to LaTeX whole,
    so a citation command inside it is live in a LaTeX render even though
    pandoc's own JSON shows no Cite. Reading its indented lines as code
    would hide that from the gate."""

    def test_an_indented_cite_inside_an_environment_is_gated(self):
        text = "\\begin{figure}\n\n    \\caption{From \\citet{env_key}}\n\n\\end{figure}\n"
        assert gate_ids(text) == {"env_key"}

    def test_nested_environments_close_at_their_own_end(self):
        text = (
            "\\begin{itemize}\n\\item a\n\\begin{itemize}\n\\item b\n\\end{itemize}\n"
            "\n    \\citep{outer_key}\n\\end{itemize}\n\n    @code_after\n"
        )
        assert gate_ids(text) == {"outer_key"}

    def test_an_environment_opened_mid_paragraph_still_counts(self):
        assert gate_ids("a \\begin{x}\n\n    \\citep{mid_key}\n\n\\end{x}\n") == {"mid_key"}

    def test_a_raw_latex_fence_or_span_is_gated(self):
        text = "```{=latex}\n\\citep{fence_key}\n```\n\nand `\\citet{span_key}`{=latex}\n"
        assert gate_ids(text) == {"fence_key", "span_key"}

    def test_an_environment_inside_one_paragraph_is_gated(self):
        text = "a \\begin{x} \\citep{env_inline} \\end{x} b @after_env"
        assert gate_ids(text) == {"env_inline", "after_env"}

    def test_an_unmatched_begin_is_prose(self):
        assert gate_ids("\\begin{x}\n\n    @code_key\n") == set()


class TestBracedKeys:
    def test_each_braced_form_is_extracted_with_its_line(self):
        text = "Shown by @{fake.key}\nand [@{other}; -@{a{b}c}].\n"
        assert citation_gate.extract_citekeys(text) == [
            (1, "fake.key"),
            (2, "other"),
            (2, "a{b}c"),
        ]

    def test_a_braced_key_not_in_the_ledger_fails_the_gate(self):
        result = citation_gate.check_text(Path("d.md"), "[@{fabricated_2026}]", {"real"})
        assert not result.ok
        assert result.unknown == [(1, "fabricated_2026")]

    def test_an_unbalanced_or_spaced_brace_is_not_a_citation(self):
        assert citation_gate.extract_citekeys("@{open and @{a b} and @{x") == []

    def test_an_overlong_braced_run_fails_closed_and_fast(self):
        # No ledger holds a key this long, so reporting the prefix fails
        # the draft; and a run of `@{` with no space must stay linear.
        text = "@{" * 50_000
        keys = citation_gate.extract_citekeys(text)
        assert keys and all(len(key) <= _braced_keys.BRACED_KEY_LIMIT for _, key in keys)

    def test_a_braced_key_in_code_is_not_a_citation(self):
        assert citation_gate.extract_citekeys("`@{in_code}` and\n\n    @{indented}\n") == []


class TestPathologicalInputsStayLinear:
    """The gate hook is killed at 30 s, and a killed hook blocks nothing
    (#824). Each of these is one shape that a quadratic scan of this
    module's would hang on."""

    @pytest.mark.parametrize(
        "text",
        [
            "```\n" * 20_000,
            "````\n```\n" * 10_000,
            "<!--\n" * 20_000,
            "`" * 20_000 + "\n" + "``x" * 10_000,
            ">" * 5_000 + " @deep\n",
            "- " * 5_000 + "@deep\n",
            "<pre>\n" * 20_000,
            "[a](" * 20_000,
            "a\n" + "- b\n  " * 10_000,
        ],
        ids=[
            "unclosed-fences",
            "short-closers",
            "unclosed-comments",
            "backtick-runs",
            "deep-quotes",
            "deep-lists",
            "unclosed-pre",
            "unclosed-links",
            "long-list",
        ],
    )
    def test_completes(self, text):
        citation_gate.extract_citekeys(text)


# #957's class: a caller restating the `.tex` rule instead of asking
# `citation_gate.is_latex`. The restated one was missing from
# `registry.claims`, and a `.tex` unit's citation dropped out.
SUFFIX_RULE = re.compile(r"""suffix(?:\.lower\(\))?\s*==\s*["']\.tex["']""")


def test_no_caller_derives_the_latex_flag_from_a_suffix_itself():
    gate = ROOT / "chitragupta" / "citation_gate.py"
    offenders = [
        f"{path.relative_to(ROOT)}:{n}"
        for top in ("chitragupta", "scripts", ".claude/hooks")
        for path in sorted((ROOT / top).rglob("*.py"))
        if path != gate
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if SUFFIX_RULE.search(line)
    ]
    assert offenders == []
