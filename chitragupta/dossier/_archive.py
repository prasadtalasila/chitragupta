"""`dossier export`/`restore`: bundling a set of dossiers (and
optionally their renders) into one tar.gz, and unpacking one back.
"""

import argparse
import sys
import tarfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath

from chitragupta import config, review
from chitragupta.dossier import DossierError, draft_relpath

# The only top-level directories `restore` unpacks: a whitelist, so a
# hostile tarball cannot write elsewhere. Every root `bundle_members`
# emits must be here, or the whole archive is refused on restore.
ARCHIVE_ROOTS = ("drafts", "dossiers", "rendered", "review")


def _matches(relative: PurePosixPath, names: list[str]) -> bool:
    if not names:
        return True
    text = relative.as_posix()
    stem = relative.with_suffix("").as_posix()
    return any(text == name or stem == name or text.startswith(f"{name}/") for name in names)


def _strip_aid_suffix(relative: PurePosixPath) -> PurePosixPath:
    """`survey.provenance.md` -> `survey`, for matching a review report
    against the draft it belongs to.

    Strips the aid suffix only if it is in `review.AIDS`, so a draft
    named `survey.v2.md` keeps its `.v2`.
    """
    stem = relative.with_suffix("")
    if stem.suffix.lstrip(".") in review.AIDS:
        return stem.with_suffix("")
    return stem


def _strip_sidecar_suffix(relative: PurePosixPath) -> PurePosixPath:
    """`survey.evidence.pdf` -> `survey`, for matching a draft's evidence
    sidecar against the draft it belongs to.

    Without it an export silently left out the draft's evidence. Exactly
    `.evidence`, for the `survey.v2` reason `_strip_aid_suffix` gives.
    """
    # Deferred: `chitragupta/evidence_appendix.py` imports this package,
    # so a module-level import is circular. Spelling "evidence" here
    # instead would let the writer, this matcher and .gitignore drift.
    from chitragupta import evidence_appendix

    stem = relative.with_suffix("")
    if stem.suffix.lstrip(".") == evidence_appendix.SUFFIX:
        return stem.with_suffix("")
    return relative


def bundle_members(names: list[str], with_rendered: bool) -> list[tuple[Path, str]]:
    """(file on disk, name inside the archive) for everything to back up.

    Names are relative to `content/`, so a bundle restores into a
    differently configured `[content].dir`. Review `.md` reports and
    `.json` payloads are included by default: a draft's evidence must be
    findable from it, by people and tools (#127); only heavy renders
    need `--with-rendered`.
    """
    roots = [
        ("drafts", config.DRAFTS_DIR),
        ("dossiers", config.DOSSIERS_DIR),
        ("review", config.REVIEW_DIR),
    ]
    if with_rendered:
        roots.append(("rendered", config.RENDERED_DIR))

    members: list[tuple[Path, str]] = []
    for label, root in roots:
        if root.is_dir():
            members.extend(_root_members(label, root, names, with_rendered))
    return members


def _root_members(
    label: str, root: Path, names: list[str], with_rendered: bool
) -> list[tuple[Path, str]]:
    members = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if label == "review" and not with_rendered and path.suffix.lower() not in (".md", ".json"):
            continue
        relative = PurePosixPath(path.relative_to(root).as_posix())
        if _matches(_match_target(label, relative), names):
            members.append((path, f"{label}/{relative.as_posix()}"))
    return members


def _match_target(label: str, relative: PurePosixPath) -> PurePosixPath:
    """What one archive member's path is matched against a draft name as.

    A dossier is one directory deeper than its draft, so match its
    parent. Reports and the evidence sidecar carry an extra suffix, so
    strip exactly that one (not "two suffixes", which breaks
    `survey.v2.md`). Other renders need no adjustment.
    """
    if label == "dossiers":
        return relative.parent
    if label == "review":
        return _strip_aid_suffix(relative)
    if label == "rendered":
        return _strip_sidecar_suffix(relative)
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

    Wholesale: a partially extracted backup looks like it worked.
    `extractall(filter="data")` repeats the traversal checks; this layer
    names *which* member was wrong and limits writes to our directories.
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
                f"{member.name!r} escapes the extraction directory. Refusing the whole archive."
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

    Restoring is this module's one destructive act, and its use case is
    where the working copy may be worth keeping.
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
    print(
        f"  {len(plan.overwrite)} existing file(s) "
        f"{'overwritten' if plan.performed else 'would be OVERWRITTEN'}"
    )
    for path in plan.overwrite[:10]:
        print(f"    {draft_relpath(path)}")
    if len(plan.overwrite) > 10:
        print(f"    ... and {len(plan.overwrite) - 10} more")
    if not plan.performed:
        print("\n  Dry run. Re-run with --force to write:")
        print(f"    python -m chitragupta.draft dossier restore {archive} --force")
    return 0
