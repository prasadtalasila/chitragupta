# Docs refresh: current release only, and a page per figure rule

Status: **a plan.** Branch `docs-refresh-2026-10`, off `main` at 6.155.0.

Eight read-only audits checked every page under `docs/` and every root
document against the code at 6.155.0. This plan lists what they found and
what this branch changes. It is a docs-only change plus one test, so it
takes a PATCH bump.

## Ground rules for every page

1. **Present tense, current release.** Delete narration of earlier
   behaviour ("used to", "until #N", "since 6.x", "now does", "no
   longer", "an earlier revision of this file said"). Where the history
   carries a reason that still binds, keep the reason and state it as a
   present-tense fact.
2. **No provenance tags.** Drop inline `(#NNN)` tags. Keep an issue
   link only when it points at work that is still open, or names a
   mechanism a reader has to search for (`#781`).
3. **Status lines carry the kind, not dates.** `Status: **<kind>.**`
   only. The "Written/Updated" dates drifted on almost every page, and
   git records them anyway. DEVELOPER.md's convention changes to match.
4. **Version-gated upgrade notes go.** Sections such as "The ledger path
   change in 6.133.0", "A schedule written before 5.2.0" and "Migrating a
   checkout to `pip install`" are removed. Each keeps one sentence of
   current behaviour.
5. **Measurements stay when they are evidence.** A dated table in a
   `measurements` page is evidence and stays. Before/after narration
   around it goes.
6. **Counts are checked, not copied.** The code has 11 skills, 6
   drafting genres, 11 review aids (`agenda` reads 8 of them), 12 `draft`
   verbs, 11 TikZ scaffolds, 36 `figure check` rules (28 objective, 8
   advisory), and `sync` exit codes 0/1/2/3.

## Part A: figure drawing and checking

The figure audit found the confusion the request describes:

- The figure rules are documented in three places: FIGURE-DRAWER (9 rules
  with a why), TIKZ-STYLE's last section (all 36, as a table), and the
  skill's hidden `references/check.md` (the fixes). 27 of the 36 rules
  have no "why" anywhere a person would look.
- FIGURE-DRAWER is a how-to that turns into a rule reference halfway
  through. It lists 7 of the 11 layouts, misses the skill's taste gate,
  and its worked example fails the checker the page teaches (6 findings).
- `review figure` (7 rules, a whole draft) and `figure check` (36 rules,
  one figure) share ids but measure differently, and no page says which
  to run.

What this branch does:

- **A1. New section `docs/figure-checks/`**: a README that explains how
  to read a report, `cg-allow`, and how `review figure` relates to
  `figure check`, plus one page per family of rules:
  - `build.md`: `does-not-compile`, `nothing-measurable`,
    `loads-library-by-hand`.
  - `size.md`: `size-width`, `size-stray`, `content-protrusion`, and the
    size reports.
  - `nodes.md`: `node-overlap`, `node-text-overload`,
    `stranded-arrowhead`, `focal-count`, `unnamed-pic`.
  - `connectors.md`: `c1` to `c7`, with the layout exemption table.
  - `colour-and-type.md`: `k1`, `k2`, `type-below-floor`,
    `colour-off-palette`, `tint-outside-band`.
  - `wording.md`: `w4-pictograph` and the advisory `w1` to `w3`.
  - `twin.md`: `twin-missing`, `t1` to `t3`.

  Every rule gets what it catches, why a reader cares, a **faulty
  figure** with the line `figure check` prints for it, the **fixed
  figure**, and both rendered. The examples are real files under
  `docs/figure-checks/examples/<rule>/`.
- **A2. `tests/test_figure_check_examples.py`** compiles every example.
  Each faulty figure must fire its own rule and no other; each fixed
  figure must fire nothing and leave nothing unmeasured. Each page's
  **Fix** line must match `check.md`. It replaces
  `tests/test_figure_rule_gallery.py` and the FIGURE-DRAWER half of
  `tests/test_figure_rule_ids.py`. The two combined gallery images go.
- **A3. FIGURE-DRAWER.md** becomes the task page only. It mirrors the
  skill's nine steps, lists all 11 layouts, and uses a worked example
  that `figure check` passes. The rule section moves out.
- **A4. TIKZ-STYLE.md** keeps the standard (metaphors, panels, palette,
  house block, type, width). The rule table and `cg-allow` move to
  `figure-checks/README.md`, and `test_figure_rule_ids` follows them.
  Stale claims ("not mechanically checked", "six layout metaphors",
  "seventeen" geometry rules) are fixed.
- **A5.** WRITING-STANDARDS §10, REVIEW.md, `assets/tikz/README.md` and
  DIAGRAMS.md name `figure check` where they name only `review figure`.
- **A6. FIGURE-ROADMAP.md** leads with a table of what has shipped,
  followed by the open Parts only.

## Part B: stale facts, by page group

The highest-signal items. The full audit notes are in the branch
history of this file's PR.

- **CLI.md / CONFIG.md / config.toml.example.**
  - `draft style` runs six Python checks without vale, not two.
  - The `stix-two` install stage is missing.
  - `draft render` is missing `--output-dir` and `--fragment`, and the
    section on them sits under `draft style`.
  - CONFIG says `acronyms` is unread by `draft style`; it is read.
  - "env var of the same name" is wrong (`[bib] path` maps to
    `BIB_FILE`).
  - "repo root" should be "project directory".
  - The nine-aid figures need a note that they predate the eleven aids.
  - `init`, `doctor` and `install` get short stubs.
- **Root docs.**
  - AGENTS.md lists 10 of 11 aids and says "ten".
  - DEVELOPER.md: the skill and aid counts, the missing modules, the
    install stages, a dead README link, and `poetry lock` where
    `scripts/relock.py` is needed.
  - DEVELOPER-AGENTS.md says `docker/` is never built; CI builds it on
    every push.
  - DOCKER-DEVELOPER.md's Python matrix is wrong.
  - DEV-ENV.md's defaults are wrong.
  - MIGRATION.md calls a Poetry-to-uv change it never made "its own
    page".
  - The release asset list is incomplete.
- **Writing guides.**
  - The aid count and the six genres (the verbatim digest is missing)
    are wrong.
  - WRITING-PROCESS's book table disagrees with WRITE-A-BOOK.
  - GENRE.md's skill ordinals and its prose-check scope are wrong.
  - The sample agendas in the WRITE-A-* tutorials name Vale rules that
    do not exist (`DefectMarker`, `AcronymNotExpanded`,
    `DialectDrift`), and they lack the header lines the renderer
    writes.
  - `figure-drawer` and `agenda-reviser` go unmentioned where they
    apply.
  - WRITE-A-BOOK says `bibtex` where the skill uses `bibtexu`, and
    citeproc where fragments use natbib.
  - The "unattended" column in WRITING-STANDARDS §9 does not match the
    code.
  - HOUSE-STYLE.md is labelled a proposal but has mostly shipped; it
    becomes a reference with its three open items.
  - REJECTION.md says draft-reviser needs a dossier that six genres now
    write.
  - The five draft-drift checks are restated three times; they are kept
    in DOSSIER, with pointers elsewhere.
- **Review layer.**
  - The agenda excludes `union` and `digest`.
  - `verbatim` has four modes.
  - `agenda-reviser` runs up to `pass_bound` = 3 passes, not one.
  - The overlap gate was declined, not "eventual".
  - CITATION-PROVENANCE names functions that no longer exist.
  - HOOKS.md misdescribes the Codex hooks.
  - Wrong skill counts in HARNESS, LLM-AGENTS and TLDR.
- **Corpus and retrieval.**
  - Exit code 3 is missing in ARCHITECTURE and DESIGN.
  - Skill and genre counts are wrong.
  - The `parse_failed` retry rule contradicts itself.
  - RETRIEVAL's module list is incomplete.
  - PDF-PARSER's "fallback ladder" contradicts ARCHITECTURE's tiers.
  - RENDERING-FLOW's "four places" table has five rows.
- **Topic discovery and the rest.**
  - TOPIC-DISCOVERY's JSON schema lacks `communities` and `paths`, and
    its sample artefacts are older than the code.
  - TOPIC-DISCOVERY-GRAPH is a proposal that now contradicts the code;
    it becomes a short note on the unbuilt ideas.
  - ZOTERO and EXPORT-ZOTERO-GROUPS disagree on `groups` paths. This is
    flagged, not guessed.
- **Roadmaps and status pages.**
  - FEATURE-ROADMAP presents shipped D6 work as open.
  - FEATURES has wrong counts in its diagram.
  - REQUIREMENTS, TECHNICAL-DEBT and CODE-STANDARDS are mostly closed
    history; each is cut to "what holds now" plus the open items.
  - "classless" is false (155 classes).
  - NAME.md says `citation gate`.
- **mkdocs.yml.** PROMPTS, REQUIREMENTS, `docs/examples/README.md` and
  the new figure-checks pages go in the nav. UV-MIGRATION moves to a
  "Decisions" group.

## Part C: humanizer pass

When Parts A and B are done, every changed page gets one pass with the
humanizer skill to strip the tells of machine-written prose. Facts,
commands, numbers, links and anchors stay as they are, and the pinned
tests are re-run afterwards.

## Not changed here (found, reported separately)

Code defects the audits turned up are for issues, not this branch:

- `node-text-overload` never counts a `\cglab{Name}{gloss}` label: the
  label pattern stops at the first `}`.
- `stranded-arrowhead` sees only a literal `->` in a path's options, so
  a house `cgedge` arrow is never checked.
- `chitragupta --help` says "review -- four read-only aids".
- `assets/tikz/exemplars/architecture.tex` reports two `c6-tag-covered`
  findings without a `cg-allow`.
- `draft figures --help` says "never reproduce a source figure in a
  draft", which contradicts the digest exception in VERBATIM-DIGEST.md.
- ZOTERO.md (`groups` carries `Parent > Child` paths) and
  `scripts/populate_bib_groups.py` (writes leaf names only) disagree,
  and one of them is wrong in code.
- The committed sample artefacts behind TOPIC-DISCOVERY.md
  (`topic_graph.json` and the discover output) predate `communities`,
  `paths` and the brokerage block. They are pipeline output and are
  regenerated, not hand-edited.
