"""Which directory answers a question about an assembled book.

An assembly and the records it is checked against no longer live in one
place. `book-assembler` writes `book.tex`, the per-unit `.tex` fragments
and `book.md` into `content/rendered/<book>/`; the units' authored `.md`
stays in `content/drafts/<book>/` and their acceptance records in
`content/specs/<book>/`. So "the book directory" is two directories, and
which one is right depends on what is being asked:

- **The fragments** are beside the assembly. `_citekey_union_includes`
  resolves `\\input{ch-01}` against the assembly's own directory, because
  that is where LaTeX resolves it from.
- **The records** are reached from the *drafts* directory.
  `unit.acceptance_units`, `unit.state` and `unit.record_path` all route
  through `spec.spec_dir`, which requires a path under
  `config.DRAFTS_DIR` and raises `spec.SpecError` otherwise.

`citekey_union.compute` derived one directory for both jobs, which was
correct only while they coincided. Split here rather than inline at each
call site so the two questions are named, and so `refuse_a_unit` cannot
drift from `compute`.

**Why a module of its own.** `chitragupta/review/__init__.py` is where
this would otherwise sit, next to `report_dir` which is one of its
callers -- but C2 leaves it three code lines of headroom and
`citekey_union.py` eleven (`python3 scripts/code_standards.py`), and a
rule that would be broken by the fix for a real bug is still the rule.
"""

from pathlib import Path

from chitragupta import config


def drafts_dir_for(assembled: Path) -> Path:
    """The `content/drafts/` book directory `assembled` is checked against.

    `assembled.parent` for anything not under `content/rendered/`, which
    is the same fallback `report_dir` and `render_output._output_dir`
    already make for an input that is legitimately elsewhere under
    `content/`: a book assembled before the layout moved still has its
    units beside it, and refusing to read one would be a worse answer
    than reading it where it actually is.

    Says nothing about whether the result exists. A path under
    `content/rendered/` with no book behind it maps to a `content/drafts/`
    directory with no spec in it, and `spec.spec_dir`'s own refusal is
    the right place for that to be reported -- it names the missing spec,
    which is what the reader has to go and write.
    """
    mirrored = config.mirrored_dir(assembled, config.RENDERED_DIR, config.DRAFTS_DIR)
    return Path(assembled).parent if mirrored is None else mirrored


def review_dir_for(draft: Path) -> "Path | None":
    """`draft`'s place under `config.REVIEW_DIR`, or None if it has none.

    `content/drafts/` first, which is every draft the other nine aids
    read. `content/rendered/` second, for the one input that is an
    assembly rather than a draft: without it `book.tex` mirrors to
    nothing and every book in the project shares one flat
    `content/review/book.union.md`, which is a collision rather than a
    fallback -- the reports overwrite each other.

    None is still the answer for an input under neither, and
    `report_dir`'s flat fallback still handles it: that case is a draft
    legitimately elsewhere under `content/`, where writing flat collides
    with nothing.
    """
    for source in (config.DRAFTS_DIR, config.RENDERED_DIR):
        mirrored = config.mirrored_dir(draft, source, config.REVIEW_DIR)
        if mirrored is not None:
            return mirrored
    return None
