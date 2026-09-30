# #823: stop TeX reading outside the draft, and figure siblings following symlinks

Status: **closed by PR #906 (6.126.7).** Written 2026-09-30 against
`origin/main` at `3e54222`. Closes #823. Two things were added on the
way, both from the final branch review: `render()` now refuses a draft
whose `\input` or image reference is a symlink out of its directory
(`_refuse_escaping_refs`), because pandoc and pdflatex follow such a
link themselves and `openin_any=p` cannot see it. A `pdf` render also
reports a `TMPDIR` with a dot-directory up front
(`_require_tex_readable_tmpdir`), because paranoid mode refuses pandoc's
own temp copy of the draft there.

> **For agentic workers:** REQUIRED SUB-SKILL: use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task by task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a collaborator-controlled `.bib` field or a symlinked figure
can no longer make a render or a review aid read a file outside the
draft, and no `pdflatex` this codebase starts runs with shell escape.

**Architecture:** two environment/argv settings on the two places that
start `pdflatex` (pandoc's `pdf` path and the figure-layout probe), plus
one resolved-path check in `_resolve_sibling`. The image copier gets the
same check by routing through `_resolve_sibling`.

**Tech stack:** Python 3, pytest, pandoc 3.x, TeX Live `pdflatex`
(kpathsea).

**Spec:** issue #823. This plan departs from it in one place, described
under "The departure from the issue" below. Read that section before
starting.

**Written for** whoever implements #823. **Assumed:** the
`DEVELOPER-AGENTS.md` shipping cycle (TDD, 100% line and branch coverage,
ruff, markdownlint, OCR review, PATCH bump). **Not covered here:** the
`tex` output format and the `--fragment` (natbib) path. See "Out of
scope".

## The departure from the issue: `openin_any=p`, not `--sandbox`

The issue proposes pandoc's `--sandbox` and asks for one real render to
be checked before it lands. I checked it on this host (pandoc 3.6.4, TeX
Live, `openin_any = a` and `shell_escape = p` by default). The fixture
was a draft citing one entry whose title is
`See \input{<abs>/secret.txt} here`, plus a 1×1 PNG:

| Format | no flag: leaks? | `--sandbox`: leaks? | `--sandbox`: side effect |
| --- | --- | --- | --- |
| html | no | no | none |
| docx | no | no | **the PNG is dropped** (`[WARNING] Could not fetch resource img.png`, exit 0) |
| tex | writes a raw `\input{<abs>/secret.txt}` into the output | same | none |
| pdf | **yes**, the secret is in the PDF text | **yes, still** | none |

So `--sandbox` fails on both counts:

1. **It does not close the hole.** pandoc 3.6.4's BibTeX reader does not
   expand `\input`. It passes the command through as raw LaTeX, and
   `pdflatex` reads the file at compile time. `--sandbox` only confines
   pandoc's own reads, so it cannot see this.
2. **It regresses docx.** The docx writer embeds images, and under
   `--sandbox` it may only read files named on the command line, not
   ones found through `--resource-path`. The image goes missing and the
   render still exits 0. That is the "wrong-but-successful render" the
   comment above `--resource-path` in `_pandoc.py` warns about.

What does close it is kpathsea's `openin_any`, set to `p` (paranoid) in
`pdflatex`'s environment. kpathsea lets an environment variable override
the same-named `texmf.cnf` setting, which is how `max_print_line` is set
in `_probe.py`. Measured on the same fixture:

- secret-bearing bib, `openin_any=p`: pdflatex refuses (`pdflatex: Not
  reading from <abs>/secret.txt (openin_any = p).`), pandoc exits 43 and
  no PDF is written. The render fails closed.
- clean bib, `openin_any=p`, with `TEXINPUTS=<draft dir>:` and a
  `\input{figures/f.tex}`: exit 0, the figure body and the image are both
  in the PDF. Paranoid mode checks the name as TeX spells it, not the
  path TEXINPUTS finds, so the draft's own figures still load.
- `--pdf-engine-opt=-no-shell-escape` on top: no change to a normal
  render.

A person on the other end sees a render that used to succeed with
someone else's file inside it now fail, with that file's path in the
error. That is the behaviour we want.

**The implementer does not decide this.** If the user wants `--sandbox`
anyway, as defence in depth against a future pandoc that does expand
`\input`, it can only go on the non-docx formats, and that is the user's
call. Ask; do not add it silently.

## Global constraints

- The citekey rule in `CLAUDE.md` applies to test fixtures too: reuse
  the `smith_2024` entry pattern `tests/test_render_output.py` already
  uses. Never invent a new key.
- Line and branch coverage stays at 100% (`fail_under = 100`).
- Every line that needs a real `pdflatex` keeps its
  `# pragma: no cover-windows`, as its neighbours do.
- Match the local comment density: every existing flag in
  `_pandoc_command` has a comment saying why. The new ones need one too.
- PATCH version bump (a security fix with no new surface).

## Review focus

Inputs no task below is primarily about, and what a person would expect
from each. The owning task pins each one with a test.

1. **A symlink that stays inside the draft directory**, such as
   `figures/current.tex -> figures/v3.tex`, must keep working. Only
   escaping links are refused (Task 3).
2. **A draft directory that is itself a symlink**, such as
   `content/drafts/dt -> /elsewhere/dt`, must keep resolving its own
   figures. `resolves_inside` resolves both sides, so this holds. Pin it
   (Task 3).
3. **An image symlinked out of the draft.** `_copy_local_images` has its
   own spelling-only check (`_assets.py:66`) and the same hole as
   `_resolve_sibling`. The issue does not mention it. Route it through
   `_resolve_sibling` (Task 3).
4. **A clean draft with citations, a PNG and a TikZ figure renders to
   exactly the same PDF text as before** under `openin_any=p` and
   `-no-shell-escape`. The existing real-`pdflatex` tests cover part of
   this. Task 1 adds a before/after `pdftotext` comparison to cover the
   rest.
5. **EPS images.** graphicx converts `.eps` through `repstopdf`, which is
   on restricted shell escape's allow-list. `-no-shell-escape` stops it.
   This host has no `repstopdf`, so an EPS render already fails here
   (exit 43). On a host that has it, EPS worked before this change and
   no longer will: pandoc exits 0 and the image is silently missing.
   Document it in `docs/SECURITY.md` and suggest PDF or PNG instead (Task
   4). Do not add an exception.

---

### Task 1: harden pandoc's `pdf` path

**Files:**

- Modify: `chitragupta/render_output/_pandoc.py:237-252`, the
  `if output_format == "pdf":` block in `_pandoc_command`.
- Test: `tests/test_render_output_cli.py` (new class
  `TestPdflatexHardening`, next to `TestLongtableCaptionWidth`).
- Test: `tests/test_render_output.py` (new method on `TestRenderReal`).

**Interfaces:** `_pandoc_command`'s signature and return type do not
change. It still returns `(cmd, env)`, and `env` is still `None` for
every format except `pdf`.

- [ ] **Step 1: write the failing argv/env tests**

Add to `tests/test_render_output_cli.py`:

```python
class TestPdflatexHardening:
    """#823. A `.bib` title such as `See \\input{~/.netrc}` passes
    through pandoc's BibTeX reader as raw LaTeX, and `pdflatex` reads it
    at compile time, since kpathsea's default `openin_any = a` allows any
    readable file. `openin_any=p` limits reads to the working directory
    and TEXINPUTS, and `-no-shell-escape` also turns off the restricted
    `\\write18` allow-list."""

    def _cmd(self, output_format):
        return render_output._pandoc_command(
            Path("in.md"),
            Path("bib.bib"),
            Path("ieee.csl"),
            Path(f"out.{output_format}"),
            Path("in.md"),
            output_format,
            "article",
            "12pt",
            "a4",
            "1in",
            [],
            False,
            False,
        )

    def test_a_pdf_render_turns_shell_escape_off(self):
        cmd, _ = self._cmd("pdf")
        assert "--pdf-engine-opt=-no-shell-escape" in cmd

    def test_a_pdf_render_runs_pdflatex_paranoid_about_reads(self):
        _, env = self._cmd("pdf")
        assert env["openin_any"] == "p"

    def test_the_hosts_own_openin_any_does_not_win(self, monkeypatch):
        monkeypatch.setenv("openin_any", "a")
        _, env = self._cmd("pdf")
        assert env["openin_any"] == "p"

    @pytest.mark.parametrize("output_format", ["html", "docx", "tex"])
    def test_a_format_that_runs_no_pdflatex_is_untouched(self, output_format):
        cmd, env = self._cmd(output_format)
        assert env is None
        assert not any(flag.startswith("--pdf-engine-opt") for flag in cmd)

    def test_pandoc_itself_is_not_sandboxed(self):
        # Measured on pandoc 3.6.4: `--sandbox` silently drops a docx
        # render's images and does not stop the pdf-path leak. See
        # plans/823-tex-read-hardening.md.
        for output_format in ("pdf", "docx"):
            cmd, _ = self._cmd(output_format)
            assert "--sandbox" not in cmd
```

- [ ] **Step 2: run them and confirm they fail**

Run: `pytest tests/test_render_output_cli.py::TestPdflatexHardening -v`
Expected: `test_a_pdf_render_turns_shell_escape_off` and both
`openin_any` tests FAIL. The other two already pass, because they pin
current behaviour.

- [ ] **Step 3: write the failing real-render test**

Add to `TestRenderReal` in `tests/test_render_output.py`. It already
skips without pandoc and pdflatex, and the file already imports
`subprocess`.

```python
    def test_a_bib_field_cannot_make_pdflatex_read_outside_the_draft(
        self, isolated_config, tmp_path
    ):
        # #823: a shared (e.g. Zotero group) .bib is collaborator text.
        secret = tmp_path / "outside" / "secret.txt"
        secret.parent.mkdir()
        secret.write_text("NOT-FOR-THE-PDF\n")
        con = ledger.connect()
        ledger.upsert_reference(
            con, make_reference(citekey="smith_2024", title="An Example Paper", year="2024")
        )
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024,\n"
            f"  title={{See \\input{{{secret}}} here}},\n"
            "  year={2024},\n}\n"
        )
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# Title\n\nSome claim [@smith_2024].\n")

        with pytest.raises(subprocess.CalledProcessError) as raised:
            render_output.render(str(draft), output_format="pdf")

        assert "openin_any" in raised.value.stderr
        assert not (isolated_config.RENDERED_DIR / "draft.pdf").exists()
```

Run: `pytest tests/test_render_output.py -k bib_field_cannot -v`
Expected: FAIL with `DID NOT RAISE`, because today the render succeeds
and the secret ends up in the PDF. If it fails some other way (for
example the aliased bib dropping the title), stop and fix the fixture
before going on.

- [ ] **Step 4: implement**

In `_pandoc_command`, extend the `pdf` block:

```python
    if output_format == "pdf":  # pragma: no cover-windows
        cmd += ["--pdf-engine", "pdflatex"]
        # No `\write18` at all, not even TeX Live's default restricted
        # allow-list (`shell_escape = p`). Nothing a draft legitimately
        # needs calls out to a shell, and the allow-list is still code
        # execution chosen by the document (#823). The one casualty is
        # graphicx's `.eps` -> `repstopdf` conversion; docs/SECURITY.md
        # says to use PDF or PNG figures instead.
        cmd += ["--pdf-engine-opt=-no-shell-escape"]
        # (existing TEXINPUTS comment, unchanged)
        env = {
            **os.environ,
            "TEXINPUTS": f"{input_path.resolve().parent}:",
            # kpathsea's paranoid read mode: no absolute paths, no `..`,
            # no dotfiles, only the working directory and TEXINPUTS
            # (#823). Without it, a `.bib` title of
            # `\input{/home/alice/.netrc}` reaches pdflatex as raw LaTeX
            # through citeproc and the file is typeset into the reference
            # list. pandoc's own `--sandbox` does not help: it confines
            # pandoc's reads, not pdflatex's, and it drops a docx
            # render's images (measured on pandoc 3.6.4; see
            # plans/823-tex-read-hardening.md). Paranoid mode checks the
            # name as TeX spells it, so the draft's `figures/x.tex`,
            # found through TEXINPUTS above, still loads. Set after
            # `os.environ` so a host's own `openin_any` cannot loosen it.
            "openin_any": "p",
        }
```

Keep the existing TEXINPUTS comment where it is. Only the dict literal
gains a key.

- [ ] **Step 5: run the tests again**

Run:

```bash
pytest tests/test_render_output_cli.py::TestPdflatexHardening \
  tests/test_render_output.py -v
```

Expected: all PASS, including every existing `TestRenderReal` and TikZ
pdf test, which now run under `openin_any=p`.

- [ ] **Step 6: check the whole PDF against the old one (Review focus 4)**

The issue asks for a render of
`content/drafts/digital-twins-for-software-engineers/`. That draft has
no images or figures, and this container has no ledger or `.bib`, so it
cannot run here. Use a fixture that covers more instead: one citation,
one PNG, one `figures/` file read through TEXINPUTS. Run pandoc exactly
as `_pandoc_command` does, once without the new settings and once with
them:

```bash
S=<session scratchpad>/823 && rm -rf "$S" && mkdir -p "$S/figures" && cd "$S"
python3 -c "import struct,zlib;c=lambda t,d:struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d));open('img.png','wb').write(b'\x89PNG\r\n\x1a\n'+c(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+c(b'IDAT',zlib.compress(b'\x00\xff\x00\x00'))+c(b'IEND',b''))"
echo 'FIGURE-BODY' > figures/f.tex
printf '@article{smith_2024, title={An Example Paper}, year={2024}}\n' > x.bib
printf '# T\n\nSee [@smith_2024].\n\n![cap](img.png)\n\n```{=latex}\n\\input{figures/f.tex}\n```\n' > x.md
CSL=<worktree>/assets/csl/ieee.csl
TEXINPUTS="$S:" pandoc x.md --standalone --resource-path . --citeproc --csl "$CSL" \
  --bibliography x.bib --pdf-engine pdflatex -o before.pdf
openin_any=p TEXINPUTS="$S:" pandoc x.md --standalone --resource-path . --citeproc --csl "$CSL" \
  --bibliography x.bib --pdf-engine pdflatex --pdf-engine-opt=-no-shell-escape -o after.pdf
diff <(pdftotext before.pdf -) <(pdftotext after.pdf -) && echo SAME-TEXT
pdfimages -list before.pdf | tail -n +3 | wc -l; pdfimages -list after.pdf | tail -n +3 | wc -l
```

Expected: `SAME-TEXT`, the figure body in both, and an image count of 1
for each. (The `smith_2024` key is only a pandoc fixture here; no ledger
is involved.) Paste the output into the PR description. If the user has
a real corpus, ask them to render the digital-twins draft to `pdf` on
this branch. Do not claim that render was done.

- [ ] **Step 7: commit**

```bash
git add chitragupta/render_output/_pandoc.py tests/test_render_output_cli.py tests/test_render_output.py
git commit -m "Run pdflatex paranoid about reads and without shell escape on the pdf render path (#823)"
```

---

### Task 2: harden the figure-layout probe and the bench compile

**Files:**

- Modify: `chitragupta/review/figure_layout/_probe.py:195-202`
- Modify: `bench/bench_figure_similarity.py:253-259`
- Test: `tests/test_figure_layout.py`. Extend `TestMaxPrintLineEnv` (it
  already fakes `subprocess.run`), or add a sibling class next to it.

**Interfaces:** `node_boxes(figure_path: Path) -> dict[str, Box]` does
not change.

- [ ] **Step 1: write the failing tests**

```python
class TestProbeTexHardening:
    """#823: the probe compiles a user's figure file, so it gets the
    same two settings as the pdf render path."""

    def _run(self, tmp_path, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(_probe.subprocess, "run", fake_run)
        figure = tmp_path / "fig.tex"
        figure.write_text(
            "\\begin{tikzpicture}\\node (a) {A};\\end{tikzpicture}\n", encoding="utf-8"
        )
        figure_layout.node_boxes(figure)
        assert len(calls) == 1
        return calls[0]

    def test_shell_escape_is_off(self, tmp_path, monkeypatch):
        cmd, _ = self._run(tmp_path, monkeypatch)
        assert "-no-shell-escape" in cmd

    def test_reads_are_paranoid_even_if_the_host_says_otherwise(self, tmp_path, monkeypatch):
        monkeypatch.setenv("openin_any", "a")
        _, kwargs = self._run(tmp_path, monkeypatch)
        assert kwargs["env"]["openin_any"] == "p"
```

Run: `pytest tests/test_figure_layout.py::TestProbeTexHardening -v`
Expected: both FAIL.

- [ ] **Step 2: implement in `_probe.py`**

```python
        result = subprocess.run(
            [
                "pdflatex",
                "-no-shell-escape",
                "-interaction=nonstopmode",
                "-halt-on-error",
                probe.name,
            ],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
            # `openin_any=p` and `-no-shell-escape`: the figure file is
            # draft text, and a shared tree's draft text is someone
            # else's (#823). Same two settings, same reasons, as
            # render_output/_pandoc.py's pdf path.
            env={**os.environ, "max_print_line": _MAX_PRINT_LINE, "openin_any": "p"},
        )
```

- [ ] **Step 3: bench.** Add `"-no-shell-escape"` after `"pdflatex"` in
  `bench/bench_figure_similarity.py`'s argv, so the success criterion
  "never from this codebase" holds there too. Only the flag, no env
  change: the bench compiles fixtures this repository ships.

- [ ] **Step 4: run the tests**

Run: `pytest tests/test_figure_layout.py -v`
Expected: all PASS, including `TestProbeAgainstRealPdflatex`. It runs a
real compile and shows that paranoid reads still find `tikz.sty`.

- [ ] **Step 5: commit**

```bash
git add chitragupta/review/figure_layout/_probe.py bench/bench_figure_similarity.py tests/test_figure_layout.py
git commit -m "Compile figure probes without shell escape and with paranoid reads (#823)"
```

---

### Task 3: refuse figure and image siblings that resolve outside the draft

**Files:**

- Modify: `chitragupta/render_output/_figures.py:150-162`
  (`_resolve_sibling`). Add `from chitragupta import config`, as
  `_assets.py` does.
- Modify: `chitragupta/render_output/_assets.py:64-71`
  (`_copy_local_images`). Route it through `_resolve_sibling` and delete
  its duplicated spelling check.
- Test: `tests/test_render_output_figures.py::TestResolveSibling`
- Test: `tests/test_render_output_assets.py::TestCopyLocalImages`

**Interfaces:** `_resolve_sibling(draft_dir: Path, ref: str) -> Path | None`
does not change, and it still returns the *unresolved*
`draft_dir / ref`. That matters: `_copy_local_tex_includes` writes to
`dest_dir / ref`, and the TikZ-library scan and `_citekey_union_includes`
consume it unchanged. Every caller gets the new refusal without being
edited.

- [ ] **Step 1: write the failing tests**

In `TestResolveSibling`:

```python
    def test_refuses_a_symlink_that_lands_outside_the_draft(self, tmp_path):
        secret = tmp_path / "outside" / "secret.tex"
        secret.parent.mkdir()
        secret.write_text("marker")
        draft_dir = tmp_path / "drafts"
        (draft_dir / "figures").mkdir(parents=True)
        (draft_dir / "figures" / "x.tex").symlink_to(secret)
        assert render_output._resolve_sibling(draft_dir, "figures/x.tex") is None

    def test_refuses_a_symlinked_directory_that_lands_outside(self, tmp_path):
        (tmp_path / "outside").mkdir()
        (tmp_path / "outside" / "x.tex").write_text("marker")
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()
        (draft_dir / "figures").symlink_to(tmp_path / "outside", target_is_directory=True)
        assert render_output._resolve_sibling(draft_dir, "figures/x.tex") is None

    def test_keeps_a_symlink_that_stays_inside_the_draft(self, tmp_path):
        # Review focus 1: `current.tex -> v3.tex` is ordinary versioning.
        figure_pair(tmp_path)
        link = tmp_path / "figures" / "current.tex"
        link.symlink_to(tmp_path / "figures" / "fig1.tex")
        assert render_output._resolve_sibling(tmp_path, "figures/current.tex") == link

    def test_a_draft_directory_that_is_itself_a_symlink_still_resolves(self, tmp_path):
        # Review focus 2: both sides are resolved, so the link cancels out.
        real = tmp_path / "real"
        real.mkdir()
        figure_pair(real)
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)
        resolved = render_output._resolve_sibling(link, "figures/fig1.tex")
        assert resolved == link / "figures" / "fig1.tex"
```

In `TestCopyLocalImages`:

```python
    def test_skips_an_image_symlinked_out_of_the_draft(self, tmp_path):
        # Review focus 3: the image copier had its own spelling-only check.
        outside = tmp_path / "outside" / "secret.png"
        outside.parent.mkdir()
        outside.write_bytes(b"not yours")
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        (src_dir / "figure.png").symlink_to(outside)
        draft = src_dir / "draft.md"
        draft.write_text("![alt](figure.png)\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_images(draft, dest_dir)

        assert list(dest_dir.iterdir()) == []
```

Run:

```bash
pytest tests/test_render_output_figures.py::TestResolveSibling \
  tests/test_render_output_assets.py::TestCopyLocalImages -v
```

Expected: the two refusal tests in `TestResolveSibling` and the image
test FAIL. The two "keeps working" tests already PASS; they pin current
behaviour so the change cannot break it.

- [ ] **Step 2: implement `_resolve_sibling`**

```python
def _resolve_sibling(draft_dir: Path, ref: str) -> Path | None:
    """`ref` as a real file under `draft_dir`, or None.

    Two refusals. The spelling check is `_copy_local_tex_includes`'s,
    shared rather than restated: an absolute or `..`-escaping reference
    is never resolved. `resolves_inside` then catches what spelling
    cannot: a symlink, of the file or of a directory on the way to it,
    that lands outside `draft_dir` (#823). In a shared tree,
    `figures/x.tex -> /anywhere` would otherwise be compiled by the
    figure aid and copied into `content/rendered/`. Both sides are
    resolved, so a link that stays inside the draft, or a draft
    directory that is itself a link, still resolves. The returned path
    is the unresolved spelling, because callers write to
    `dest_dir / ref`.
    """
    ref_path = Path(ref)
    if ref_path.is_absolute() or ".." in ref_path.parts:
        return None
    candidate = draft_dir / ref_path
    if not candidate.is_file():
        return None
    return candidate if config.resolves_inside(candidate, draft_dir) else None
```

Split into two `if`s so branch coverage sees each refusal separately.
Check first that `from chitragupta import config` in `_figures.py` does
not create an import cycle (`python -c "import chitragupta.render_output"`).
`_assets.py` already imports it, so it should not.

- [ ] **Step 3: implement `_copy_local_images`**

```python
    for ref in _local_image_refs(input_path.read_text(encoding="utf-8")):
        src = _resolve_sibling(input_path.parent, ref)
        if src is None:
            continue
        _copy_beside(src, dest_dir / ref)
```

Update its docstring. The "absolute, or `..`-escaping" sentence becomes
"or any reference `_resolve_sibling` refuses: absolute, `..`-escaping,
or a symlink that lands outside `input_path`'s directory". Update
`_copy_local_tex_includes`'s docstring the same way, since it describes
its skip rules as mirroring this one. Run the existing
`TestCopyLocalImages` URL-encoded and angled-reference tests too:
`_local_image_refs` already unquotes, so `dest_dir / ref` matches the
old `dest_dir / ref_path`.

- [ ] **Step 4: run the tests**

Run:

```bash
pytest tests/test_render_output_figures.py \
  tests/test_render_output_assets.py tests/test_figure_layout.py \
  tests/test_render_output_tikz_libraries.py -v
```

Plus the citekey-union tests, `pytest -k citekey_union -v`.
Expected: all PASS.

- [ ] **Step 5: commit**

```bash
git add chitragupta/render_output/_figures.py chitragupta/render_output/_assets.py tests/test_render_output_figures.py tests/test_render_output_assets.py
git commit -m "Refuse figure and image siblings that resolve outside the draft directory (#823)"
```

---

### Task 4: document it, run the full suite, bump, ship

**Files:**

- Modify: `docs/SECURITY.md`
  - "Content-root containment and symlink-aware checks" (about line
    105): add a paragraph saying figure and image references are
    resolved and refused if they land outside the draft's own directory.
  - "Parameterised local-tool invocation" (about line 135): add that
    every `pdflatex` this codebase starts runs with `-no-shell-escape`
    and `openin_any=p`, and what that stops. Also say it does *not*
    cover a `tex` output or a `--fragment` unit compiled later by the
    reader's own engine, and that EPS figures no longer convert (Review
    focus 5).
