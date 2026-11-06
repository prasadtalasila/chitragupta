"""Re-render the diagram exports and record which source each came from (#850).

    python scripts/render_diagrams.py                 # every diagram
    python scripts/render_diagrams.py v1-overview     # just these
    python scripts/render_diagrams.py --puppeteer-config pp.json
    python scripts/render_diagrams.py --sync          # stamp the theme, copy to .mmd

Runs the commands docs/DIAGRAMS.md documents for each
`docs/diagrams/<name>.mmd`: `mmdc` to `svg/<name>.svg` at `-w 1900` and
to `pdf/<name>.pdf` with `--pdfFit`, both on white. Then
it records the source's fingerprint in
`docs/diagrams/svg/sources.json`. `tests/test_diagrams_in_sync.py` checks
every export against that manifest, so an `.mmd` edited without a
re-render fails with a message naming the source to re-render -- where
before only a stale *aid name* in an SVG was caught, and any other edit
to a diagram left its picture silently out of date.

The manifest records what was rendered, not what was intended: a render
that fails records nothing, so the file can never claim a freshness no
render produced.

mermaid-cli 11 is the pinned major: 12 dropped the `-w` flag this command
uses. A host that cannot sandbox Chromium (a container, CI) passes
`--puppeteer-config` a JSON file holding `{"args": ["--no-sandbox"]}`.

**The house theme (#1017).** Every diagram opens with one Mermaid init
directive, and every flowchart closes with the same four role
`classDef`s: `flow`, `alt`, `key` and `absent`, the roles
docs/TIKZ-STYLE.md gives the TikZ palette. Both are generated here, from
that file's `\\definecolor` block, so no hex is typed twice and the two
halves of the house style cannot drift. GitHub renders a fenced block as
it stands and cannot include a shared file, so the text has to be in every
block; `--sync` is what puts it there. It rewrites each fenced block in
docs/DIAGRAMS.md, and each one elsewhere under docs/ that a
`<!-- diagram: <name> -->` line names, to carry the current theme, and
copies the block into its `.mmd`, which is also the copy step that file
used to ask for by hand. It renders nothing: run the script again,
without `--sync`, on the names it prints.
"""

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
DIAGRAMS = DOCS / "diagrams"
MANIFEST = DIAGRAMS / "svg" / "sources.json"
DIAGRAMS_MD = REPO_ROOT / "docs" / "DIAGRAMS.md"
STYLE_DOC = REPO_ROOT / "docs" / "TIKZ-STYLE.md"

EDITING_HEADING = "## ✏ Editing these"
_NAME_ROW = re.compile(r"^\| [^|]+ \| `([\w-]+)` \|$", re.MULTILINE)
_BLOCK = re.compile(r"(```mermaid\n)(.*?)(```)", re.DOTALL)
_TITLE = re.compile(r"\A---\ntitle:.*?\n---\n", re.DOTALL)
# The line naming a block outside DIAGRAMS.md, directly above its fence.
MARKER = "<!-- diagram: {} -->"
_MARKER = re.compile(r"<!-- diagram: ([a-z0-9][a-z0-9-]*) -->\n\Z")

# The house theme lives in scripts/diagram_theme.py, loaded by path: this
# file runs both as `python scripts/render_diagrams.py` and as
# `scripts.render_diagrams`, which put different directories on
# `sys.path`, so no plain import works in both (scripts/merge_pr.py loads
# its sibling the same way).
_THEME_SPEC = importlib.util.spec_from_file_location(
    "diagram_theme", Path(__file__).resolve().parent / "diagram_theme.py"
)
_theme = importlib.util.module_from_spec(_THEME_SPEC)
_THEME_SPEC.loader.exec_module(_theme)
ROLES, palette, tint = _theme.ROLES, _theme.palette, _theme.tint
house_theme, stamp, mermaid_css = _theme.house_theme, _theme.stamp, _theme.mermaid_css


