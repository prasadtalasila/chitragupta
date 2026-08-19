"""`dossier export`/`restore`: bundling a set of dossiers (and
optionally their renders) into one tar.gz, and unpacking one back.

Split out of chitragupta/dossier.py (#219).
"""

import argparse
import sys
import tarfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath

from chitragupta import config, review
from chitragupta.dossier import DossierError, draft_relpath

# Top-level directories a bundle may contain, and the only ones `restore`
# will unpack. A whitelist rather than a blocklist: an archive member
# naming anything else is refused outright, so a hand-edited or
# hostile tarball cannot write outside the directories this module owns.
#
# Every root `bundle_members` can emit has to be here, or `export` and
# `restore` stop being a round trip -- and because `_checked_members`
# refuses the *whole* archive rather than skipping a member, the failure
# would be a bundle that cannot be restored at all rather than one
# missing a file.
ARCHIVE_ROOTS = ("drafts", "dossiers", "rendered", "review")


def _matches(relative: PurePosixPath, names: list[str]) -> bool:
    if not names:
        return True
    text = relative.as_posix()
    stem = relative.with_suffix("").as_posix()
    return any(
        text == name or stem == name or text.startswith(f"{name}/") for name in names
    )


def _strip_aid_suffix(relative: PurePosixPath) -> PurePosixPath:
    """`survey.provenance.md` -> `survey`, for matching a review report
    against the draft it belongs to.

    Drops the format suffix, then the aid suffix -- and only if it really
    is one of `review.AIDS`, so a draft named `survey.v2.md` keeps its
    `.v2` and its reports go on matching `topic/survey.v2`.
    """
    stem = relative.with_suffix("")
    if stem.suffix.lstrip(".") in review.AIDS:
        return stem.with_suffix("")
    return stem


def bundle_members(names: list[str], with_rendered: bool) -> list[tuple[Path, str]]:
    """(file on disk, name inside the archive) for everything to back up.

    Archive names are relative to `content/`, not to the repo root, so a
    bundle restores correctly into a checkout whose `[content].dir`
    points somewhere else.

    `content/review/` is included by default, filtered to the `.md`
    reports and the `.json` payloads beside them. That is the line
    `--with-rendered` already draws -- it exists to gate PDFs, not text
    -- and a bundle that dropped the review reports would quietly falsify
    the property they were given a mirrored path for, namely that a
    draft's evidence is findable from the draft. The same holds for the
    payload: it is that evidence as data, and leaving it out of the
    bundle would mean a restored draft's findings were readable by a
    person and not by the tools written to consume them (#127). Their
    `.tex`/`.pdf` renders sit in the same tree and are gated with
    everything else heavy.
    """
    roots = [("drafts", config.DRAFTS_DIR), ("dossiers", config.DOSSIERS_DIR),
             ("review", config.REVIEW_DIR)]
    if with_rendered:
        roots.append(("rendered", config.RENDERED_DIR))

    members: list[tuple[Path, str]] = []
    for label, root in roots:
        if root.is_dir():
            members.extend(_root_members(label, root, names, with_rendered))
    return members


def _root_members(label: str, root: Path, names: list[str],
                  with_rendered: bool) -> list[tuple[Path, str]]:
    """The (file, archive name) pairs one content root contributes."""
    members = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if (label == "review" and not with_rendered
                and path.suffix.lower() not in (".md", ".json")):
            continue
        relative = PurePosixPath(path.relative_to(root).as_posix())
        if _matches(_match_target(label, relative), names):
            members.append((path, f"{label}/{relative.as_posix()}"))
    return members


def _match_target(label: str, relative: PurePosixPath) -> PurePosixPath:
    """What one archive member's path is matched against a draft name as.

    A dossier lives one directory deeper than its draft, so
    match its parent: `dossiers/topic/survey/scope.md` belongs
    to the draft named `topic/survey`. A review report mirrors
    the draft's path exactly, so it needs no such adjustment --
    but its own name carries the aid (`survey.provenance.md`),
    so strip exactly that before matching against a draft named
    `topic/survey`. Exactly that, not "two suffixes": a draft
    named `survey.v2.md` would otherwise have its reports
    double-stripped to `survey` and stop matching the draft.
    """
    if label == "dossiers":
        return relative.parent
    if label == "review":
        return _strip_aid_suffix(relative)
    return relative


