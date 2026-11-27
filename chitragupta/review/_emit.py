"""How a review aid prints and files its report (#849).

`review/__init__.py` fixes the output contract; this is the procedure
every aid copied around it (decide what to print from `--json`/`--write`,
build command and payload only when needed, file `.md` and `.json`, move
the summary to stderr when stdout is a payload), so a change lands once.
"""

import argparse
import json
import shlex
import sys
from collections.abc import Callable
from pathlib import Path

from chitragupta import install, review

# Every aid's --formats help, written once: ten copies went on naming
# pdflatex after #996 moved pdf to LuaLaTeX (#1022). Matches docs/CLI.md.
FORMATS_HELP = (
    "Additional formats to render beside the Markdown report (default: "
    "md,tex,pdf). The .md is always written -- it is the report; tex and "
    "pdf are renders of it: tex needs pandoc, and pdf needs pandoc and "
    f"LuaLaTeX with the fonts {install.remedy('os-deps')} installs."
)


def add_formats(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--formats", default="md,tex,pdf", help=FORMATS_HELP)


def formats(args: argparse.Namespace) -> list[str]:
    """`--formats md,pdf` as `["md", "pdf"]`; `"md, pdf,"` means what its
    author meant."""
    return [fmt.strip() for fmt in args.formats.split(",") if fmt.strip()]


def emit(
    draft: Path,
    aid: str,
    args: argparse.Namespace,
    *,
    text: Callable[[], str],
    command: Callable[[], str],
    payload: Callable[[str], dict],
    markdown: Callable[[str], str],
) -> int:
    """Print, and under `--write` file, one aid's report. Returns 0: an
    aid is advisory whatever it found.

    Each piece is a callable built only when needed (no human text under
    `--json`, nothing extra for a bare run). `command()` is called once and
    shared, so the report and its `.json` name the same invocation.
    """
    if not (args.json or args.write):
        print(text())
        return 0
    invocation = command()
    data = payload(invocation)
    print(json.dumps(data, indent=2) if args.json else text())
    if args.write:
        written = review.write(draft, aid, markdown(invocation), formats(args))
        written["json"] = review.write_json(draft, aid, data)
        review.print_written(written, stream=sys.stderr if args.json else sys.stdout)
    return 0


def recheck_command(aid: str, draft: str | Path, baseline: str | Path) -> str:
    """The `--baseline ... --json` invocation a comparison records in its
    envelope so it can be regenerated; `--json` since only JSON has one."""
    parts = ["python", "-m", "chitragupta.review", aid, str(draft)]
    return shlex.join([*parts, "--baseline", str(baseline), "--json"])


def read_baseline(path: str | Path, aid: str, label: str) -> dict:
    """A filed `<stem>.<aid>.json`, read back as a `--baseline` basis.

    Refuses unreadable JSON and another aid's payload (also a dict, which
    would report every item as new). `label` is the refusal's noun phrase
    ("an agenda payload").
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Cannot read the baseline {path}: {exc}") from None
    except json.JSONDecodeError:
        raise ValueError(
            f"{path} is not {label} -- it is not valid JSON. "
            f"Write one with `review {aid} <draft>`, which files it as "
            "the report's .json sibling."
        ) from None
    if not isinstance(payload, dict) or payload.get("aid") != aid or "items" not in payload:
        raise ValueError(
            f"{path} is not {label}. Write one with `review {aid} <draft>`, "
            "which files it as the report's .json sibling."
        )
    return payload


def announce(data: dict, written: dict[str, Path], *, as_json: bool) -> None:
    """After filing: the payload under `--json`, summary moved to stderr so
    stdout stays valid JSON; otherwise the summary alone."""
    if as_json:
        print(json.dumps(data, indent=2))
        review.print_written(written, stream=sys.stderr)
    else:
        review.print_written(written)
