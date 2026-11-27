"""The human's own topic list, and the reader for what it matched.

`load()` parses the hand-authored `content/seed_topics.toml`; `report()`
formats `content/topic_seeds.json`, which `enrich/topic_seeding.py`
writes. Stdlib-only, so reading back needs no venv, GPU or model (the
split #204 made for collections).

A seed topic is a phrase and is never split: the matcher embeds it whole,
since a bag-of-words lookup would decompose it. TOML because a person
writes this file and wants comments, as for every hand-edited file here;
JSON is for program-written artefacts.
"""

import argparse
import json
import tomllib
from pathlib import Path

from chitragupta import config
from chitragupta.progname import prog_for
from chitragupta.help_format import ClickParser

DESCRIPTION = "Show which corpus papers each hand-authored seed topic matched."

# No `__main__` block: reached through `chitragupta.corpus topics`, one
# entry point per layer (docs/ARCHITECTURE.md); tests/test_corpus_entrypoint.py
# pins the silent no-op.
TOPICS_KEY = "topics"


class SeedTopicsError(RuntimeError):
    """`content/seed_topics.toml` exists but cannot be read as a seed list.

    Raised, not skipped: falling back to "no seeds" would produce a
    finished-looking topic model ignoring every phrase the author asked
    for. A missing file is not an error (see `load()`).
    """


def _clean(raw: str) -> str:
    """One phrase, with its internal whitespace normalised; never split."""
    return " ".join(raw.split())


def load(path: "Path | None" = None) -> tuple[str, ...]:
    """The author's seed phrases, in the order they wrote them.

    An absent file returns `()`, leaving the topic model unchanged; that
    is the common case. Duplicates drop case-insensitively, keeping the
    first spelling (as `bib_collections.py` does), so no paper is counted
    twice.
    """
    seed_path = config.SEED_TOPICS_PATH if path is None else Path(path)
    if not seed_path.exists():
        return ()
    try:
        with open(seed_path, "rb") as handle:
            parsed = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        raise SeedTopicsError(f"{seed_path} could not be parsed as TOML: {exc}") from exc

    raw_topics = parsed.get(TOPICS_KEY, [])
    if not isinstance(raw_topics, list):
        raise SeedTopicsError(
            f"{seed_path}: '{TOPICS_KEY}' must be an array of strings, "
            f"got {type(raw_topics).__name__}"
        )

    topics: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw_topics):
        if not isinstance(entry, str):
            raise SeedTopicsError(
                f"{seed_path}: '{TOPICS_KEY}[{index}]' must be a string, got {type(entry).__name__}"
            )
        phrase = _clean(entry)
        if not phrase:
            raise SeedTopicsError(
                f"{seed_path}: '{TOPICS_KEY}[{index}]' is empty, which cannot match anything"
            )
        if phrase.casefold() in seen:
            continue
        seen.add(phrase.casefold())
        topics.append(phrase)
    return tuple(topics)


def load_report(path: "Path | None" = None) -> dict:
    """`content/topic_seeds.json` as written, or `{}` if the stage has not
    run, which `report()` turns into a "run the stage first" message."""
    report_path = config.TOPIC_SEEDS_PATH if path is None else Path(path)
    if not report_path.exists():
        return {}
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # A truncated write gets the same clean refusal as any other
        # malformed file, not a raw JSONDecodeError (#504, m-32).
        raise SeedTopicsError(f"{report_path} is not valid JSON: {exc}") from exc


def report(data: dict, phrase: "str | None" = None) -> str:
    """The match report as lines a person reads. A paper is listed under
    every phrase it matched: the relation is many-to-many.
    """
    if not data:
        return (
            "No seed-topic matches recorded yet. Write "
            f"{config.SEED_TOPICS_PATH} and run "
            f"`{prog_for('enrich')} --stages seed-topics`."
        )

    topics = data.get("topics", [])
    if phrase is not None:
        wanted = _clean(phrase).casefold()
        topics = [t for t in topics if t["phrase"].casefold() == wanted]
        if not topics:
            known = ", ".join(t["phrase"] for t in data.get("topics", [])) or "none"
            return f"No seed topic named {phrase!r}. Recorded topics: {known}"

    lines = []
    for topic in topics:
        matches = topic["matches"]
        # "25 of 240": a truncated list must not read as a complete one,
        # since only it calls for raising [enrich].seed_topic_max_papers.
        considered = topic.get("considered", len(matches))
        shown = (
            f"{len(matches)} of {considered} papers"
            if considered > len(matches)
            else f"{len(matches)} papers"
        )
        lines.append(f"{topic['phrase']}  ({shown})")
        for match in matches:
            lines.append(f"    {match['score']:.3f}  {match['citekey']}")
        lines.append("")

    # Only when showing everything: a per-phrase view did not ask for
    # corpus-wide coverage.
    if phrase is None:
        unmatched = data.get("unmatched", [])
        lines.append(
            f"{data.get('n_docs', 0)} documents, "
            f"{len(topics)} seed topics, "
            f"{len(unmatched)} documents matched no topic."
        )
        # The unmatched list is what tells an author what to seed next.
        if unmatched:
            lines.append("Matched no topic: " + ", ".join(unmatched))
    return "\n".join(lines).rstrip()


def build_parser() -> argparse.ArgumentParser:
    parser = ClickParser(prog=f"{prog_for('corpus')} topics", description=DESCRIPTION)
    parser.add_argument(
        "--topic",
        metavar="PHRASE",
        help="show only this seed topic's papers, instead of every topic",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    data = load_report()
    print(report(data, args.topic))
    # 1 for "asked about something that isn't there", as `ledger` returns
    # for an unknown citekey, so scripts need not parse prose.
    if not data:
        return 1
    if args.topic is not None and not any(
        t["phrase"].casefold() == _clean(args.topic).casefold() for t in data.get("topics", [])
    ):
        return 1
    return 0
