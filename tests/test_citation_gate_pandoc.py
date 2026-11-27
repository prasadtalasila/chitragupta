import functools
import json
import random
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from chitragupta import _braced_keys, citation_gate, references

ROOT = Path(__file__).resolve().parent.parent
PANDOC = shutil.which("pandoc")
needs_pandoc = pytest.mark.skipif(PANDOC is None, reason="pandoc not installed")


@functools.cache
def _pandoc_version() -> tuple[int, ...]:
    if PANDOC is None:
        return ()
    first = subprocess.run(
        [PANDOC, "--version"], capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout.split()[1]
    return tuple(int(part) for part in first.split("."))


RECORDED = (3, 6)


def assert_agrees_with_pandoc(gate: set[str], text: str) -> None:
    resolved = pandoc_citation_ids(text)
    if _pandoc_version() >= RECORDED:
        assert gate == resolved, text
    else:
        assert resolved <= gate, text


def pandoc_citation_ids(text: str) -> set[str]:
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


FRAGMENTS = [
    (
        "Shown by @{brace.one} and [@{brace_two}] and [@bare_one].",
        {"brace.one", "bare_one", "brace_two"},
    ),
    ("[@{multi_a}; @{multi_b}] and -@{suppressed.c}.", {"suppressed.c", "multi_a", "multi_b"}),
    ("@{nest{ed}key} @{} @{has space} @{}tail", {"", "nest{ed}key"}),
    ("```\n@fence_in\n```\n@fence_after", {"fence_after"}),
    ("~~~ {.python}\n@tilde_in\n~~~\n@tilde_after", {"tilde_after"}),
    ("````\n```\n@long_in\n````\n@long_after", {"long_after"}),
    ("```\n@info_in\n```python\n@info_in2\n```\n@info_after", {"info_after"}),
    ("```python\n@unclosed_fence\n", {"unclosed_fence"}),
    ("Before\n```\n@interrupt_in\n```\n@interrupt_after", {"interrupt_after"}),
    ("Before\n~~~\n@tilde_lazy\n~~~\n@tilde_lazy2", {"tilde_lazy2", "tilde_lazy"}),
    ("``` bash -c ``` runs @span_after", {"span_after"}),
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
    (
        "---\ntitle: x\nnocite: |\n    @yaml_nocite\n---\n\n@yaml_after",
        {"yaml_nocite", "yaml_after"},
    ),
    (
        "Body[^n].\n\n[^n]: Note @footnote_first.\n\n    @footnote_para\n",
        {"footnote_para", "footnote_first"},
    ),
    (
        "pre-@k_hyphen, [pre-@k_bracket], x_@k_under, x%@k_pct and x+@k_plus",
        {"k_hyphen", "k_bracket", "k_under", "k_pct", "k_plus"},
    ),
    (
        'x*@k_star x~@k_tilde x/@k_slash x:@k_colon x#@k_hash )@k_paren "@k_quote x!@k_bang',
        {"k_star", "k_tilde", "k_slash", "k_colon", "k_hash", "k_paren", "k_quote", "k_bang"},
    ),
    ("x.@k_dot é@k_accent x²@k_super see@k_letter me@k_email.org", set()),
    (
        "\\@k_esc1 \\\\@k_esc2 \\\\\\@k_esc3 \\-@k_esc4 \\\\-@k_esc5",
        {"k_esc2", "k_esc4", "k_esc5"},
    ),
    ("\\.@k_escdot a\\.@k_escdot2 \\\\.@k_escdot3", {"k_escdot", "k_escdot2"}),
    (
        "x...@el_1 x....@el_2 x......@el_3 ..\\.@el_4 \\...@el_5 ...@el_6",
        {"el_1", "el_3", "el_4", "el_6"},
    ),
    ("[@url_a:/b] @url_c//d @url_e:/ @url_f/:g", {"url_a:/b", "url_c//d", "url_e:", "url_f"}),
    (
        "@日本_2021 and [@müller_2020] and [@p36ü] and @Ⅻ_roman",
        {"日本_2021", "müller_2020", "p36ü", "Ⅻ_roman"},
    ),
    ("@comb́ined and @²_digit", {"comb", "²_digit"}),
    ("@* and [@*k_wild]", {"*", "*k_wild"}),
    (
        "(@ex_a) An example.\n\nSee (@ex_a), @ex_a, -@ex_a and @{ex_a}, but [@ex_a]"
        " and [see @ex_a, p. 3] and @ex_a:more.",
        {"ex_a", "ex_a:more"},
    ),
    ("See (@ex_undef).", {"ex_undef"}),
    ("Text\n(@ex_lazy) is no list.\n\n@ex_lazy", {"ex_lazy"}),
    ("@ex_c) d\n\n@ex_d. d\n\n@ex_c @ex_d", set()),
    ("- a\n(@ex_e) lazy item\n\n@ex_e", set()),
    ("```\n(@ex_f) code\n```\n\n@ex_f", {"ex_f"}),
    ("<!--\n(@ex_g) c\n-->\n\n@ex_g", {"ex_g"}),
    ("- a\n  <!--\n  (@ex_h) c\n  -->\n\n@ex_h", {"ex_h"}),
    ("# (@ex_i) heading\n\n@ex_i", {"ex_i"}),
    ("(@é_ex) d\n\n@é_ex", set()),
    ("(@ex_j) d\n\n(@ex_jj) d\n\n[see \\] @ex_j] and [a [b] @ex_jj]", {"ex_j", "ex_jj"}),
    ("(@ex_k) d\n\nOne [para\n\n@ex_k] two", set()),
    ("Term\n\n:   (@ex_l) d\n\n> (@ex_m) d\n\n@ex_l @ex_m", set()),
    ("(@ul_a) x\n---\n\n@ul_a", {"ul_a"}),
    ("(@ul_b) x\n===\n\n@ul_b", {"ul_b"}),
    ("@ul_c. x\n-\n\n@ul_c", {"ul_c"}),
    ("- (@ul_d) x\n  ---\n\n@ul_d", {"ul_d"}),
    ("(@ul_e) x | y\n--- | ---\n1 | 2\n\n@ul_e", {"ul_e"}),
    ("(@br_a) item\n\n[see\n`code`\n@br_a]", {"br_a"}),
    ("(@br_b) item\n\n[see\n<!-- c -->\n@br_b]", {"br_b"}),
    ("(@br_c) item\n\n> [see\n> `code`\n> @br_c]", {"br_c"}),
]


@pytest.mark.parametrize("fragment, resolved", FRAGMENTS)
def test_each_fragment_extracts_what_pandoc_resolves(fragment, resolved):
    assert gate_ids(fragment) == resolved


@needs_pandoc
@pytest.mark.parametrize("fragment, resolved", FRAGMENTS)
def test_pandoc_still_resolves_what_each_fragment_records(fragment, resolved):
    assert pandoc_citation_ids(fragment) == resolved


@pytest.mark.parametrize(
    "fragment",
    [
        fragment
        for fragment, _ in FRAGMENTS
        if "\\begin" not in fragment and "\\end" not in fragment
    ],
)
def test_renumbering_leaves_no_citation_the_gate_extracts(fragment):
    numbers = {key: n for n, key in enumerate(references.used_citekeys(fragment), start=1)}
    assert gate_ids(references.renumber(fragment, numbers)) == set()


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
    assert_agrees_with_pandoc(gate_ids(text), text)


_BEFORE = list("-_%+*~/:#)\"'!&=?.,;|^{}(\\") + ["\\\\", "\\\\\\", "x", "é", "²", "·", "…", " "]
_KEY = list("aZ09_-:.#%&+?~/*'é日üÅⅫ²ʼ·→́ ") + ["--", "aa", "b1"]


def _at_tokens(rng: random.Random) -> str:
    tokens = []
    for _ in range(rng.randint(3, 8)):
        before = "".join(rng.choice(_BEFORE) for _ in range(rng.randint(0, 2)))
        key = "".join(rng.choice(_KEY) for _ in range(rng.randint(1, 5)))
        tokens.append(f"{before}@{key}")
    return "Text " + " ".join(tokens) + "\n"


@needs_pandoc
@pytest.mark.parametrize("seed", range(80))
def test_random_characters_around_an_at_extract_what_pandoc_resolves(seed):
    text = _at_tokens(random.Random(1021_000 + seed))
    assert_agrees_with_pandoc({key.split("--")[0] for key in gate_ids(text)}, text)


class TestDeliberateDisagreements:
    @needs_pandoc
    def test_a_latex_cite_in_markdown_is_still_gated(self):
        text = "Claimed \\citep{raw_cite} and \\nocite{raw_nocite}."
        assert pandoc_citation_ids(text) == set()
        assert gate_ids(text) == {"raw_cite", "raw_nocite"}

    @needs_pandoc
    def test_a_doubled_hyphen_keeps_the_whole_key(self):
        assert pandoc_citation_ids("[@twin--as-a-service]") == {"twin"}
        assert gate_ids("[@twin--as-a-service]") == {"twin--as-a-service"}

    TEX_COMMANDS = (
        "\\x@k_tex1 \\é@k_tex2 \\xa12@k_tex3 a\\x@k_tex4 \\\\x@k_tex5 \\1@k_tex6 \\x2b@k_tex7"
    )
    TEX_COMMAND_KEYS = {"k_tex1", "k_tex2", "k_tex3", "k_tex4"}

    def test_a_tex_command_before_an_at_opens_a_citation(self):
        assert gate_ids(self.TEX_COMMANDS) == self.TEX_COMMAND_KEYS

    @needs_pandoc
    def test_no_pandoc_cites_after_a_tex_command_what_the_gate_does_not(self):
        assert "k_tex3" in pandoc_citation_ids(self.TEX_COMMANDS)
        assert pandoc_citation_ids(self.TEX_COMMANDS) <= self.TEX_COMMAND_KEYS

    @needs_pandoc
    def test_a_tex_command_taking_an_argument_still_opens_a_citation(self):
        text = "\\b@tex_arg and \\emph@tex_arg2"
        assert pandoc_citation_ids(text) == set()
        assert gate_ids(text) == {"tex_arg", "tex_arg2"}

    @needs_pandoc
    def test_an_abandoned_emphasis_opener_still_opens_a_citation(self):
        text = "*@star_a *@star_b"
        assert pandoc_citation_ids(text) == {"star_a"}
        assert gate_ids(text) == {"star_a", "star_b"}

    @needs_pandoc
    def test_math_is_not_blanked(self):
        text = "$@math_token$ and @after_math"
        assert pandoc_citation_ids(text) == {"after_math"}
        assert gate_ids(text) == {"math_token", "after_math"}


class TestRawTexInMarkdown:
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
        text = "@{" * 50_000
        keys = citation_gate.extract_citekeys(text)
        assert keys and all(len(key) <= _braced_keys.BRACED_KEY_LIMIT for _, key in keys)

    def test_a_braced_key_in_code_is_not_a_citation(self):
        assert citation_gate.extract_citekeys("`@{in_code}` and\n\n    @{indented}\n") == []


class TestPathologicalInputsStayLinear:
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
