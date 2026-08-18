# PROMPTS.md

What text does the model actually see when a genre skill runs? This
document answers that for two skills that sit at opposite ends of this
pipeline's complexity: `textbook-chapter-writer`, a single-context skill,
and `deep-research`, a multi-agent one. They do **not** look the same --
the second half of this document is about why.

This file is self-contained: read it without any other doc open. Where
it names a file, that is so you can go verify the claim yourself, not
because you need to have already read it.

## Vocabulary this document assumes

- **The prompt**: everything the model is given before it generates --
  the harness's own system prompt, plus whatever project files, prior
  tool output and conversation turns are in context at that point.
- **CLAUDE.md**: this repository's router, loaded into every Claude Code
  session automatically. It is one page and contains almost no rules
  itself -- it says which of two longer files governs the task at hand
  and sends the agent there.
- **AGENTS.md / SOUL.md**: `AGENTS.md` is the rulebook for an agent
  *drafting content* with this pipeline (the citekey invariant, the
  four layers, the gate). `SOUL.md` is the one-page "why" behind it and
  the tie-breaker if two docs disagree. Both are pointed to by
  `CLAUDE.md`, not inlined in it.
- **A skill**: a Markdown file under `.claude/skills/<name>/SKILL.md`.
  Invoking one loads its full body into the current context, as
  instructions to follow for the rest of the turn -- it is not a
  function call, it is more text added to the same prompt.
- **A subagent**: a *separate* model context, dispatched by the running
  skill (via an `Agent`-style tool call), with its own system prompt --
  usually a file under `.claude/agents/<name>.md` -- and only the
  specific inputs the dispatching skill hands it. It cannot see the
  dispatching session's conversation, and the dispatching session
  cannot see its intermediate reasoning, only what it returns.
- **The dossier**: `content/dossiers/<draft path minus suffix>/`, a set
  of Markdown files (`scope.md`, `evidence.md`, `rejected.md`,
  `retrieval.md`, `steering.md`, `sections.md`) that record the
  judgment behind a draft -- reader, kept/rejected sources, glossary --
  so a later revision doesn't have to reconstruct it from a stale
  conversation. `docs/DRAFT-ITERATION.md` is the full design.

## 1. A single-context skill: `textbook-chapter-writer`

This skill never dispatches a subagent. Everything happens in one
context, so its prompt is one stack that only ever grows, in this
order:

```text
┌────────────────────────────────────────────────────────────────────┐
│         PROMPT FOR ONE textbook-chapter-writer TURN                 │
└────────────────────────────────────────────────────────────────────┘

1. HARNESS LAYER  -- fixed overhead, present on every turn
   ┌──────────────────────────────────────────────────────────────┐
   │ Claude Code's own system prompt (tool definitions, platform,  │
   │ environment)                                                  │
   │ SessionStart hook output (e.g. the corpus-config preflight    │
   │ check)                                                        │
   └──────────────────────────────────────────────────────────────┘
                                │
                                ▼
2. PROJECT ROUTER  -- CLAUDE.md, auto-loaded by the harness every turn
   ┌──────────────────────────────────────────────────────────────┐
   │ CLAUDE.md                                                     │
   │  "drafting content? -> read AGENTS.md, that file and the      │
   │   skill are the whole contract"                                │
   │  + the one hard rule, stated once: never fabricate a citekey  │
   └──────────────────────────────────────────────────────────────┘
                                │  the agent follows the pointer
                                ▼
3. GOVERNING CONTRACT  -- read because CLAUDE.md said to
   ┌──────────────────────────────────────────────────────────────┐
   │ AGENTS.md -- citekey invariant in full, the bib file as       │
   │              source of truth, the four layers, the gate       │
   │ SOUL.md   -- the one-page why; tie-breaker on disagreement    │
   └──────────────────────────────────────────────────────────────┘
                                │
                                ▼
4. SKILL BODY  -- loaded whole the moment the skill is invoked
   ┌──────────────────────────────────────────────────────────────┐
   │ .claude/skills/textbook-chapter-writer/SKILL.md                │
   │   frontmatter (name/description/triggers) + the full 18-step  │
   │   process (name the reader -> objectives -> scope -> ...      │
   │   -> gate -> render -> present)                                │
   └──────────────────────────────────────────────────────────────┘
                                │  the skill's own cross-references,
                                │  pulled in on demand as steps reach them
                                ▼
5. CROSS-GENRE STANDARDS
   ┌──────────────────────────────────────────────────────────────┐
   │ docs/WRITING-STANDARDS.md -- prose rules shared by every genre │
   │ docs/DRAFT-ITERATION.md   -- the dossier's design               │
   │ docs/PLAGIARISM.md        -- what the verbatim scan does and   │
   │                              does not catch                    │
   │ assets/style/acronyms.toml (+ the user's own file, if          │
   │              config.toml's [style].acronyms points at one)     │
   └──────────────────────────────────────────────────────────────┘
                                │
                                ▼
6. RUN-SPECIFIC STATE  -- created and re-read during THIS run
   ┌──────────────────────────────────────────────────────────────┐
   │ content/dossiers/<slug>/scope.md      (reader, glossary,      │
   │                                         covers/does-not-cover) │
   │ content/dossiers/<slug>/retrieval.md  (every search() call,   │
   │                                         logged via --log)      │
   │ content/dossiers/<slug>/rejected.md   (worked examples and     │
   │                                         exercises dropped)      │
   │ content/dossiers/<slug>/steering.md   (the user's in-chat asks)│
   │ content/ledger.sqlite + src.retrieval.search() hits, if the    │
   │              chapter grounds its motivation section in one     │
   └──────────────────────────────────────────────────────────────┘
                                │
                                ▼
7. THIS TURN
   ┌──────────────────────────────────────────────────────────────┐
   │ The user's actual request (topic, reader level, any steering) │
   │ Relevant entries from the user's own persistent memory, if any │
   └──────────────────────────────────────────────────────────────┘
                                │
                                ▼
              ══════════════════════════════════════
                ALL SEVEN LAYERS, CONCATENATED,
                ARE WHAT THE MODEL GENERATES AGAINST
              ══════════════════════════════════════
```