def export(names: list[str], out: Path, with_rendered: bool = False) -> tuple[Path, int]:
    """Write a gzipped tar of the named drafts, their dossiers and their
    review reports (`.md`; the renders need `--with-rendered`)."""
    members = bundle_members(names, with_rendered)
    if not members:
        raise DossierError(
            "Nothing to export"
            + (f" matching {', '.join(names)}" if names else f" under {config.CONTENT_DIR}")
            + "."
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as archive:
        for path, name in members:
            archive.add(path, arcname=name)
    return out, len(members)


def _checked_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    """Every member, having refused the whole archive if any is unsafe.

    Refusing wholesale rather than skipping the bad member: a partially
    extracted backup is worse than none, because it looks like it worked.
    `extractall(filter="data")` below repeats the traversal checks -- this
    is not redundant, it is the layer that can say *which* member was
    wrong and that only the three directories this module owns are
    writable.
    """
    checked: list[tarfile.TarInfo] = []
    for member in archive.getmembers():
        if not (member.isfile() or member.isdir()):
            raise DossierError(
                f"{member.name!r} is not a regular file or directory "
                "(a link or device node). Refusing the whole archive."
            )
        name = PurePosixPath(member.name)
        if name.is_absolute() or ".." in name.parts:
            raise DossierError(
                f"{member.name!r} escapes the extraction directory. "
                "Refusing the whole archive."
            )
        if not name.parts or name.parts[0] not in ARCHIVE_ROOTS:
            raise DossierError(
                f"{member.name!r} is not under {'/, '.join(ARCHIVE_ROOTS)}/. "
                "Refusing the whole archive."
            )
        checked.append(member)
    return checked


@dataclass
class RestorePlan:
    archive: Path
    new: list[Path] = field(default_factory=list)
    overwrite: list[Path] = field(default_factory=list)
    performed: bool = False


def restore(archive: Path, force: bool = False) -> RestorePlan:
    """Unpack a bundle under `content/`. A dry run unless `force`.

    Reporting first is the default because restoring is the only
    destructive thing in this module, and the case it exists for --
    "I need last month's draft back" -- is exactly the case where the
    working copy might be something you'd rather not lose to a
    mistyped archive name.
    """
    plan = RestorePlan(archive=archive)
    with tarfile.open(archive, "r:gz") as tar:
        members = _checked_members(tar)
        for member in members:
            if not member.isfile():
                continue
            target = config.CONTENT_DIR / member.name
            (plan.overwrite if target.exists() else plan.new).append(target)
        if force:
            config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
            tar.extractall(config.CONTENT_DIR, members=members, filter="data")
            plan.performed = True
    return plan


def _cmd_export(args: argparse.Namespace) -> int:
    if args.out:
        out = Path(args.out)
    else:
        label = "-".join(name.replace("/", "-") for name in args.names) or "all"
        out = Path(f"drafts-{label}-{date.today().isoformat()}.tar.gz")
    try:
        written, count = export(args.names, out, args.with_rendered)
    except DossierError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    size = written.stat().st_size
    print(f"  {written}  ({count} file(s), {size / 1024:.1f} KiB)")
    print("\n  Restore with:")
    print(f"    python -m chitragupta.draft dossier restore {written} --force")
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    archive = Path(args.archive)
    if not archive.is_file():
        print(f"No such archive: {archive}", file=sys.stderr)
        return 1
    try:
        plan = restore(archive, args.force)
    except (DossierError, tarfile.TarError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    verb = "Restored" if plan.performed else "Would restore"
    print(f"{verb} into {draft_relpath(config.CONTENT_DIR)}:")
    print(f"  {len(plan.new)} new file(s)")
    print(f"  {len(plan.overwrite)} existing file(s) "
          f"{'overwritten' if plan.performed else 'would be OVERWRITTEN'}")
    for path in plan.overwrite[:10]:
        print(f"    {draft_relpath(path)}")
    if len(plan.overwrite) > 10:
        print(f"    ... and {len(plan.overwrite) - 10} more")
    if not plan.performed:
        print("\n  Dry run. Re-run with --force to write:")
        print(f"    python -m chitragupta.draft dossier restore {archive} --force")
    return 0
