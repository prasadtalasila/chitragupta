"""Two prompt-cost claims this project makes on n = 1, measured on n many.

`docs/TOKENS.md` reports a 17.4x dispatch-pointer saving from **one**
example report, and the paper's Evaluation section quotes "an estimated
4.6k-token whole-file rewrite" -- an estimate, not a measurement. #610
(B8) asks for both over several real drafts, which is what this does.

Two arms, both counted in **characters** and converted at the four
characters per token this project documents everywhere else. No model is
called: characters are countable, reproducible and free, and a
tokeniser's exact split is not what either claim turns on.

- **Rewrite arm.** What a whole-file rewrite re-emits (every character
  of the draft) against what a section-scoped edit re-emits (the edited
  section alone). Reported per draft as the whole-file cost, the median
  and largest section, and the ratio between them -- the ratio is the
  claim, because it is what survives a change of draft length.

- **Dispatch arm.** For every section of every draft with a dossier:
  the evidence a Phase 5 dispatch would have pasted -- the real output
  of `chitragupta.draft dossier brief --section`, the same call the
  shipped skill makes -- against the one dispatch line that replaces it.
  `docs/TOKENS.md` measured exactly this on one report; this runs it on
  every committed report and every book chapter that has a dossier.

Sections that cite nothing contribute a zero to both sides and are
counted as such rather than dropped: a report where two of seven
sections had nothing to paste is a report where the saving is smaller
than the cited sections alone suggest, and hiding those rows would
overstate it.

Stdlib only apart from the `chitragupta.draft` CLI it shells out to.
Needs the drafts and their dossiers; needs no GPU and no corpus parse.

    CHITRAGUPTA_PROJECT=. .venv-full/bin/python \\
        bench/bench_prompt_economics.py --tag 2026-09-04-prompt-economics
"""

import argparse
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chitragupta import config  # noqa: E402

# The conversion docs/TOKENS.md uses throughout. Stated as a constant so
# a reader can see it is an assumption rather than a measurement.
CHARS_PER_TOKEN = 4
# The line that replaces a pasted evidence payload in a Phase 5 dispatch,
# as .claude/skills/deep-research/SKILL.md writes it.
DISPATCH_LINE = (
    'Your evidence: python -m chitragupta.draft dossier brief {draft} --section "{section}"'
)
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


def tokens(characters: int) -> int:
    """Characters at the documented four-per-token conversion."""
    return round(characters / CHARS_PER_TOKEN)


def split_sections(text: str) -> list:
    """`[(heading, body characters)]`, one per Markdown heading.

    The material before the first heading is its own row under the
    empty title: a draft's preamble is real text a whole-file rewrite
    re-emits, and dropping it would understate the whole-file arm.
    """
    matches = list(_HEADING.finditer(text))
    if not matches:
        return [("", len(text))]
    sections = [("", matches[0].start())] if matches[0].start() else []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((match.group(2).strip(), end - match.start()))
    return sections


def rewrite_arm(draft: Path) -> dict:
    """Whole-file re-emission against per-section re-emission."""
    text = draft.read_text(encoding="utf-8", errors="replace")
    sizes = [size for _title, size in split_sections(text)]
    median = statistics.median(sizes) if sizes else 0
    return {
        "draft": str(draft.relative_to(config.CONTENT_DIR)),
        "words": len(text.split()),
        "sections": len(sizes),
        "whole_file_chars": len(text),
        "whole_file_tokens": tokens(len(text)),
        "median_section_chars": int(median),
        "median_section_tokens": tokens(median),
        "largest_section_chars": max(sizes) if sizes else 0,
        "ratio_whole_to_median_section": round(len(text) / median, 2) if median else None,
    }


def _brief(dossier: Path, section: str) -> tuple:
    """`(characters, outcome)` from one `dossier brief --section` call.

    The outcome matters as much as the count, because there are three
    different zeros and reporting them as one number would hide the only
    interesting thing this arm found:

    - `cited-and-resolved` -- blocks were printed; this is a real payload.
    - `cited-no-block` -- the section cites sources but `evidence.md`
      carries no block for them, so a dispatch had nothing to paste
      *and neither would a reader*. A zero here is a fact about the
      dossier, not about the saving.
    - `uncited` -- the section cites nothing; an honest zero on both
      sides, the kind docs/TOKENS.md already reported for two of its
      seven sections.
    - `no-such-section` -- the draft's heading is not a `sections.md`
      row, so this pairing could not be measured at all.
    """
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "chitragupta.draft",
            "dossier",
            "brief",
            str(dossier),
            "--section",
            section,
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO),
    )
    if completed.returncode == 0:
        return len(completed.stdout), "cited-and-resolved"
    if "No section matching" in completed.stderr:
        return 0, "no-such-section"
    if re.search(r"0 of (?!0\b)\d+ citekey", completed.stderr):
        return 0, "cited-no-block"
    return 0, "uncited"


