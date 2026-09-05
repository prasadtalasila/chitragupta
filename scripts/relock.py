#!/usr/bin/env python3
"""Regenerate `poetry.lock` from nothing, by letting `uv` do the search.

`poetry lock --regenerate` does not finish on this dependency set. That
is measured, not folklore: over 600 seconds before being killed, and 22
hours on one attempt with a wider Python range, with the CPU pegged and
nothing being downloaded -- backtracking inside the resolver, not a slow
index. `docs/UV-MIGRATION.md` has the profile and the numbers.

This script is the way around it that was found by hand and is worth
keeping. `uv` resolves the same graph in under two seconds; it cannot
write a `poetry.lock`, because that format is Poetry's own, but its
*answer* removes Poetry's search:

    1. `uv pip compile` the declared constraints            (~2s)
    2. write those exact versions back as temporary `==` pins
    3. `poetry lock` -- nothing left to search              (~90s)
    4. restore the original pyproject.toml
    5. `poetry lock` again, now with a lock to start from   (~40s)

Step 5 matters and is not decoration: step 3's lock is correct but was
produced from pins, so its `content-hash` belongs to a pyproject.toml
that is about to be thrown away. Step 5 re-locks against the real file,
keeping the versions step 3 found because a lock is already present.

**You should rarely need this.** Adding, removing or bumping a single
dependency is a normal `poetry lock` / `poetry update --lock <pkg>` and
takes about 40 seconds -- see the table in `pyproject.toml`. This is for
the case where there is no usable lock at all.

Usage:

    python3 scripts/relock.py             # regenerate poetry.lock
    python3 scripts/relock.py --check     # resolve and report, write nothing

Exits non-zero if any step fails, leaving pyproject.toml as it found it.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
LOCK = REPO_ROOT / "poetry.lock"


def _run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, streaming nothing, returning the result.

    check=False everywhere: every call site reports its own failure with
    the context of which step failed, which a raised CalledProcessError
    traceback would bury.
    """
    return subprocess.run(
        command, cwd=REPO_ROOT, capture_output=True, text=True, check=False, **kwargs
    )


def _tool(name: str) -> str:
    """Absolute path to a required tool, or exit saying how to get it."""
    found = shutil.which(name)
    if found is None:
        hint = {
            "uv": "pip install uv (or see https://docs.astral.sh/uv/)",
            "poetry": "bash scripts/install_full_pipeline.sh os-deps",
        }[name]
        sys.exit(f"relock: {name} not found on PATH. Install it: {hint}")
    return found


