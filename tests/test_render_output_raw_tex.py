"""#1144: a Markdown render drops the draft's raw LaTeX.

`--format md` on a Markdown draft never reaches pandoc, so nothing
dropped a ```` ```{=latex} ```` block or a `` `...`{=latex} `` span the
way pandoc's own non-LaTeX writers do: both reached the rendered `.md`
verbatim, where every Markdown viewer shows them as code.
"""

import shutil

from chitragupta import _markdown_inert, render_output
from chitragupta.render_output import _raw_tex
from tests.conftest import content_draft

# The issue's reproduction, plus a fenced ```{=latex} shown *inside* a
# longer ````markdown fence, which is an example and must survive.
_DRAFT = """# Demo

Some text with an inline span `\\hfill`{=latex} here.

```{=latex}
\\renewcommand{\\arraystretch}{1.35}
```

| A | B |
|---|---|
| 1 | 2 |

: A table.

~~~~ {=tex}
\\renewcommand{\\arraystretch}{1}
~~~~

```python
print("a code block that must survive")
```

````markdown
```{=latex}
\\small
```
````
"""

_EXPECTED = """# Demo

Some text with an inline span here.

| A | B |
|---|---|
| 1 | 2 |

: A table.

```python
print("a code block that must survive")
```

````markdown
```{=latex}
\\small
```
````
"""


def test_a_markdown_render_drops_raw_latex_and_keeps_code(isolated_config, monkeypatch):
    draft = content_draft(isolated_config, "demo/demo.md")
    draft.write_text(_DRAFT, encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda _: None)

    out_path = render_output.render(str(draft), output_format="md")

    assert out_path.read_text(encoding="utf-8") == _EXPECTED


class TestDropped:
    """`_raw_tex.dropped` on its own: what is cut, and what is left."""

    def test_a_block_at_either_end_leaves_no_stray_blank_line(self):
        text = "```{=latex}\n\\a\n```\n\nBody.\n\n```{=latex}\n\\b\n```\n"
        assert _raw_tex.dropped(text) == "Body.\n"

    def test_consecutive_blocks_collapse_to_one_gap(self):
        text = "A.\n\n```{=latex}\n\\a\n```\n\n```{=tex}\n\\b\n```\n\nB.\n"
        assert _raw_tex.dropped(text) == "A.\n\nB.\n"

    def test_a_block_without_a_trailing_newline(self):
        assert _raw_tex.dropped("A.\n\n```{=latex}\n\\a\n```") == "A.\n"

    def test_a_short_closer_does_not_end_a_long_fence(self):
        text = "A.\n\n````{=latex}\n```\n````\n\nB.\n"
        assert _raw_tex.dropped(text) == "A.\n\nB.\n"

    def test_an_unclosed_raw_fence_is_left_alone(self):
        # Pandoc reads it as a paragraph, not a raw block.
        text = "A.\n\n```{=latex}\n\\a\n"
        assert _raw_tex.dropped(text) == text

    def test_a_raw_block_in_a_blockquote_takes_its_prefixes_with_it(self):
        text = "> A.\n>\n> ```{=latex}\n> \\a\n> ```\n>\n> B.\n"
        assert _raw_tex.dropped(text) == "> A.\n>\n> B.\n"

    def test_a_raw_block_on_a_list_marker_line_is_left_alone(self):
        # Cutting the line would cut the item's marker with it.
        text = "- ```{=latex}\n  \\a\n  ```\n"
        assert _raw_tex.dropped(text) == text

    def test_an_inline_span_before_punctuation_leaves_no_space(self):
        assert _raw_tex.dropped("Wide `\\hfill`{=latex}, then.\n") == "Wide, then.\n"

    def test_an_inline_span_opening_a_line_takes_the_space_after_it(self):
        assert _raw_tex.dropped("`\\noindent`{=tex} Text.\n") == "Text.\n"

    def test_an_inline_span_between_words_glues_nothing(self):
        assert _raw_tex.dropped("a`\\,`{=latex}b\n") == "ab\n"

    def test_a_line_of_only_an_inline_span_goes_without_splitting_its_paragraph(self):
        assert _raw_tex.dropped("One\n`\\newline`{=latex}\ntwo.\n") == "One\ntwo.\n"

    def test_inline_code_and_other_raw_formats_are_kept(self):
        # `{=html}` is passed through: a Markdown viewer renders raw HTML.
        text = "Run `make` and `<br>`{=html} here.\n\n```{=html}\n<hr>\n```\n"
        assert _raw_tex.dropped(text) == text


def test_raw_tex_spans_skip_code_and_report_kind():
    text = "x `\\a`{=latex} y\n\n````md\n```{=latex}\n```\n````\n\n```{=tex}\n\\b\n```\n"
    spans = _markdown_inert.raw_tex_spans(text)
    assert [(text[start:end], block) for start, end, block in spans] == [
        ("`\\a`{=latex}", False),
        ("```{=tex}\n\\b\n```", True),
    ]