def dispatch_arm(draft: Path, dossier: Path) -> dict:
    """Pasted evidence against dispatch lines, per section, for one draft."""
    text = draft.read_text(encoding="utf-8", errors="replace")
    pasted, dispatched = 0, 0
    outcomes: dict = {}
    for title, _size in split_sections(text):
        if not title:
            continue
        payload, outcome = _brief(dossier, title)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        pasted += payload
        dispatched += len(DISPATCH_LINE.format(draft=draft, section=title))
    return {
        "draft": str(draft.relative_to(config.CONTENT_DIR)),
        "sections": sum(1 for title, _ in split_sections(text) if title),
        "section_outcomes": outcomes,
        "pasted_chars": pasted,
        "dispatch_chars": dispatched,
        "pasted_tokens": tokens(pasted),
        "dispatch_tokens": tokens(dispatched),
        "ratio": round(pasted / dispatched, 2) if dispatched else None,
    }


def self_check() -> None:
    """Fabricate a difference each arm's arithmetic must see.

    The section splitter is where this script could silently lie: a
    splitter that lost the preamble, or that merged two sections, would
    inflate the median section and so deflate the very ratio the rewrite
    arm publishes. So it is checked on a document with a preamble, two
    headings of different depths, and known character counts.
    """
    doc = "pre\n\n# One\n\nbody one\n\n## Two\n\nbody two\n"
    got = split_sections(doc)
    assert [title for title, _ in got] == ["", "One", "Two"], got
    assert sum(size for _t, size in got) == len(doc), "the split must lose no character"
    assert split_sections("no headings here") == [("", 16)], split_sections("no headings here")
    assert tokens(15660) == 3915, tokens(15660)
    # The ratio the dispatch arm publishes, on docs/TOKENS.md's own
    # recorded figures: 15,660 pasted against 901 dispatched is 17.4x.
    assert round(15660 / 901, 1) == 17.4, round(15660 / 901, 1)


def _drafts_with_dossiers() -> list:
    """Every draft under CONTENT_DIR that has a dossier directory."""
    pairs = []
    drafts_root = config.CONTENT_DIR / "drafts"
    for draft in sorted(drafts_root.rglob("*.md")):
        dossier = config.CONTENT_DIR / "dossiers" / draft.relative_to(drafts_root).with_suffix("")
        if dossier.is_dir():
            pairs.append((draft, dossier))
    return pairs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="names the results directory")
    args = parser.parse_args(argv)
    self_check()

    pairs = _drafts_with_dossiers()
    if not pairs:
        raise SystemExit(
            f"No draft under {config.CONTENT_DIR / 'drafts'} has a dossier. "
            "This measures real drafting material and fabricates none."
        )

    rewrite = [rewrite_arm(draft) for draft, _dossier in pairs]
    print(f"\n{'draft':58} {'words':>6} {'whole':>7} {'median':>7} {'ratio':>6}")
    for row in rewrite:
        print(
            f"{row['draft'][-58:]:58} {row['words']:>6} {row['whole_file_tokens']:>7} "
            f"{row['median_section_tokens']:>7} {str(row['ratio_whole_to_median_section']):>6}"
        )

    dispatch = []
    print(f"\n{'draft':58} {'pasted':>8} {'lines':>7} {'ratio':>6}")
    for draft, dossier in pairs:
        row = dispatch_arm(draft, dossier)
        dispatch.append(row)
        print(
            f"{row['draft'][-58:]:58} {row['pasted_tokens']:>8} "
            f"{row['dispatch_tokens']:>7} {str(row['ratio']):>6}  {row['section_outcomes']}",
            flush=True,
        )

    totals = {
        "pasted_chars": sum(r["pasted_chars"] for r in dispatch),
        "dispatch_chars": sum(r["dispatch_chars"] for r in dispatch),
    }
    totals["ratio"] = (
        round(totals["pasted_chars"] / totals["dispatch_chars"], 2)
        if totals["dispatch_chars"]
        else None
    )
    print(
        f"\nacross {len(dispatch)} drafts: {totals['pasted_chars']} characters pasted "
        f"against {totals['dispatch_chars']} dispatched -- {totals['ratio']}x"
    )

    out_dir = REPO / "bench" / "results" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "chars_per_token": CHARS_PER_TOKEN,
        "rewrite": rewrite,
        "dispatch": dispatch,
        "dispatch_totals": totals,
    }
    (out_dir / "prompt_economics.json").write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"\nwrote {out_dir / 'prompt_economics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
