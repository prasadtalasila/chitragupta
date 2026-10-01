#!/usr/bin/env bash
# The vendored Vale style parses, and its quoted-span exemptions hold.
#
# Not a lint of this repository's own prose, which would fail today:
# docs/ carries 27 uses of §2's markers, and DEVELOPER-AGENTS.md's rule
# is that a check which has not been made to pass must not ship. This
# runs the vendored style over a fixture instead, so a BlockIgnores regex
# that Vale refuses to parse -- a comma inside `\n{2,}` is the way that
# happens -- fails CI rather than silently reporting zero findings on
# every draft forever.
#
# `style` exits 0 by design -- it is a review aid, not a gate -- so this
# reads the findings rather than the exit code. Every marker in the
# fixtures sits inside an exemption, so anything reported means an
# exemption broke.
#
# A file rather than an inline `run: |` block in ci.yml (#865), so that
# scripts/check_local.sh can run the same text CI does rather than a copy
# of it. PYTHON defaults to `python`, which is what ci.yml's setup-python
# provides; point it at your venv's interpreter locally if `python` is
# not the one with this package's dependencies.

set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"
report="$(mktemp)"
trap 'rm -f "$report"' EXIT

"$PYTHON" -m chitragupta.draft style --json \
    tests/fixtures/style/exemptions.md \
    tests/fixtures/style/exemptions.tex > "$report"

"$PYTHON" - "$report" <<'CHECK'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    payload = json.load(f)
bad = [(d["draft"], d["findings"]) for d in payload["drafts"] if d["findings"]]
if payload["warnings"]:
    sys.exit(f"style check could not run: {payload['warnings']}")
if bad:
    sys.exit(f"a quoted-span exemption has broken: {bad}")
print("exemptions hold: 0 findings in", len(payload["drafts"]), "fixtures")
CHECK
