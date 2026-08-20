"""The human's own topic list, and the reader for what it matched.

Two halves of one idea, kept in one stdlib-only module so that neither
needs the venv:

- `load()` parses `content/seed_topics.toml`, the hand-authored list of
  phrases an author wants the corpus organised by.
- `report()` formats `content/topic_seeds.json`, which
  `chitragupta/enrich/topic_seeding.py` writes by matching those phrases
  against the corpus.

**A seed topic is a phrase, and a phrase is never split.** "structural
health monitoring" is one topic, not three, and nothing here or
downstream tokenises it -- that is the whole reason the matching half
embeds a phrase whole (chitragupta/enrich/topic_seeding.py) rather than
looking it up in a bag-of-words vocabulary, where a multi-word seed
silently decomposes into unigrams that no longer mean what the author
wrote. The parsing side's contribution to that guarantee is small but
real: a TOML array element is an atomic string, so there is no separator
to get this wrong at, and `_clean()` below normalises whitespace without
ever splitting on it.

TOML rather than JSON, for the one reason that decides it: this file is
written by a person, and a person curating a seed list wants to record
*why* a phrase is on it -- which reads as a comment, and JSON has no
comments. It also follows what this repository already does, where TOML
is the format of every hand-edited file (`config.toml`,
`content/acronyms.toml`) and JSON is reserved for artefacts a program
wrote (`content/topics.json`, and `topic_seeds.json` here). The seed list
is the first kind; the match report is the second.

Why the *reader* lives at tier 1, with no venv and no import from
`chitragupta/enrich/`: matching needs a GPU, an embedding model and the
enrich Poetry group, but reading back what it decided needs none of
those, and an author browsing topics to plan a draft is doing the second
thing. This is the same split #204 made for Zotero collections, where
`ledger --collections` reads without the venv what only a real sync can
write.
"""

import argparse
import json
import tomllib
from pathlib import Path

from chitragupta import config
from chitragupta.progname import prog_for

DESCRIPTION = "Show which corpus papers each hand-authored seed topic matched."

# No `if __name__ == "__main__"` block, deliberately, and the same
# omission chitragupta/ledger.py makes: this module is reached through
# `chitragupta.corpus topics`, and docs/ARCHITECTURE.md keeps one entry
# point per layer. `python -m chitragupta.seed_topics` therefore imports
# this file and exits 0 without doing anything, which
# tests/test_corpus_entrypoint.py pins as the accepted trap.

# The one table key content/seed_topics.toml is read for. A fixed name
# rather than a config key: this file exists to be the seed list, so a
# second level of indirection over what to call its only array would be
# configuration for its own sake.
TOPICS_KEY = "topics"


class SeedTopicsError(RuntimeError):
    """`content/seed_topics.toml` exists but cannot be read as a seed list.

    Raised rather than skipped past. A malformed seed file is a typo in
    something the author wrote by hand and expects to be in force; a run
    that silently fell back to "no seeds" would produce a topic model
    that looks finished and quietly ignores every phrase they asked for.
    A missing file is a different case entirely and is not an error --
    see `load()`.
    """


def _clean(raw: str) -> str:
    """One phrase, with its internal whitespace normalised.

    `" digital   twin "` and `"digital twin"` are the same seed and must
    not produce two entries in the report. Note what this deliberately
    does *not* do: `split()`/`join()` here collapses runs of whitespace
    inside one already-atomic string, and never breaks that string into
    several -- the return type is `str`, not a list, and the phrase
    survives whole.
    """
    return " ".join(raw.split())


def load(path: "Path | None" = None) -> tuple[str, ...]:
    """The author's seed phrases, in the order they wrote them.

    An absent file returns `()`, which every caller treats as "no
    seeding" and which leaves the topic model exactly as it behaves
    today. That is the common case, not a degraded one: most libraries
    have no seed file, the same way most have no Zotero collections
    (docs/ZOTERO.md), and the stage must be unchanged for them rather
    than merely tolerant of them.

    Duplicates are dropped case-insensitively while preserving the first
    spelling, matching what chitragupta/bib_collections.py does for
    collection paths: two entries differing only in case are one topic
    the author wrote twice, and reporting it twice would double-count
    every paper under it.
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
                f"{seed_path}: '{TOPICS_KEY}[{index}]' must be a string, "
                f"got {type(entry).__name__}"
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
    """`content/topic_seeds.json` as written, or `{}` if the stage
    has not run. The empty dict is what `report()` turns into the "run
    the stage first" message, so a caller never has to distinguish
    "no file" from "no matches" itself."""
    report_path = config.TOPIC_SEEDS_PATH if path is None else Path(path)
    if not report_path.exists():
        return {}
    return json.loads(report_path.read_text(encoding="utf-8"))


def report(data: dict, phrase: "str | None" = None) -> str:
    """The match report as lines a person reads.

    Papers are listed under every phrase they matched, not just their
    best one -- the report is a view of a many-to-many relation and
    flattening it to one topic per paper would throw away the fact the
    author's own Zotero collections already assert, that a paper about
    digital twins in manufacturing belongs under both.
    """
    if not data:
        return ("No seed-topic matches recorded yet. Write "
                f"{config.SEED_TOPICS_PATH} and run "
                f"`{prog_for('enrich')} --stages seed-topics`.")

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
        lines.append(f"{topic['phrase']}  ({len(matches)} papers)")
        for match in matches:
            lines.append(f"    {match['score']:.3f}  {match['citekey']}")
        lines.append("")

    # Only when showing everything: a per-phrase view is a question about
    # one topic, and answering it with a corpus-wide coverage figure the
    # caller did not ask for buries the answer.
    if phrase is None:
        unmatched = data.get("unmatched", [])
        lines.append(f"{data.get('n_docs', 0)} documents, "
                     f"{len(topics)} seed topics, "
                     f"{len(unmatched)} documents matched no topic.")
        # The unmatched list is the point of the whole report for an
        # author deciding what to seed next: it is precisely the part of
        # their own corpus their own topic list does not describe.
        if unmatched:
            lines.append("Matched no topic: " + ", ".join(unmatched))
    return "\n".join(lines).rstrip()


def build_parser():
    parser = argparse.ArgumentParser(prog=f"{prog_for('corpus')} topics",
                                     description=DESCRIPTION)
    parser.add_argument(
        "--topic", metavar="PHRASE",
        help="show only this seed topic's papers, instead of every topic",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    data = load_report()
    print(report(data, args.topic))
    # 1 for "asked about something that isn't there", matching what
    # `ledger` already returns for a citekey it doesn't hold -- an
    # unwritten report and an unknown phrase are both that, and a script
    # checking the exit code should not have to parse prose to tell.
    if not data:
        return 1
    if args.topic is not None and not any(
        t["phrase"].casefold() == _clean(args.topic).casefold()
        for t in data.get("topics", [])
    ):
        return 1
    return 0
