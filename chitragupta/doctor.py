"""`chitragupta doctor`: probe the environment, report, never install.

An aid, not a gate (SOUL.md, docs/HOOKS.md): always exits 0, with a
status word and a detail per line; only a `PATH` probe can say
`missing-binary`. Checks, none fatal:

1. OS binaries pip cannot supply, once up front rather than at the first
   render; pdflatex is listed as `[optional]` for thesis templates (#1037).
2. Is every module of the `enrich` extra importable, without importing
   `chitragupta.enrich`?
3. Does torch see this host's GPU? `pip install` on CUDA lands a CPU
   wheel silently (#265); `chitragupta install gpu-torch` fixes it.
4. Does another distribution provide `chitragupta`/`cg`? (#269, an
   unrelated PyPI package)
5. Can each harness's hook launcher start? (#812,
   `chitragupta/launcher_configs.py`)
6. Does OpenCode see only its own skill copies? (#900)
7. Can LuaLaTeX find every pdf font? (#996) Looked up with
   `luaotfload-tool`, the render's own database; `dpkg` once reported an
   empty font package as installed.
"""

import argparse
import importlib.metadata
import importlib.util
import json
import sys
from pathlib import Path

from chitragupta import install, launcher_configs, pdf_fonts, programs
from chitragupta.progname import prog_for
from chitragupta.help_format import ClickParser

DESCRIPTION = (
    "Report the toolchain's state -- OS binaries, the enrich "
    "extra, torch vs. the GPU driver, a competing distribution, hook launchers."
)

# The binaries render, style, figure and a book build run (#1052, #1168),
# probed once, up front.
BINARIES = (
    "pandoc",
    "lualatex",
    "pdftotext",
    "pdftoppm",
    "pdfinfo",
    "vale",
    "bibtexu",
    "upmendex",
    "latexdiff",
)

THIS_DISTRIBUTION = "chitragupta-cli"
CONSOLE_SCRIPTS = ("chitragupta", "cg")


def _check_binaries() -> list[str]:
    found = []
    for binary in BINARIES:
        path = programs.resolve_program(binary)
        if path:
            found.append(f"[ok] {binary} found: {path}")
        else:
            found.append(f"[missing-binary] {binary} not found on PATH")
    return found


def _check_optional_pdflatex() -> str:
    """pdflatex, which the pipeline no longer runs (#1037) but a thesis
    author whose template forces it does, with chitragupta-unicode.sty
    beside the fragment. Absent is said plainly and is not a problem."""
    path = programs.resolve_program("pdflatex")
    if path:
        return f"[ok] pdflatex found: {path} (optional: only a pdflatex thesis template uses it)"
    return (
        "[optional] pdflatex not found on PATH -- only needed if your thesis "
        "template forces pdflatex; the pipeline itself uses lualatex"
    )


# Import names, not distribution names: what a stage imports is what a
# partial install breaks.
ENRICH_MODULES = (
    "torch",
    "torchvision",
    "sentence_transformers",
    "chromadb",
    "bertopic",
    "docling",
    "adapters",
    "scipy",
    "networkx",
    "pypdfium2",
)


def _check_enrich_extra() -> str:
    """Every module the extra installs, not one of them (#509): a partial
    or interrupted install is the likely state, and probing one module
    passed hosts that then failed at `docling`.
    """
    missing = [module for module in ENRICH_MODULES if importlib.util.find_spec(module) is None]
    if not missing:
        return "[ok] the enrich extra is importable"
    if len(missing) == len(ENRICH_MODULES):
        return "[missing] the enrich extra is not installed -- chitragupta install enrich"
    return (
        f"[missing] the enrich extra is installed but incomplete: {', '.join(missing)} "
        "-- chitragupta install enrich"
    )


def _check_gpu_torch() -> str:
    if not programs.resolve_program("nvidia-smi"):
        return "[ok] no GPU detected (nvidia-smi absent) -- the default CPU wheel is correct"
    try:
        import torch  # pylint: disable=import-outside-toplevel
    except ImportError:
        return "[skipped] nvidia-smi is present but torch is not installed"
    if torch.cuda.is_available():
        return "[ok] torch sees the GPU"
    return (
        "[gpu-mismatch] nvidia-smi reports a GPU but torch cannot see it -- "
        "run: chitragupta install gpu-torch"
    )


