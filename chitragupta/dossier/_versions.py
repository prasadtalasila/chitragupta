"""Numbered snapshots of a draft, kept in its dossier, for `draft diff`.

`content/` is outside git on purpose, so nothing else holds the text a
draft had before a revision pass. A snapshot is that text byte for byte,
plus both forms of every figure the draft names, laid out the way the
draft's own directory is -- `versions/001/survey.md`,
`versions/001/figures/x.tex` -- so the render path reads a snapshot
exactly as it reads the live draft.

The directory name is the identifier: a running three-digit number, and
for a snapshot an author asked for by name, a slug of that name after a
hyphen (`002-sent-to-supervisor`). Labels may not be all digits, so a
`--against 3` can only ever mean the number.

Each version is written into a hidden sibling and renamed into place, so
a crash leaves a `.tmp-*` directory `list_versions` never reads rather
than a version missing half its figures.
"""

import argparse
import json
import re
import shutil
import sys
import tempfile
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from chitragupta import config
from chitragupta.dossier import dossier_dir, draft_relpath
from chitragupta.render_output._figures import (
    _FIGURE_MARKER_MD_RE,
    _FIGURE_MARKER_TEX_RE,
    _INPUT_WITH_MARKER_RE,
    _resolve_sibling,
)
from chitragupta.render_output._paths import _MARKDOWN_SUFFIXES

VERSIONS_DIR = "versions"

SNAPSHOT_JSON = "snapshot.json"

MARK_REVISION = "mark-revision"
MANUAL = "manual"
TRIGGERS = (MARK_REVISION, MANUAL)

# The two files a figure marker names, in the order the figure-drawer
# writes them.
_FIGURE_FORMS = (".tex", ".txt")

# Three digits or more, so the thousandth snapshot is still a version
# rather than a directory nothing reads.
_VERSION_DIR_RE = re.compile(r"^(\d{3,})(?:-|$)")


class VersionError(ValueError):
    """A snapshot that cannot be taken or found; `str()` is the user-facing message."""


@dataclass(frozen=True)
class Snapshot:
    """One version of a draft, as its `snapshot.json` records it."""

    number: int
    label: str
    taken_at: str
    trigger: str
    revision_label: str
    fingerprint: str
    draft_name: str
    # Where the version sits, which is not written into the manifest: an
    # absolute path would not survive `dossier export` to another machine.
    path: Path = field(compare=False)

    @property
    def source(self) -> Path:
        """The draft's text as it was when this snapshot was taken."""
        return self.path / self.draft_name

    @property
    def ref(self) -> str:
        """The number as a directory name spells it, and as `--against` accepts it."""
        return f"{self.number:03d}"


def label_slug(label: str) -> str:
    """`label` as a directory-name suffix: ASCII, lowercase, hyphen-separated."""
    folded = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


def figure_names(text: str, suffix: str) -> list[str]:
    """Every figure `text` names, as its marker spells it (`figures/<base>`).

    A Markdown draft names a figure once, in a `<!-- figure: -->` marker.
    A `.tex` fragment names it twice, in the `\\input` of its TikZ form and
    the `%figure:` comment naming the ASCII one; both are read, since a
    fragment with only one of the two still has that figure.
    """
    if suffix in _MARKDOWN_SUFFIXES:
        names = _FIGURE_MARKER_MD_RE.findall(text)
    else:
        inputs = [ref.removesuffix(".tex") for ref, _ in _INPUT_WITH_MARKER_RE.findall(text)]
        names = inputs + _FIGURE_MARKER_TEX_RE.findall(text)
    return list(dict.fromkeys(names))


def _read(version_dir: Path) -> Snapshot:
    try:
        data = json.loads((version_dir / SNAPSHOT_JSON).read_text(encoding="utf-8"))
        return Snapshot(**data, path=version_dir)
    except (ValueError, TypeError) as error:
        raise VersionError(
            f"{version_dir / SNAPSHOT_JSON} is not a snapshot manifest: {error}"
        ) from error


def _numbered_dirs(draft: Path) -> list[tuple[int, Path]]:
    root = dossier_dir(draft) / VERSIONS_DIR
    if not root.is_dir():
        return []
    found = []
    for child in root.iterdir():
        match = _VERSION_DIR_RE.match(child.name)
        if match and child.is_dir():
            found.append((int(match.group(1)), child))
    return sorted(found)


def list_versions(draft: Path) -> list[Snapshot]:
    """Every snapshot of `draft`, oldest first."""
    return [_read(path) for _, path in _numbered_dirs(draft) if (path / SNAPSHOT_JSON).is_file()]


def latest(draft: Path) -> Snapshot | None:
    """The newest snapshot of `draft`, or None if it has none."""
    versions = list_versions(draft)
    return versions[-1] if versions else None


def _checked_slug(label: str, versions: list[Snapshot]) -> str:
    slug = label_slug(label)
    if not slug:
        raise VersionError(
            f"A named snapshot needs a label with letters or digits in it; {label!r} has none."
        )
    if slug.isdigit():
        raise VersionError(
            f"The label {label!r} is all digits, which `--against` would read as a "
            "version number. Give it a word."
        )
    for snap in versions:
        if snap.label and label_slug(snap.label) == slug:
            raise VersionError(f"{snap.path.name} already has the label {snap.label!r}.")
    return slug