def _declared_requirements() -> list[str]:
    """Every declared dependency as a PEP 508 requirement string.

    Read from pyproject.toml rather than restated here, so a dependency
    added to the project cannot be silently missed by the resolution
    this script feeds to uv. `python` is skipped -- it is the
    interpreter constraint, not a package.
    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    poetry = data["tool"]["poetry"]
    tables = [poetry.get("dependencies", {})]
    tables += [group.get("dependencies", {}) for group in poetry.get("group", {}).values()]

    requirements: dict[str, str] = {}
    for table in tables:
        for name, spec in table.items():
            if name == "python":
                continue
            version = spec["version"] if isinstance(spec, dict) else spec
            requirements[name] = f"{name}{_pep508(name, version)}"
    return sorted(requirements.values())


def _pep508(name: str, version: str) -> str:
    """Poetry's version syntax as something uv will accept.

    Only the forms this project actually uses are translated, and an
    unrecognised one stops the run rather than being guessed at: a
    mistranslated constraint would resolve to a *plausible* wrong
    version and land in the lock silently, which is worse than a refusal.

    `"0.1.5"` -- Poetry's bare exact pin, which mkdocs-same-dir uses --
    is the one that bites: passed through unchanged it produces
    `mkdocs-same-dir0.1.5`, which uv reports as a package that does not
    exist rather than as a malformed specifier.
    """
    version = version.strip()
    if version == "*":
        return ""
    if version[0].isdigit():
        return f"=={version}"
    if version[0] in "><=!~":
        return version
    sys.exit(
        f"relock: {name} declares `{version}`, a version form this script does "
        f"not translate (caret/tilde). Add it to _pep508 rather than guessing."
    )


def _resolve_with_uv(uv: str, requirements: list[str]) -> dict[str, str]:
    """uv's answer: {package: version}, resolved for the lowest Python
    this project supports.

    The lowest, deliberately. A lock has to install across the whole
    declared range, and the floor is the end that rejects a wheel a
    newer interpreter would accept.
    """
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "requirements.in"
        source.write_text("\n".join(requirements) + "\n", encoding="utf-8")
        output = Path(tmp) / "requirements.txt"
        result = _run(
            [
                uv,
                "pip",
                "compile",
                "--quiet",
                "--python-version",
                "3.12",
                str(source),
                "-o",
                str(output),
            ]
        )
        if result.returncode != 0:
            sys.exit(f"relock: uv could not resolve the dependency set:\n{result.stderr}")
        pins: dict[str, str] = {}
        for line in output.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if "==" in line:
                name, _, version = line.partition("==")
                pins[name.strip()] = version.strip()
        return pins


def _pin(text: str, pins: dict[str, str]) -> str:
    """Rewrite every declared constraint to uv's exact version.

    Line-oriented on purpose: tomlkit would round-trip this file more
    correctly, but it is not a dependency of this project and the edit
    is thrown away three steps later. Only lines that already declare a
    dependency are touched, so the comments -- which carry most of this
    file's value -- survive untouched.
    """
    out = []
    for line in text.split("\n"):
        name = line.split(" = ", 1)[0].strip()
        pinned = pins.get(name.replace("_", "-"))
        if pinned and " = " in line and not line.startswith("#"):
            out.append(_pin_line(name, line, pinned))
            continue
        out.append(line)
    return "\n".join(out)


def _pin_line(name: str, line: str, pinned: str) -> str:
    """One declaration, rewritten to `pinned`, whatever shape it is in.

    Both shapes this file uses are handled by substituting the version
    *inside* the line rather than rebuilding it: an inline table can
    carry more than `optional` (`markers`, `python`, `source`), and
    reconstructing it from the name alone would drop whatever else was
    there.

    A declaration that matches a pinned package but has no recognisable
    version stops the run. Skipping it silently is the tempting
    alternative and the wrong one: the package would simply not be
    pinned, Poetry would search it again, and the script would appear to
    work while doing the one thing it exists to avoid.
    """
    inline = re.search(r'version = "[^"]*"', line)
    if inline:
        return line[: inline.start()] + f'version = "{pinned}"' + line[inline.end() :]
    value = line.split(" = ", 1)[1]
    if value.startswith('"'):
        return f'{name} = "{pinned}"'
    sys.exit(
        f"relock: cannot pin {name} -- its declaration `{line.strip()}` has no "
        f"version this script recognises. Pin it by hand or teach _pin_line the shape."
    )


def _poetry_lock(poetry: str, step: str) -> float:
    """One `poetry lock`, timed, exiting with its stderr if it fails."""
    started = time.monotonic()
    result = _run([poetry, "lock"])
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        sys.exit(f"relock: `poetry lock` failed during {step}:\n{result.stderr}")
    return elapsed


def _regenerate(poetry: str, pins: dict[str, str]) -> None:
    """The two-pass lock, restoring the tree on any failure.

    Split out of `main` for the C1 statement limit, and it earns the
    split anyway: this is the only part that edits tracked files, so the
    restore path is easier to check when it is not interleaved with
    argument parsing.
    """
    original = PYPROJECT.read_text(encoding="utf-8")
    previous_lock = LOCK.read_bytes() if LOCK.exists() else None
    try:
        PYPROJECT.write_text(_pin(original, pins), encoding="utf-8")
        LOCK.unlink(missing_ok=True)
        print(f"relock: locking against pins ... {_poetry_lock(poetry, 'the pinned pass'):.0f}s")
        PYPROJECT.write_text(original, encoding="utf-8")
        print(
            f"relock: re-locking against the real constraints ... "
            f"{_poetry_lock(poetry, 'the restoring pass'):.0f}s"
        )
    except BaseException:
        # Including KeyboardInterrupt: a half-pinned pyproject.toml left
        # behind by an interrupted run is the one outcome worth more
        # than the traceback, since it looks like a hand edit later.
        PYPROJECT.write_text(original, encoding="utf-8")
        if previous_lock is not None:
            LOCK.write_bytes(previous_lock)
        print("relock: restored pyproject.toml and poetry.lock", file=sys.stderr)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 scripts/relock.py",
        description="Regenerate poetry.lock using uv to do the resolution.",
    )
    parser.add_argument(
        "--check", action="store_true", help="Resolve and report the versions; write nothing."
    )
    args = parser.parse_args(argv)

    uv = _tool("uv")
    requirements = _declared_requirements()
    print(f"relock: {len(requirements)} declared dependencies, resolving with uv ...")

    started = time.monotonic()
    pins = _resolve_with_uv(uv, requirements)
    print(f"relock: uv resolved {len(pins)} packages in {time.monotonic() - started:.1f}s")

    if args.check:
        for name in sorted(n for n in pins if any(r.startswith(n) for r in requirements)):
            print(f"    {name}=={pins[name]}")
        return 0

    _regenerate(_tool("poetry"), pins)
    print("relock: done. Review `git diff poetry.lock` before committing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
