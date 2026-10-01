"""Re-render the diagram exports and record which source each came from (#850).

    python scripts/render_diagrams.py                 # every diagram
    python scripts/render_diagrams.py v1-overview     # just these
    python scripts/render_diagrams.py --puppeteer-config pp.json

Runs the command docs/DIAGRAMS.md documents,
`mmdc -i <name>.mmd -o svg/<name>.svg -b white -w 1900`, for each
`docs/diagrams/<name>.mmd`, then records the source's fingerprint in
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
"""

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS = REPO_ROOT / "docs" / "diagrams"
MANIFEST = DIAGRAMS / "svg" / "sources.json"


def fingerprint(source: Path) -> str:
    """sha256 of `source` with line endings normalised to LF, so a CRLF
    checkout (Windows under `core.autocrlf`) matches the manifest too."""
    return hashlib.sha256(source.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _argv(name: str, puppeteer_config: "str | None") -> list[str]:
    argv = [
        "mmdc",
        "-i",
        str(DIAGRAMS / f"{name}.mmd"),
        "-o",
        str(DIAGRAMS / "svg" / f"{name}.svg"),
        "-b",
        "white",
        "-w",
        "1900",
    ]
    return argv + ["-p", puppeteer_config] if puppeteer_config else argv


def render(
    names: list[str],
    *,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    puppeteer_config: "str | None" = None,
) -> int:
    """Render each of `names` and record the ones that rendered. Returns
    0 when all did, 1 when any failed -- after recording the others, so a
    second run only has the failures left to do."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else {}
    failed = 0
    for name in names:
        try:
            result = run(_argv(name, puppeteer_config), capture_output=True, text=True, check=False)
        except FileNotFoundError:
            print(
                "mmdc is not on PATH: npm install -g @mermaid-js/mermaid-cli@11",
                file=sys.stderr,
            )
            return 1
        if result.returncode != 0:
            print(f"{name}: mmdc exited {result.returncode}\n{result.stderr}", file=sys.stderr)
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
    args = parser.parse_args(argv)
    known = sorted(path.stem for path in DIAGRAMS.glob("*.mmd"))
    unknown = sorted(set(args.names) - set(known))
    if unknown:
        print(f"no such diagram: {', '.join(unknown)} (have: {', '.join(known)})", file=sys.stderr)
        return 2
    return render(args.names or known, puppeteer_config=args.puppeteer_config)


if __name__ == "__main__":
    sys.exit(main())