def _write(draft: Path, text: bytes, snap: Snapshot, staging: Path) -> None:
    (staging / snap.draft_name).write_bytes(text)
    for name in figure_names(text.decode("utf-8"), draft.suffix):
        for form in _FIGURE_FORMS:
            ref = f"{name}{form}"
            figure = _resolve_sibling(draft.parent, ref)
            # A figure named but not yet drawn has nothing to keep; the
            # draft's own checks are what report it missing.
            if figure is not None:
                (staging / ref).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(figure, staging / ref)
    manifest = {key: value for key, value in asdict(snap).items() if key != "path"}
    (staging / SNAPSHOT_JSON).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def take(
    draft: Path, *, trigger: str, label: str = "", revision_label: str = ""
) -> Snapshot | None:
    """Snapshot `draft` as its next numbered version.

    `trigger="mark-revision"` is the automatic one: it carries no label,
    and is skipped (None) when the draft is unchanged since the latest
    snapshot, since a second copy of the same text compares as nothing.
    `trigger="manual"` is a milestone the author named, always taken.
    """
    # Deferred for `_draft_fingerprint.stamp`'s reason: `chitragupta.spec`
    # imports from this package, which re-exports this module.
    from chitragupta.spec import digest

    if trigger not in TRIGGERS:
        raise VersionError(f"Unknown snapshot trigger {trigger!r}; expected one of {TRIGGERS}.")
    if trigger == MARK_REVISION and label:
        raise VersionError(
            "An automatic snapshot is numbered only; pass the label as revision_label."
        )
    text = draft.read_bytes()
    fingerprint = digest(text.decode("utf-8"))
    versions = list_versions(draft)
    slug = _checked_slug(label, versions) if trigger == MANUAL else ""
    if trigger == MARK_REVISION and versions and versions[-1].fingerprint == fingerprint:
        return None
    numbered = _numbered_dirs(draft)
    number = numbered[-1][0] + 1 if numbered else 1
    name = f"{number:03d}-{slug}" if slug else f"{number:03d}"
    root = dossier_dir(draft) / VERSIONS_DIR
    snap = Snapshot(
        number=number,
        label=label,
        taken_at=datetime.now().isoformat(timespec="seconds"),
        trigger=trigger,
        revision_label=revision_label,
        fingerprint=fingerprint,
        draft_name=draft.name,
        path=root / name,
    )
    root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".tmp-", dir=root))
    try:
        _write(draft, text, snap, staging)
        staging.rename(snap.path)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return snap


def _no_versions(draft: Path) -> VersionError:
    return VersionError(
        f"{draft.name} has no snapshots yet. One is taken by every `dossier mark-revision`; "
        "until then, compare against a file with `--against <file>`."
    )


def resolve(draft: Path, ref: str | None) -> Snapshot:
    """The snapshot `ref` names: a number (`2`, `002`), a label, or None for the latest."""
    versions = list_versions(draft)
    if not versions:
        raise _no_versions(draft)
    if ref is None:
        return versions[-1]
    wanted = ref.strip()
    is_number = wanted.isascii() and wanted.isdigit()
    for snap in versions:
        if is_number and int(wanted) == snap.number:
            return snap
        if not is_number and snap.label and label_slug(snap.label) == label_slug(wanted):
            return snap
    held = ", ".join(snap.path.name for snap in versions)
    raise VersionError(f"{draft.name} has no version {ref!r}. It has: {held}.")


def versions_summary(draft: Path) -> str:
    """`dossier status`'s one line: how many versions, and the latest."""
    try:
        versions = list_versions(draft)
    except VersionError as error:
        # `status` is what a person runs to find out what is wrong, so it
        # reports a broken manifest rather than failing on it.
        return f"Versions: unreadable -- {error}"
    if not versions:
        return "Versions: none yet"
    newest = versions[-1]
    return f"Versions: {len(versions)}, latest {newest.ref} ({newest.taken_at[:10]})"


def _cmd_snapshot(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    if not draft.is_file():
        print(f"[error] No such draft: {args.draft}", file=sys.stderr)
        return 1
    snap = take(draft, trigger=MANUAL, label=args.label)
    print(f"Snapshot {snap.path.name} of {draft_relpath(draft)}")
    return 0


def _as_json(snap: Snapshot) -> dict:
    entry = asdict(snap)
    entry["path"] = snap.path.resolve().relative_to(config.CONTENT_DIR.resolve()).as_posix()
    return entry


def _cmd_versions(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    versions = list_versions(draft)
    if args.json:
        print(json.dumps([_as_json(snap) for snap in versions], indent=2))
        return 0
    if not versions:
        print(f"{draft.name} has no snapshots yet; `dossier mark-revision` takes the first.")
        return 0
    for snap in versions:
        about = snap.label or (f'"{snap.revision_label}"' if snap.revision_label else "")
        print(f"{snap.ref}  {snap.taken_at[:10]}  {snap.trigger:<13}  {about}".rstrip())
    return 0