def _competing_distributions() -> set[str]:
    """Every distribution besides this one that declares a `chitragupta`
    or `cg` console script -- the collision #269 accepts on the condition
    that it stops being silent."""
    found = set()
    for dist in importlib.metadata.distributions():
        name = dist.name
        if name == THIS_DISTRIBUTION:
            continue
        for entry_point in dist.entry_points:
            if entry_point.group == "console_scripts" and entry_point.name in CONSOLE_SCRIPTS:
                found.add(name)
    return found


def _check_competing_distribution() -> str:
    others = _competing_distributions()
    if not others:
        return "[ok] no competing chitragupta/cg distribution found"
    return (
        f"[collision] {', '.join(sorted(others))} also provides chitragupta/cg -- "
        "install into separate virtualenvs"
    )


OPENCODE_PLUGIN = Path(".opencode") / "plugins" / "chitragupta-gate.js"
OPENCODE_SKILLS = Path(".opencode") / "skills"
OPENCODE_CONFIG = Path(".opencode") / "opencode.json"
OPENCODE_SUFFIX = "-opencode"


def _check_launchers(root: Path) -> list[str]:
    """Each harness launcher's faults, or one ok line when there are none."""
    found = [f"[launcher] {fault}" for fault in launcher_configs.faults(root)]
    if (root / ".opencode").is_dir() and not (root / OPENCODE_PLUGIN).is_file():
        found.append(
            f"[launcher] .opencode/ exists but {OPENCODE_PLUGIN.as_posix()} does not, so "
            "OpenCode runs no citation gate -- chitragupta init --agent opencode"
        )
    return found or ["[ok] every hook launcher found can start"]


def _check_opencode_skills(root: Path) -> list[str]:
    """Does OpenCode see only its own skill copies?

    OpenCode also reads `.claude/skills/` and `.agents/skills/`, and keys
    skills by name, so without `.opencode/opencode.json` denying the
    unsuffixed names it would load the other harnesses' wording
    (docs/HARNESS.md). Silent on a project with no OpenCode skills.
    """
    skills = root / OPENCODE_SKILLS
    if not skills.is_dir():
        return []
    names = sorted(p.name.removesuffix(OPENCODE_SUFFIX) for p in skills.iterdir() if p.is_dir())
    try:
        config = json.loads((root / OPENCODE_CONFIG).read_text(encoding="utf-8"))
        rules = config["permission"]["skill"]
    except (OSError, ValueError, KeyError, TypeError):
        rules = {}
    allowed = [name for name in names if not isinstance(rules, dict) or rules.get(name) != "deny"]
    if not allowed:
        return ["[ok] OpenCode sees only its own skill copies"]
    return [
        f"[skills] {OPENCODE_CONFIG.as_posix()} does not deny {', '.join(allowed)}, so OpenCode "
        "may load the Claude Code or Codex wording of those skills -- restore the deny list "
        "chitragupta init --agent opencode writes"
    ]


def _check_pdf_fonts() -> list[str]:
    """One line per font family a pdf render names (#996)."""
    if programs.resolve_program("luaotfload-tool") is None:  # one line, not one per font
        return [
            "[missing-binary] luaotfload-tool not found on PATH: LuaLaTeX's font "
            "loader (texlive-luatex) is not installed, so no pdf renders; "
            f"{install.remedy('os-deps')} installs it"
        ]
    lines = []
    for name in pdf_fonts.all_families():
        if pdf_fonts.font_installed(name):
            lines.append(f"[ok] pdf font found: {name}")
            continue
        # A required font stops every render; a fallback only a draft
        # holding a character no earlier font in the chain has (#1022).
        effect = (
            "no pdf renders without it"
            if name in pdf_fonts.REQUIRED_FONTS
            else "a draft with a character only it has will not render to pdf"
        )
        lines.append(
            f"[missing] pdf font {name}: {effect}; {install.remedy('os-deps')} installs it"
        )
    return lines


def build_parser() -> argparse.ArgumentParser:
    return ClickParser(prog=prog_for("doctor"), description=DESCRIPTION)


def main(argv=None) -> int:
    build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    lines = [
        *_check_binaries(),
        _check_optional_pdflatex(),
        _check_enrich_extra(),
        _check_gpu_torch(),
        _check_competing_distribution(),
        *_check_launchers(Path.cwd()),
        *_check_opencode_skills(Path.cwd()),
        *_check_pdf_fonts(),
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
