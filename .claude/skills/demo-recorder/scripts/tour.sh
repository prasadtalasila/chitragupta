#!/usr/bin/env bash
# The demo's terminal half: a numbered tour of the CLI, run against a
# throwaway copy of docs/examples/sample-project, so `corpus sync` and
# `enrich` never rewrite the committed one. asciinema records it
# (SKILL.md, "Record"); run it bare first and read every step's output.
#
# Each step prints the installed form (`chitragupta ...`) and runs this
# checkout's own code (`$PY -m chitragupta.<layer>`, with the checkout on
# PYTHONPATH), so the recording shows this branch. The `# N. ...`
# headings are what retime_cast.py's --start/--end match, so keep them.
#
# Environment:
#   PY     interpreter to run (default: python3). Steps 5 and 31 need
#          the enrich extra; without it they print the remedy instead.
#   PAUSE  multiplies every pause (default: 1; 0 for a quick dry run).
set -uo pipefail
export PS1='$ '

REPO=$(cd "$(dirname "$0")" && git rev-parse --show-toplevel)
PY=${PY:-python3}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cp -R "$REPO/docs/examples/sample-project" "$WORK/"
cd "$WORK/sample-project" || exit 1
export PYTHONPATH="$REPO" CHITRAGUPTA_PROJECT=.

DRAFT=content/drafts/dt-overview/survey.md
BOOK=content/drafts/twin-basics

pause() { sleep "$(awk -v s="$1" -v k="${PAUSE:-1}" 'BEGIN { print s * k }')"; }
say() { printf '\n\033[1;36m# %s\033[0m\n' "$1"; pause 0.6; }

# show SECONDS LAYER ARGS...: print `$ chitragupta LAYER ARGS`, quoting
# an argument with a space the way someone would type it, run it, pause.
show() {
  local after=$1 layer=$2 shown="" arg
  shift 2
  for arg in "$@"; do
    if [[ $arg == *" "* ]]; then shown+=" \"$arg\""; else shown+=" $arg"; fi
  done
  printf '$ chitragupta %s%s\n' "$layer" "$shown"
  "$PY" -m "chitragupta.$layer" "$@"
  pause "$after"
}

clear 2>/dev/null
say "chitragupta -- an all-features tour"
pause 1

say "1. install (pip, dry-run against real PyPI)"
echo '$ pip install chitragupta-cli'
"$PY" -m pip install --dry-run --ignore-installed --no-deps chitragupta-cli 2>&1 | tail -20
pause 1

say "2. sync the corpus: bib file -> ledger -> parsed PDF text"
show 1.5 corpus sync

say "3. the ledger -- what sync found"
show 2 corpus ledger --list
show 1 corpus ledger --status parse_failed
show 1.5 corpus ledger --collections

say "4. named topics matched against the corpus"
show 2 corpus topics

say "5. enrich -- the optional whole-corpus layer the topic aids are built on"
show 1.5 enrich --stages embed

say "6. discover: what is this corpus actually about, unprompted?"
show 2.5 corpus discover "digital twin"

say "7. discover, one paper at a time -- which topics claim it, and how strongly"
show 2 corpus discover --paper sample_dt_overview_2024

say "8. why two topics are (or are not) linked -- evidence, with the null model stated"
show 2.5 corpus discover --why "digital twin" "anomaly detection"

say "9. compare topics -- who holds what, pairwise"
show 2.5 corpus discover --compare "digital twin" "interoperability standards"

say "10. the citation gate -- the one exit from drafting to a rendered document"
show 1.5 draft gate "$DRAFT"

say "11. references -- rebuild the References section from the citekeys actually used"
show 1.5 draft references "$DRAFT" --heading References

say "12. evidence -- the draft's citations as a standalone appendix"
show 1.5 draft evidence "$DRAFT"

say "13. retrieve evidence -- the same corpus search a drafting skill would run"
show 2 draft retrieve evidence synchronisation --citekey sample_dt_sync_2023

say "14. retrieve search -- search the whole corpus by hand"
show 2 draft retrieve search "digital twin composability" --k 5

say "15. dossier -- every draft's externalised working memory"
show 1.5 draft dossier list

say "16. dossier status -- has the corpus moved under a finished draft?"
show 2.5 draft dossier status --all

say "17. dossier sections -- the draft's own structure, as the aids see it"
show 2 draft dossier sections "$DRAFT"

say "18. style -- dialect and prose-style findings"
show 1.5 draft style "$DRAFT"

say "19. render -- a numbered Markdown copy, no pandoc needed"
show 1.5 draft render "$DRAFT" --format md

say "20. the book track: spec -- the outline a book is drafted against"
show 2 draft spec show "$BOOK"

say "21. spec status -- is that outline signed off, and at which digest?"
show 1.5 draft spec status "$BOOK"

say "22. unit -- which units are accepted and current"
show 1.5 draft unit status "$BOOK"

say "23. registry -- cross-unit consistency, evidence not verdict"
show 1.5 draft registry check "$BOOK"

say "24. registry excerpt -- what one unit may rely on the others having settled"
show 2 draft registry excerpt "$BOOK" ch-staleness

say "25. tldr -- a per-source one-liner, when one has been recorded"
show 1.5 draft tldr show sample_dt_overview_2024

say "26. figures -- per-source figure index, when the docling stage has run"
show 1.5 draft figures sample_dt_overview_2024

say "27. review agenda -- the advisory aids, merged into one ranked worklist"
show 3 review agenda "$DRAFT"

say "28. coverage -- citation coverage against a query"
show 2 review coverage "$DRAFT" --query "digital twin staleness"

say "29. figure -- checks any figures the draft embeds"
show 1.5 review figure "$DRAFT"

say "30. provenance -- where every citekey's claims actually trace to"
show 2 review provenance "$DRAFT"

say "31. support -- semantic support scoring (needs the enrich extra)"
show 1.5 review support "$DRAFT"

say "32. synthesis -- how many claims rest on just one source"
show 2 review synthesis "$DRAFT" --unit section

say "33. uncited -- claim-bearing prose with no citation, read against a genre"
show 2 review uncited "$DRAFT" --genre survey

say "34. quotation -- do the quoted passages actually appear in the source?"
show 2 review quotation "$DRAFT"

say "35. verbatim scan -- near-duplicate phrasing against the parsed corpus"
show 2 review verbatim scan "$DRAFT"

say "36. verbatim overlap -- the same check against one source, phrase by phrase"
show 2.5 review verbatim overlap "$DRAFT" sample_dt_overview_2024

say "37. discover --app -- export the topic graph as an offline viewer"
show 1.5 corpus discover --app "$WORK/topic-app"

say "next: the offline topic-graph viewer (content/topic_map.html)"
pause 1.5