def fingerprint(source: Path) -> str:
    """sha256 of `source` with line endings normalised to LF, so a CRLF
    checkout (Windows under `core.autocrlf`) matches the manifest too."""
    return hashlib.sha256(source.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def export_names(text: str) -> list[str]:
    """The `<name>` column of DIAGRAMS.md's "Editing these" table, in
    order. That table is the one hand-kept list of diagrams (#866), and
    its order is what ties fenced block i to export i. Refuses to return
    an empty list: an empty list would make every check over it vanish
    while the run stayed green."""
    _, found, tail = text.partition(EDITING_HEADING)
    names = _NAME_ROW.findall(tail) if found else []
    if not names:
        raise ValueError(
            f"docs/DIAGRAMS.md no longer has a {EDITING_HEADING!r} table to read. "
            "Rewording it is fine; teach _NAME_ROW the new shape in the same change."
        )
    return names


def marked_names(text: str, where: str) -> list[str]:
    """The export name of each fenced block in a doc other than
    DIAGRAMS.md: the `<!-- diagram: <name> -->` line directly above it.
    A block without one is refused, so no diagram goes unexported."""
    names = []
    for match in _BLOCK.finditer(text):
        marker = _MARKER.search(text, 0, match.start())
        if marker is None:
            raise ValueError(
                f"docs/{where} has a mermaid block with no {MARKER.format('<name>')} line "
                "directly above it; add one naming its export in docs/diagrams/."
            )
        names.append(marker.group(1))
    return names


def sources() -> "list[tuple[Path, list[str]]]":
    """Every doc holding diagrams, with each block's export name in block
    order: DIAGRAMS.md from its 'Editing these' table, then every other
    doc under docs/ from its marker lines. A name used twice is refused:
    two blocks would overwrite one export."""
    found = [(DIAGRAMS_MD, export_names(DIAGRAMS_MD.read_text(encoding="utf-8")))]
    for path in sorted(DOCS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if path.resolve() != DIAGRAMS_MD.resolve() and "```mermaid" in text:
            found.append((path, marked_names(text, path.relative_to(DOCS).as_posix())))
    names = [name for _, listed in found for name in listed]
    twice = sorted({name for name in names if names.count(name) > 1})
    if twice:
        raise ValueError(f"more than one diagram: {', '.join(twice)}; give each its own name.")
    return found


def blocks(text: str) -> list[str]:
    """Every fenced `mermaid` block's body, in document order."""
    return [match.group(2) for match in _BLOCK.finditer(text)]


def _restamp(text: str, theme: tuple[str, str]) -> str:
    """`text` with every fenced block carrying `theme`."""
    return _BLOCK.sub(lambda m: m.group(1) + stamp(m.group(2), theme) + m.group(3), text)


def sync() -> list[str]:
    """Stamp the current theme into every fenced block of every doc in
    `sources()` and copy each block into its `.mmd`, keeping the
    `.mmd`'s title front matter. Returns the names whose `.mmd` changed:
    the ones that need re-rendering."""
    colours = palette(STYLE_DOC.read_text(encoding="utf-8"))
    theme = house_theme(colours)
    stylesheet = DOCS / "stylesheets" / "mermaid.css"
    stylesheet.parent.mkdir(parents=True, exist_ok=True)
    stylesheet.write_text(mermaid_css(colours), encoding="utf-8")
    changed = []
    for path, names in sources():
        text = path.read_text(encoding="utf-8")
        found = blocks(text)
        if len(found) != len(names):
            raise ValueError(
                f"docs/DIAGRAMS.md has {len(found)} fenced blocks but its 'Editing these' "
                f"table lists {len(names)}. Add or remove the row with the diagram."
            )
        text = _restamp(text, theme)
        path.write_text(text, encoding="utf-8")
        for name, block in zip(names, blocks(text)):
            mmd = DIAGRAMS / f"{name}.mmd"
            old = mmd.read_text(encoding="utf-8") if mmd.is_file() else ""
            title = _TITLE.match(old)
            new = (title.group(0) if title else "") + block
            if new != old:
                mmd.write_text(new, encoding="utf-8")
                changed.append(name)
    return changed


# Each export and the flags that make it. Mermaid writes an SVG's labels
# as HTML in <foreignObject>, which only a browser draws: LaTeX, rsvg and
# Inkscape show empty boxes. So the PDF (vector, cropped to the diagram, for
# papers and slides) comes from the same browser render.
FORMATS = {"svg": ["-w", "1900"], "pdf": ["--pdfFit"]}


def _argvs(name: str, puppeteer_config: "str | None") -> "list[tuple[str, list[str]]]":
    """`(format, argv)` for each of `name`'s exports."""
    source = ["mmdc", "-i", str(DIAGRAMS / f"{name}.mmd"), "-b", "white"]
    extra = ["-p", puppeteer_config] if puppeteer_config else []
    return [
        (fmt, [*source, "-o", str(DIAGRAMS / fmt / f"{name}.{fmt}"), *flags, *extra])
        for fmt, flags in FORMATS.items()
    ]


def _rendered(name: str, run, puppeteer_config: "str | None") -> bool:
    """Every format of `name` rendered; the first failure is printed."""
    for fmt, argv in _argvs(name, puppeteer_config):
        result = run(argv, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(
                f"{name}.{fmt}: mmdc exited {result.returncode}\n{result.stderr}", file=sys.stderr
            )
            return False
    return True


def render(
    names: list[str],
    *,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    puppeteer_config: "str | None" = None,
) -> int:
    """Render each of `names` in every format and record the ones whose
    every format rendered. Returns 0 when all did, 1 when any failed --
    after recording the others, so a second run only has the failures
    left to do."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else {}
    for fmt in FORMATS:
        (DIAGRAMS / fmt).mkdir(parents=True, exist_ok=True)
    failed = 0
    for name in names:
        try:
            ok = _rendered(name, run, puppeteer_config)
        except FileNotFoundError:
            print(
                "mmdc is not on PATH: npm install -g @mermaid-js/mermaid-cli@11",
                file=sys.stderr,
            )
            return 1
        if not ok:
            failed = 1
            continue
        manifest[name] = fingerprint(DIAGRAMS / f"{name}.mmd")
        print(f"rendered {name}")
    if manifest:
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return failed


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help="diagram names; every .mmd when omitted")
    parser.add_argument("--puppeteer-config", help="passed to mmdc as -p")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="stamp the house theme into every doc's mermaid blocks and copy them to .mmd files",
    )
    args = parser.parse_args(argv)
    if args.sync:
        changed = sync()
        if changed:
            print(f"re-render: python scripts/render_diagrams.py {' '.join(changed)}")
        else:
            print("every .mmd already matches its block")
        return 0
    known = sorted(path.stem for path in DIAGRAMS.glob("*.mmd"))
    unknown = sorted(set(args.names) - set(known))
    if unknown:
        print(f"no such diagram: {', '.join(unknown)} (have: {', '.join(known)})", file=sys.stderr)
        return 2
    return render(args.names or known, puppeteer_config=args.puppeteer_config)


if __name__ == "__main__":
    sys.exit(main())