Layers 1-3 are fixed cost on every turn in this repository, regardless
of skill. Layer 4 is what makes this *this* skill rather than
`survey-writer` or `tutorial-writer`. Layers 5-6 arrive incrementally,
pulled in as the skill's own numbered steps reach the point that needs
them -- step 0 pulls in `acronyms.toml`, step 3 pulls in a retrieval
call, and so on -- rather than all at once at the start. Layer 7 is
the only layer that changes from one invocation of this skill to the
next.

## 2. A multi-agent skill: `deep-research`

`deep-research` shares layers 1-3 with every other skill in this
pipeline -- CLAUDE.md still routes to AGENTS.md/SOUL.md first, the
citekey invariant still binds it. Layer 4 onward is where it stops
looking like the diagram above, for one structural reason:
**`deep-research` is not one context, it is one orchestrating context
plus a dozen short-lived subagent contexts it dispatches and discards.**
A subagent's prompt is built fresh each time, and does not inherit the
orchestrator's conversation -- only the specific fields the orchestrator
decides to hand it.

### 2a. The orchestrating context

Same first three layers as any skill, then:

```text
4. SKILL BODY
   ┌──────────────────────────────────────────────────────────────┐
   │ .claude/skills/deep-research/SKILL.md   -- the 7 phases        │
   │ .claude/skills/deep-research/reference.md -- exact protocol,   │
   │        depth-preset defaults, the report template, the         │
   │        peer-review reconciliation rule -- pulled in because     │
   │        SKILL.md cites it by name rather than repeating it       │
   └──────────────────────────────────────────────────────────────┘
                                │
                                ▼
5. CROSS-GENRE STANDARDS  (same as every other skill)
   docs/WRITING-STANDARDS.md, assets/style/acronyms.toml, ...
                                │
                                ▼
6. RUN STATE  -- grows phase by phase; this is most of what makes a
   deep-research prompt large by the time Phase 7 runs
   ┌──────────────────────────────────────────────────────────────┐
   │ content/dossiers/deep-research-<slug>/scope.md                 │
   │ content/dossiers/deep-research-<slug>/evidence.md   -- every    │
   │        interviewer's kept claims (Phase 2) and every writer's   │
   │        added sources (Phase 5), transcribed by the orchestrator │
   │        itself -- a subagent never writes here                   │
   │ content/dossiers/deep-research-<slug>/rejected.md   -- every     │
   │        discarded citekey, with the query and why                │
   │ content/dossiers/deep-research-<slug>/sections.md   -- the       │
   │        outline -> citekey plan (Phase 4), reconciled to what     │
   │        the report actually cites (Phase 7e)                     │
   │ subagent packets returned from Phases 2, 5 and 7 -- Markdown     │
   │        text handed back by each dispatch, read once and          │
   │        transcribed above, then gone                              │
   └──────────────────────────────────────────────────────────────┘
                                │
                                ▼
7. THIS TURN -- topic, reader, scope, depth preset (quick / standard /
   deep), any steering
```

The orchestrator never pastes a subagent's returned packet, or the
dossier's accumulated evidence, into a *later* subagent's dispatch
prompt. It hands back a **pointer** instead:

```bash
python -m src.draft dossier brief content/drafts/deep-research-<slug>.md --section "<heading>"
```

`docs/TOKENS.md` has the reasoning: pasted evidence is spent as output
tokens once per writer it's pasted into, while a pointer costs about
forty tokens and the writer reads the underlying rows inside its own
context. That discipline is why the orchestrator's own prompt does not
balloon by the size of every packet every subagent ever returned --
only the transcribed, deduplicated dossier does.

### 2b. A dispatched subagent's context (the part that's genuinely different)

