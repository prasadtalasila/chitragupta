# Survey: what this genre alone needs

Read a section of this file when the step that sent you here cites it;
each section opens with when it applies. Paths here are from the project
root.

## 1. Sub-theme subagents and their packet

Read this before you dispatch the first sub-theme subagent.

**The packet is `claim:`/`quote:` shaped, not a paste of what the
subagent read.** Tell each subagent explicitly: write `claim:` in your
own words, after you have judged the source, not by lightly editing the
snippet or evidence window still on screen; capture `quote:` only where
a quotation is genuinely warranted. A subagent that returns a
`relevance:` line next to a pasted 500-character snippet or 600-character
evidence window has satisfied "never the raw candidates" in name only:
the raw retrieval window still reaches your context, just wearing a
`relevance:` label. The rule is on the *content* of what comes back, not
only on which candidates are excluded.

**The reason is not parallelism.** This is where the reliable token
saving is: it costs nothing in retrieval quality, unlike trimming what
you read. Anything you read yourself stays in your context and is
re-sent on every later turn of the run; anything a subagent reads is
paid for once. Four sub-themes retrieved inline is tens of thousands of
characters you would then carry through clustering, drafting, gating
and rendering, most of it material you already rejected.

**Skip it for a narrow topic with one sub-theme.** A subagent that
returns almost everything it read saves nothing and costs a dispatch.

## 2. The comparison table and the gap analysis

Read this before you write the comparison table or the gap-analysis
paragraph. How any table is captioned, marked, introduced and read is
`docs/writing-standards/tables.md` §13; this is what a survey's own table
and gap analysis hold.

**The comparison table is the one §13 was written for.** Its columns
are the approach or paper, the citekey, the core idea and the stated
limitations.

**The gap analysis says what the retrieved corpus does *not* cover**,
including the sub-themes that stayed thin after reformulation and any
cross-source disagreement found before writing.

**Organise a body paragraph around what its sources agree and disagree
about**, rather than summarising them one after another.

## 3. Why a survey emits the evidence sidecar

Read this if the user asks why the sidecar is rendered, or asks to skip
it.

A survey emits one, in pdf and md. This genre is the natural fit: it is
citation-dense, and its reader is mapping a field and wants to see what
the sources actually said.

## 4. Where this genre's rules come from

Read this when asked where the survey's writing rules come from, or when
deciding whether a Diátaxis rule applies to a survey.

The prose standards a survey inherits are not original to this project.
Full citations, licences and a per-principle attribution table are in
`docs/WRITING-STANDARDS.md`, "Sources and attribution". All three works
are openly licensed (CC-BY or CC-BY-SA) and require credit. What bears on
a survey specifically:

- **Last, *Technical Writing Essentials* (CC-BY 4.0)**: audience and task
  analysis as a step before drafting, and the introduction checklist
  that asks for scope and the reader's assumed background. Naming the
  reader and the scope before opening the dossier is that checklist
  applied to a survey.
- **Google, *Technical Writing Courses* (CC-BY 4.0)**: the curse of
  knowledge, defining each term once, and leading a paragraph with its
  point. The last matters more here than in any other genre, because a
  survey is read by skimming.
- **Procida, *Diátaxis* (CC-BY-SA 4.0)**: the genre-separation principle
  behind what a survey owes its reader. A literature survey is **not**
  one of Diátaxis's four quadrants: Diátaxis describes software
  documentation, and its tutorial and how-to rules (a single path, no
  options) would destroy a survey. Only the underlying insight transfers:
  a document trying to do two jobs does both badly.
