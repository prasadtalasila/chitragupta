"""One Tier 2 task per user skill, written to reach as much of it as one run can.

Each prompt pre-answers every question its skill asks (the runs are
non-interactive) and asks for the branches this five-paper corpus can
reach: an outline on one genre and sub-themes on another, a figure through
figure-drawer, a numbered equation, a single-source point, a thin
sub-theme, recorded steering, the critique loop, the render with its
evidence sidecar, the prose check and verbatim scan the writing standards
call for, and the stamp. What one prompt cannot reach (collections: the
sample bib has no `groups` field; an empty ledger: the bench syncs first)
is left out rather than faked.

A task may name a prerequisite (`after`), which runs first in the same
project and is not scored, and two fixture hooks:

- `setup(project)` runs after the scaffold and sync, before anything else;
- `seed(project)` runs after the prerequisite, before the task: the
  revisers start from a real survey and then meet the defects their
  branches exist for (US spellings, an unstamped hand edit, short
  unquoted source runs).

No fixture writes a citekey that is not in the sample bib and its parsed
PDFs; every seeded run is copied from `content/parsed/`.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, NamedTuple, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE = REPO_ROOT / "docs" / "examples" / "sample-project"
SURVEY = "content/drafts/dt/survey.md"
NON_INTERACTIVE = (
    "This is a non-interactive run, so do not stop to ask me anything; "
    "where the skill would ask, use my answers here. "
)
TO_THE_END = (
    " Follow the skill through to the end, every step it lists, including its"
    " self-check with draft gate, and do not run corpus sync or enrich."
)


class Task(NamedTuple):
    """One skill's Tier 2 task. `body` is what a user would bring: the
    pre-answers to the skill's questions and what they want in the draft.
    `tail` names the closing steps (render, prose check, verbatim scan,
    stamp, ...). The full prompt asks for both; the skill-only prompt
    leaves the tail out, so only the skill can make a model run those
    steps -- the arm a shrink is gated on, since a step a pointer hides is
    exactly what a prompt that names it would mask."""

    body: str
    tail: str
    draft: str
    after: Optional[str] = None
    setup: Optional[Callable[[Path], None]] = None
    seed: Optional[Callable[[Path], None]] = None

    def prompt(self, skill_only: bool = False) -> str:
        return self.body + ("" if skill_only else self.tail) + TO_THE_END


# Words that name a closing step; no task's skill-only prompt may hold one
# (bench_skill_harnesses.self_check proves it for every task).
TAIL_WORDS = (
    "render",
    "stamp",
    "verbatim scan",
    "verbatim-scan",
    "prose check",
    "prose-check",
    "evidence sidecar",
    "draft diff",
    "section map",
    "sign-off",
    "verified environment",
)


def _cg(project: Path, *args: str) -> None:
    """A fixture's own `python -m chitragupta...` call, checked."""
    subprocess.run(
        [sys.executable, "-m", *args],
        cwd=project,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _insert_after_first_paragraph(draft: Path, text: str) -> bool:
    """Put `text` after the first paragraph of the draft's first `## `
    section, so the seed sits inside a section that has a sections.md row.
    False (and nothing written) when the prerequisite left no such draft."""
    if not draft.exists():
        return False
    body = draft.read_text(encoding="utf-8")
    match = re.search(r"^## .+\n\n(?:.+\n)+", body, flags=re.MULTILINE)
    if match is None:
        return False
    draft.write_text(body[: match.end()] + "\n" + text + "\n" + body[match.end() :], "utf-8")
    return True


def seed_draft_reviser(project: Path) -> None:
    """US spellings for the copy-edit to change, and a section added after
    the stamp, so `dossier status` reports the draft CHANGED and offers
    its repairs."""
    draft = project / SURVEY
    if not _insert_after_first_paragraph(
        draft,
        "Teams analyze the twin's behavior on a color dashboard centered on the "
        "asset, and they modeled its fiber links by hand.",
    ):
        return
    body = draft.read_text(encoding="utf-8")
    outlook = (
        "## Outlook\n\nWhich of these strategies a plant adopts is a decision "
        "for its operators.\n\n"
    )
    head, sep, tail = body.partition("## References")
    draft.write_text(head + outlook + sep + tail if sep else body + "\n" + outlook, "utf-8")


def seed_agenda_reviser(project: Path) -> None:
    """One item of each unattended class the agenda can file without
    touching the corpus: prose (`simply`, `Clearly`, an unexpanded `MES`,
    US spellings under an en-GB `language:` line) and two short unquoted
    runs copied from the parsed sources with their own citekeys. The
    verbatim report is refreshed after seeding, as the agenda reads it."""
    draft = project / SURVEY
    if not _insert_after_first_paragraph(
        draft,
        "Clearly, an MES simply has to analyze the twin's behavior. Integration "
        "matters because the engineering cost rises sharply at each level "
        "[@sample_dt_overview_2024]. In one plant, by month four the weekly checks "
        "were abandoned as redundant [@sample_dt_factory_2022].",
    ):
        return
    _cg(project, "chitragupta.draft", "dossier", "set-language", SURVEY, "en-GB")
    _cg(project, "chitragupta.review", "verbatim", "scan", SURVEY, "--write")


def setup_docling(project: Path) -> None:
    """review-digest copies from Docling's passage sidecars, which the
    pdftotext backend never writes; without them every source takes the
    skill's "no sidecar" branch and nothing is copied."""
    config = project / "config.toml"
    text = config.read_text(encoding="utf-8")
    config.write_text(
        re.sub(r'^backend = "pdftotext"', 'backend = "docling"', text, flags=re.M), "utf-8"
    )
    _cg(project, "chitragupta.corpus", "sync")


def setup_book(project: Path) -> None:
    """The sample book's spec and its one written chapter, plus the chapter
    the sample leaves unwritten, accepted, so the assembler gets past its
    "every unit accepted" stop and composes. The added chapter states only
    what `sample_dt_overview_2024` says."""
    for part in ("specs", "drafts"):
        shutil.copytree(
            SAMPLE / "content" / part / "twin-basics",
            project / "content" / part / "twin-basics",
            dirs_exist_ok=True,
        )
    (project / "content" / "drafts" / "twin-basics" / "ch-vocabulary.md").write_text(
        VOCABULARY, encoding="utf-8"
    )
    _cg(
        project,
        "chitragupta.draft",
        "unit",
        "accept",
        "content/drafts/twin-basics",
        "ch-vocabulary",
        "--source",
        "sample_dt_overview_2024",
    )


VOCABULARY = """\
# Vocabulary and Levels of Integration

A digital twin is a virtual representation of a physical system kept
consistent with that system for its operating life, and the word is used
loosely enough that the levels below it need names of their own
[@sample_dt_overview_2024].

## The three levels

A digital model exchanges data with the physical object only through
manual steps; a digital shadow adds an automatic flow from the physical
object to the virtual one; a digital twin closes the loop, so data flows
automatically both ways and the virtual object can actuate the physical
one [@sample_dt_overview_2024]. The distinction is a property of data
flow, not of model sophistication.

## What a twin is for

Four uses dominate: monitoring, prediction, optimisation and
record-keeping, the last of which keeps the asset's history as an audit
trail after the asset is retired [@sample_dt_overview_2024].
"""

SURVEY_BODY = (
    "Use the survey-writer skill to draft a literature survey on digital twins in "
    "manufacturing from this project's synced corpus. " + NON_INTERACTIVE + "My answers: "
    "the slug is dt/survey, so the draft is content/drafts/dt/survey.md; the reader is a "
    "PhD committee reading the background chapter of a thesis on digital twins in "
    "manufacturing; it covers what a digital twin is as distinct from a model or a "
    "shadow, how the twin is kept synchronised with the asset, factory deployment and "
    "operator trust, interoperability standards, and the security of twins (search for "
    "it properly before you call it thin); it does not cover machine-learning anomaly "
    "detection except where a source ties it to a twin; there is no collection, so use "
    "the whole corpus and omit --collection; dialect en-GB; about 1,200-1,600 words; no "
    "outline, choose the sub-themes yourself. Where the sources disagree (what counts as "
    "a twin, how slow drift is caught), say so in the text. Mark any point only one "
    "source supports. Draw one figure through the figure-drawer skill, a taxonomy of "
    "model, shadow and twin, captioned and referenced from the prose. State the reported "
    "detector figures as quantities, with one numbered equation that the prose refers "
    "to. Record this steering: do not lead with tooling."
)
SURVEY_TAIL = (
    " Then render the draft to tex, pdf and md with draft render, write its evidence "
    "sidecar, and run the prose check, the verbatim scan and the stamp."
)

TIER2_TASKS = {
    "survey-writer": Task(SURVEY_BODY, SURVEY_TAIL, SURVEY),
    "textbook-chapter-writer": Task(
        "Use the textbook-chapter-writer skill to write a chapter that students study: they "
        "read it, they do not follow it at a keyboard. " + NON_INTERACTIVE + "My answers: "
        "the slug is dt/book-chapter (content/drafts/dt/book-chapter.md); the reader is a "
        "second-year undergraduate engineer who knows mean and standard deviation but has "
        "never met a digital twin; it covers the model, shadow and twin distinction, "
        "synchronisation strategies and staleness, and rolling z-score anomaly detection on "
        "a twin's state; it does not cover autoencoders in depth; no collection, use the "
        "whole corpus and omit --collection; dialect en-US; about 2,500 words. Ground the "
        "motivation in at least two corpus papers, and keep one short quotation where a "
        "definition earns its author's exact words. Include a fully worked z-score example, "
        "then a faded one, then a problem left to the student; a captioned table of "
        "symbols; a numbered final equation the text refers back to; one figure through the "
        "figure-drawer skill; and five exercises graded easy, medium and hard, each with a "
        "hint. Record this steering: assume no probability beyond mean and variance.",
        " Then render it, write the evidence sidecar, and run the prose check, the verbatim "
        "scan and the stamp.",
        "content/drafts/dt/book-chapter.md",
    ),
    "thesis-chapter-writer": Task(
        "Use the thesis-chapter-writer skill. " + NON_INTERACTIVE + "My answers: the slug is "
        "dt/thesis-chapter, a LaTeX fragment at content/drafts/dt/thesis-chapter.tex; the "
        "examiner is a manufacturing-systems expert who knows control but not twin "
        "synchronisation; dialect en-GB; the research question is: which synchronisation "
        "strategy lets a factory digital twin earn enough operator trust to be given "
        "actuation authority?; it covers the model, shadow and twin distinction, "
        "synchronisation strategies and staleness marking, the factory case and "
        "interoperability as a precondition; it does not cover anomaly-detection algorithms "
        "beyond drift; no collection, omit --collection; about 2,000 words. Open the "
        "dossier with --outline, and write outline.md with three sections, each with a "
        "brief: and queries: -- 'Levels of integration' (queries: digital twin shadow model "
        "integration levels), 'Synchronisation and staleness' (queries: synchronisation "
        "staleness event-driven threshold push periodic pull) and 'Trust on the factory "
        "floor' (queries: operator trust weekly checks override), and give the last one "
        "the claim: twins with actuation authority cut unplanned downtime by half. Argue "
        "toward a position, mark single-source points, and surface conflicts between "
        "sources. Include a captioned comparison table of the three strategies, one "
        "architecture figure through the figure-drawer skill, and a numbered equation for "
        "the staleness bound. Record this steering: argue harder against threshold push.",
        " Then render it, write the evidence sidecar, quote any render notices to me, and "
        "run the prose check, the verbatim scan and the stamp.",
        "content/drafts/dt/thesis-chapter.tex",
    ),
    "tutorial-writer": Task(
        "Use the tutorial-writer skill. " + NON_INTERACTIVE + "My answers: the slug is "
        "dt/tutorial (content/drafts/dt/tutorial.md); the learner is a Python beginner who "
        "can run a script in a terminal but has never seen a digital twin; the artifact is "
        "a standard-library-only Python 3 script, twin_monitor.py, that replays a "
        "60-reading temperature stream with a fixed seed and an injected slow drift and "
        "prints each reading a rolling z-score flags above 4 standard deviations; it covers "
        "building and running that script; it does not cover other detectors, Docker or "
        "other languages; dialect en-GB; it must be completable in 30 minutes; no "
        "collection, omit --collection. Include a table of the expected output lines and "
        "two figures through the figure-drawer skill (what you will build; how the data "
        "flows). Treat the threshold as a quantity in the prose and as a typed constant in "
        "the code. Cite at least two corpus papers, in 'Where to go next' only. Record this "
        "steering: no third-party packages.",
        " Run every command yourself and record the verified environment. Then render it, "
        "run the prose check, the verbatim scan and the stamp, and tell me whether "
        "verification passed in full.",
        "content/drafts/dt/tutorial.md",
    ),
    "review-digest": Task(
        "Use the review-digest skill to build a verbatim digest of what this corpus says "
        "about operating digital twins. " + NON_INTERACTIVE + "My answers: the path is "
        "content/drafts/dt/digest.md; the reader is an engineering master's student who has "
        "read none of the five papers; it covers what a twin is and its levels of "
        "integration, synchronisation and staleness, factory deployment and trust, "
        "interoperability standards, and anomaly detection on twin state streams; it does "
        "not cover vendor tooling; glossary: model, shadow, twin, staleness, asset-model "
        "registry, as the overview paper defines them; dialect en-GB; no collection, the "
        "whole corpus; the themes are exactly those five. Make the disagreement between the "
        "overview paper and the interoperability paper about what keeps a twin project "
        "alive visible, with both sides copied. Typeset the anomaly paper's rolling z-score "
        "rule as an equation of your own, with its math.md row. If a source has no passage "
        "sidecar, say which. After the digest and synthesis reports: yes, work the report "
        "for one repair pass, every item, worst class first, keeping or reverting each by "
        "the skill's rule and logging each in revisions.md, then stop. Record these "
        "instructions as steering.",
        " Then stamp and present.",
        "content/drafts/dt/digest.md",
        setup=setup_docling,
    ),
    "deep-research": Task(
        "Use the deep-research skill at standard depth for a multi-perspective report on "
        "what makes an operational digital twin trustworthy. " + NON_INTERACTIVE + "My "
        "answers: the path is content/drafts/dt/deep-research.md; the reader is a plant "
        "engineering manager deciding whether to fund a twin pilot; it covers definitions, "
        "synchronisation, deployment trust, interoperability and anomaly detection; it does "
        "not cover vendor products; dialect en-GB; search the whole corpus -- I considered "
        "limiting it to one collection and decline. Open the dossier with --outline, and "
        "write outline.md with six sections, each with a brief: and queries: -- definitions "
        "(digital twin shadow model integration levels), synchronisation (synchronisation "
        "staleness event-driven push pull), trust (operator trust override divergence), "
        "interoperability (semantic interoperability asset-model registry), anomaly "
        "detection (anomaly detection drift z-score autoencoder) and provenance (blockchain "
        "ledger provenance for twins). Drop the adoption and incentives lens and log that "
        "as steering.",
        " Keep the verbatim-scan report with --write. Run every phase through the render, "
        "the evidence sidecar and the stamp.",
        "content/drafts/dt/deep-research.md",
    ),
    "figure-drawer": Task(
        "Use the figure-drawer skill directly to add one more figure to the existing survey "
        "content/drafts/dt/survey.md. " + NON_INTERACTIVE + "My answers: the figure is "
        "figures/shadow-vs-twin, comparing a digital shadow and a digital twin in two "
        "lettered panels -- (a) data flows from physical to virtual only, (b) data flows "
        "both ways, with actuation as the focal node; look at the sources' figures first; "
        "if the taste gate concludes that a sentence or a table would do, draw it anyway "
        "and say so; put its marker after the paragraph that defines the levels, with a "
        "caption and an inline reference from that paragraph; record any deliberate check "
        "finding with a cg-allow and its reason.",
        " Look at the rendered figure. Then carry on with draft-reviser's loop: write the "
        "dossier back, gate, references, render tex, pdf and md, stamp, the prose check, "
        "the verbatim scan and the draft diff.",
        SURVEY,
        after="survey-writer",
    ),
    "draft-reviser": Task(
        "Use the draft-reviser skill on content/drafts/dt/survey.md. "
        + NON_INTERACTIVE
        + "My answers: accept every dossier-drift repair you offer, running its command and "
        "logging it; if you offer to re-run a section's declared query, yes. The changes: "
        "(a) correct the interoperability section against sample_std_interop_2021 -- check "
        "with retrieve evidence what its layers actually are -- and make evidence.md match; "
        "(b) add a paragraph on machine-learning anomaly detection over plant data in "
        "general: if that conflicts with scope.md, do not widen the scope, leave it out and "
        "tell me; (c) shorten the factory section by about a third. Then, as a separate "
        "copy-edit pass, put the draft into British English (en-GB, as scope.md's language: "
        "line says); if the copy-edit tempts a change of substance, report it and do not "
        "make it. Snapshot the result as 'benchmark-v1'.",
        " Log steering and revisions, pass the gate, run references, render tex, pdf and "
        "md, stamp, run the prose check, rebuild the section map and run the verbatim scan, "
        "then the draft diff as a pdf.",
        SURVEY,
        after="survey-writer",
        seed=seed_draft_reviser,
    ),
    "corpus-reviser": Task(
        "Use the corpus-reviser skill: re-check the entire draft content/drafts/dt/survey.md "
        "against the whole corpus, cost regardless -- state the cost, then go on without "
        "waiting. " + NON_INTERACTIVE + "I agree a scope change: the survey now also covers "
        "machine-learning anomaly detection where it consumes a twin's state stream; update "
        "scope.md's scope accordingly and, since that changes why any source was rejected, "
        "say so and re-judge it. Keep the reader unchanged. Fix any claim the sources "
        "contradict. Accept any dossier-drift repair you offer.",
        " Re-search every recorded sub-theme, read every section, write back evidence, "
        "rejected, sections, steering and revisions, gate, references, render, stamp, run "
        "the prose check (report only), rebuild the section map and run the verbatim scan, "
        "then the draft diff as a pdf.",
        SURVEY,
        after="survey-writer",
    ),
    "agenda-reviser": Task(
        "I am asking you to run the agenda-reviser skill on content/drafts/dt/survey.md: "
        "work its review agenda and repair every unattended item, for one pass. "
        + NON_INTERACTIVE
        + "My answers: for any long verbatim run, convert it to an "
        "attributed quotation in quote marks and keep its citation; escalations and "
        "surfaced items go in your report. Also accept the uncited-claim items for me. "
        "Report objective_class_count before and after, not_refreshed and refresh_errors, "
        "any stale-span refusal, and what the verbatim tiers did not check.",
        " Follow every step through the closing full-format agenda run and the draft diff "
        "as a pdf.",
        SURVEY,
        after="survey-writer",
        seed=seed_agenda_reviser,
    ),
    "book-assembler": Task(
        "Use the book-assembler skill to assemble the book in content/drafts/twin-basics "
        "into one LaTeX document. " + NON_INTERACTIVE + "My answers: the author is Sample "
        "Author; if a unit is not accepted, report it and stop as the skill says; build the "
        "PDF, since TeX Live is installed.",
        " Report every registry finding, the gate result and the per-unit prose-check and "
        "verbatim results as one table, then stop at the sign-off.",
        "content/rendered/twin-basics/book.tex",
        setup=setup_book,
    ),
}