Each subagent dispatched from Phases 2, 5 and 7 gets its **own** fresh
context. Its shape is not layers 1-7 above; the orchestrator's
conversation, `CLAUDE.md`, `AGENTS.md` and `SOUL.md` are not
automatically forwarded into it. What replaces layers 2-4 is a single
file the harness loads as that subagent's system prompt:

```text
┌────────────────────────────────────────────────────────────────────┐
│           PROMPT FOR ONE DISPATCHED SUBAGENT (generic shape)         │
└────────────────────────────────────────────────────────────────────┘

1. HARNESS LAYER          -- same fixed overhead as any context
                                │
                                ▼
2. AGENT DEFINITION       -- stands in for CLAUDE.md/AGENTS.md/SOUL.md
                              /SKILL.md all at once, for this one role
   ┌──────────────────────────────────────────────────────────────┐
   │ .claude/agents/<role>.md                                       │
   │   frontmatter: name, one-line description, allowed tools       │
   │   body: what this role does, its process, its grounding rule   │
   │   ("never fabricate a citekey" is restated here, inline --      │
   │   the subagent does not go read AGENTS.md to learn it)          │
   └──────────────────────────────────────────────────────────────┘
                                │
                                ▼
3. ORCHESTRATOR-SUPPLIED PARAMETERS  -- small, specific, chosen by
   the phase that dispatched this subagent -- not the whole run
   ┌──────────────────────────────────────────────────────────────┐
   │ e.g. TOPIC, PERSPECTIVE, ROUNDS, DRAFT PATH  (interviewer)     │
   │ e.g. TOPIC, READER, GLOSSARY, section fragment, a `dossier      │
   │      brief --section` command instead of pasted evidence       │
   │      (writer)                                                  │
   │ e.g. the full draft text, DRAFT PATH, one assigned role         │
   │      (peer-reviewer)                                            │
   └──────────────────────────────────────────────────────────────┘
                                │
                                ▼
4. WHAT IT RETURNS  -- Markdown handed back to the orchestrator;
   this subagent's own context is discarded once it returns, so
   anything not in the returned text is gone
```

Three roles fill that shape differently:

| Role | Defined in | Gets (step 3) | Returns (step 4) |
|---|---|---|---|
| `deep-research-interviewer` (Phase 2, one per persona, parallel) | `.claude/agents/deep-research-interviewer.md` | `TOPIC`, `PERSPECTIVE`, `ROUNDS`, `DRAFT PATH` (for `--log`) | Core position, cited key claims, one unique insight, citekeys consulted **and** citekeys discarded with the query and why |
| `deep-research-writer` (Phase 5, one per section, parallel) | `.claude/agents/deep-research-writer.md` | `TOPIC`, `READER`, `GLOSSARY`, its section's outline fragment, and a `dossier brief --section` command in place of pasted evidence | The section's cited prose, plus `### Sources added` / `### Candidates discarded` blocks |
| `peer-reviewer` (Phase 7a, one per role, parallel, `standard`/`deep` only) | `.claude/agents/peer-reviewer.md` | The full assembled draft, `DRAFT PATH`, and one assigned lens (`domain-accuracy`, `methodology-rigor`, `clarity-completeness`, `devils-advocate`) -- never another reviewer's critique | A verdict (`ready` / `needs revision` / `reject`) plus severity-rated concerns |

No subagent ever writes to `content/dossiers/`. That is a rule stated
explicitly in `SKILL.md`, not an incidental property: each subagent's
context vanishes on return, so anything worth keeping has to be
transcribed by the orchestrator, in the same phase, before it moves on
-- a fourth Phase-2 packet sitting unread while a fifth is dispatched is
exactly how a discarded citekey's reasoning gets lost for good.

## 3. Why the two don't look the same

| | `textbook-chapter-writer` | `deep-research` |
|---|---|---|
| Number of contexts | One, for the whole run | One orchestrator + up to ~10 subagents in flight at once (concurrency-capped per `reference.md` §1), several times over across Phases 2/5/7 |
| Where the citekey invariant lives | Read once, from `AGENTS.md` | Restated locally inside each `.claude/agents/*.md` definition, since a subagent doesn't inherit `AGENTS.md` |
| How evidence reaches later steps | Stays in the one context that found it | Deliberately **not** pasted forward -- transcribed to the dossier, then handed to later subagents as a `dossier brief` pointer |
| What ends the run's growth | The chapter is written once, in the one context | The orchestrator's own context still only grows across all 7 phases -- the saving is in what it hands to *each subagent*, not in its own size |
| Citation stance | Optional -- a chapter with none is a complete, valid output | Mandatory -- every claim resolves to a real citekey or is stated as "not found in the corpus" |

Both skills obey the same router (`CLAUDE.md`) and the same hard rule
(never fabricate a citekey), and both write a dossier for the same
reason -- so a revision next month doesn't have to redo the judgment
this run already made. What differs is *where* that rule and that
judgment live at any given moment: in one growing context for
`textbook-chapter-writer`, or handed piece by piece into contexts that
are built, used once, and thrown away, for `deep-research`.