- Modify: the version (see the "Versioning and releases" section of
  `DEVELOPER-AGENTS.md`), PATCH.

- [ ] **Step 1: edit the docs as above.** Keep the file's existing
  plain, non-marketing register.
- [ ] **Step 2: run every local check** that `DEVELOPER-AGENTS.md`'s
  "Before claiming a task complete" section lists: full pytest with
  coverage (100% line and branch), ruff, markdownlint with the globs it
  gives (they include `plans/**/*.md`, so this file too), and the OCR
  review step.
- [ ] **Step 3: at the top of this plan, add the line saying which PR
  closed it**, as `plans/README.md` requires.
- [ ] **Step 4: commit, push, open the PR.** Link this plan. Put the
  measurement table from "The departure from the issue" and Task 1 Step
  6's before/after output in the description. Tick the issue's success
  criteria, and change the first one's wording to "pdflatex runs
  paranoid about reads on the citeproc path", saying why.

## Out of scope, and saying so in the PR

- **`tex` output.** pandoc writes the bib field's raw
  `\input{/abs/...}` into the `.tex` it emits. Whoever compiles that
  file later uses their own engine and their own `openin_any`. This
  project cannot set that. Opening a follow-up issue (for example, escape
  or strip TeX control sequences from bib fields before citeproc) is the
  user's decision. Mention it and do not open it.
- **`--fragment` (natbib) units.** `bibtex` and the book's own compile
  happen outside this codebase. Same reasoning.
- **pandoc `--sandbox`.** Deliberately not added. See the measurement
  table.
