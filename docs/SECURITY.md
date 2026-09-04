# 🔐 Security architecture

Status: **reference.** Written 2026-09-01. Updated 2026-09-02, adding
the SonarQube scan action and its token to the release controls -- a
credential-bearing third-party action the first version of that section
did not name.

How chitragupta protects the locally managed research corpus and its
derived artefacts, where its trust boundaries are, and what remains the
operator's responsibility.

**Written for** users operating a corpus and developers changing the
pipeline or its release automation.

**Assumed:** [ARCHITECTURE.md](ARCHITECTURE.md) for the four-layer design,
[CLI.md](CLI.md) for commands, and [CONFIG.md](CONFIG.md) for settings.
**Not covered here:** a general system overview, an organisational
security policy, or a guarantee that untrusted documents and tools are
safe to execute.

## 🧭 Table of contents

- [Security goals and explicit non-goals](#-security-goals-and-explicit-non-goals)
- [Assets and trust boundaries](#-assets-and-trust-boundaries)
- [Controls in the implementation](#-controls-in-the-implementation)
- [Residual risks and operating guidance](#-residual-risks-and-operating-guidance)
- [Safe operating practices](#-safe-operating-practices)
- [Reporting a suspected security issue](#-reporting-a-suspected-security-issue)

## 🎯 Security goals and explicit non-goals

Chitragupta is a **local-first** research-corpus pipeline. It reads the
BibTeX and PDF files that you manage, writes derived artefacts below the
configured content directory, and uses locally installed tools such as
`pdftotext`, Pandoc, and TeX Live when a command needs them.

Its main security goals are to keep ordinary pipeline processing bounded
to the configured project, preserve the provenance of citekeys, avoid
shell interpolation when it invokes local tools, and limit credentials in
the release path.

This project does **not** claim to provide:

- a sandbox for PDFs, TeX, Pandoc, Docling, or other local dependencies;
- malware detection, document sanitisation, or protection against a
  malicious parser or renderer;
- validation that a cited paper supports the surrounding claim;
- protection from users, processes, or administrators that can already
  read or modify the project directory, its configuration, its inherited
  environment, or executables on `PATH`;
- perfect protection against filesystem races, compromised dependencies,
  or host-level compromise; or
- a substitute for human review of generated research prose.

The citation gate is deliberately narrow: it verifies that a citekey in
a draft exists in the synced ledger. It does not determine whether the
citation is relevant, accurate, or sufficient. The advisory review tools
and, ultimately, the author remain responsible for those judgements; see
[ARCHITECTURE.md](ARCHITECTURE.md#-what-this-architecture-does-not-do).

## 🧱 Assets and trust boundaries

| Asset | Why it matters | Trust boundary / owner |
| --- | --- | --- |
| `papers/bibliography.bib` and referenced PDFs | Source bibliography, citekeys, metadata, and source documents | User-managed local input; review imported exports and PDFs before choosing to process them |
| `config.toml` and environment variables | Select the project, bibliography, content directory, parser, and other runtime behaviour | Trusted operator configuration; environment variables override TOML values |
| `content/ledger.sqlite` | The synced set of citekeys that the gate treats as authoritative | Pipeline-managed local state under the configured content root |
| Parsed-text, Docling, Chroma, and topic caches | Derived corpus text, embeddings, passages, and topic artefacts | Local derived data; may contain information extracted from the corpus |
| Drafts, dossiers, renders, and review reports | Research drafts and their supporting records | User-reviewed work product; generated prose is not automatically authoritative |
| Local executables and libraries | `pdftotext`, Pandoc, `pdflatex`, Docling, Python packages, and GPU tooling process corpus data | Trusted local toolchain chosen and maintained by the operator |
| GitHub Actions and PyPI release artefacts | Build, documentation, release archives, wheels, and packages | Repository-maintainer and CI trust boundary |
| Claude Code or another external AI session | A drafting session can receive corpus-derived context or user instructions | Optional external-service boundary; not required by the corpus pipeline |

The deterministic corpus layer does not fetch papers or call an LLM API.
It processes the bibliography and attachment paths you provide. The
optional drafting workflow uses Claude Code skills, so any information
placed in that session is subject to the AI service, account, client, and
network controls selected by the operator. The repository itself contains
no LLM API key requirement.

## 🛡 Controls in the implementation

### Citekey provenance gate

`python -m chitragupta.draft gate <draft>` reads known citekeys from
`content/ledger.sqlite` and refuses citations that no corpus sync
recorded. The bibliography is the only citekey source: the pipeline does
not generate, rename, or fetch citekeys.

Before sync creates derived filenames, `chitragupta/bib_reader.py`
rejects citekeys unsafe for filesystem use. An unsafe entry is skipped
with a warning rather than silently rewritten. The same validator
(`chitragupta/citekey_safety.py`) also guards the review layer's reads:
citekeys there are extracted from a draft, not the bib file, so a draft
citing `\citep{../../secret}` must -- and does -- resolve to no source
text rather than to a file outside the content tree.

The drafting skills run the gate before presenting a draft. A Claude Code
PostToolUse hook also runs it after writes under `content/drafts/`.
Because this is a post-write check, an invalid draft can exist on disk
until it is corrected. Run the gate yourself before sharing, rendering,
committing, or relying on a draft. [HOOKS.md](HOOKS.md) documents the
hook boundary and its launcher checks.

### Content-root containment and symlink-aware checks

Commands that accept draft paths use
`config.require_inside_content()` before reading or writing them.
`chitragupta/config_path.py` resolves both the candidate path and
`CONTENT_DIR` before comparing them. This makes `..` components and
existing symlinks answer for their actual destination rather than their
textual spelling.

The rendering and review paths apply additional output-directory checks
so a configured or encountered symlink cannot redirect their derived
output outside the resolved content root. These checks define the
configured content directory as the pipeline's working boundary; they
are not an access-control system, and path validation cannot eliminate a
race with a process that can alter the filesystem concurrently.

### Safer archive restore

`chitragupta.dossier` exports and restores draft records as `tar.gz`
bundles. Restore is a dry run unless the operator supplies `--force`.

Before extraction, `chitragupta/dossier/_archive.py` refuses the entire
archive if a member is not a regular file or directory, is absolute,
contains `..`, or is outside the allowlisted top-level roots:
`drafts/`, `dossiers/`, `rendered/`, and `review/`. Extraction also uses
Python's `tarfile` `filter="data"` protection. These checks resist common
traversal, link, device-node, and unexpected-root archive attacks; they
do not make restored Markdown, TeX, PDFs, or other regular files
semantically trustworthy.

### Parameterised local-tool invocation

The Python implementation invokes local commands through argument
vectors, including the PDF extractor and the Pandoc command built by the
render module. The repository has no `subprocess` call with `shell=True`.

This avoids passing corpus paths and tool arguments through a shell
parser. It does not protect against vulnerabilities or unsafe behaviour
in the called executable, a malicious executable earlier on `PATH`, or
dangerous content interpreted by the toolchain. The PDF and rendering
sections of [CLI.md](CLI.md) identify which commands require local tools.

### Local-first corpus processing

`chitragupta corpus sync` reads a user-supplied BibTeX export and its
referenced local PDFs. It writes the ledger and parsed text locally. It
does not download papers, crawl a source, or call an LLM API.

The optional enrichment layer also processes the same corpus locally, but
some optional model dependencies may download models on first use. Review
the model and package source before enabling that layer. See
[CONFIG.md](CONFIG.md#-choosing-an-embedding-model) and
[CONFIG.md](CONFIG.md#-choosing-an-entailment-model).

### One writer at a time

`sync` and `chitragupta enrich` use the same SQLite-backed mutex at
`content/pipeline.lock.db`. The lock holds `BEGIN IMMEDIATE`; a
competing writer exits with code `2` rather than interleaving writes.
Read-only operations deliberately remain available while a writer runs.

This prevents the pipeline's own writers from overlapping on a local
filesystem. SQLite locking is not reliable on network filesystems, so
this control assumes `content/` is local storage. Treat a local
filesystem as an operational requirement for writer safety, not as an
optional tuning choice.
[ARCHITECTURE.md](ARCHITECTURE.md#-one-writer-at-a-time) describes the
lock and its scope, and
[Operational requirement: local filesystem for runlock](#operational-requirement-local-filesystem-for-runlock)
states the deployment requirement and mitigations.

### Dependency and release controls

The checkout uses `poetry.lock` to fix resolved Python package versions
and hashes. The install path documents when it must allow a source
archive, while the documentation workflow uses wheels only where that is
compatible with its dependency set.

The workflows use explicit permissions, scoped per workflow or per job
depending on the file. `docs.yml` grants `contents: read` on the `build`
job and `pages: write` + `id-token: write` only on `deploy`. `ci.yml`
grants workflow-level `contents: read`. `release.yml` grants
workflow-level `contents: write`, then narrows the `publish-pypi` job to
`id-token: write` only. PyPI Trusted Publishing exchanges that OIDC token
for a short-lived token instead of storing a long-lived PyPI API token.

Sensitive third-party actions that publish releases, publish to PyPI, or
upload external analysis are commit-SHA pinned. There are **four**:
`softprops/action-gh-release`, `pypa/gh-action-pypi-publish`,
`codecov/codecov-action`, and `SonarSource/sonarqube-scan-action`. A tag
can be moved to point at different code, which is the whole reason;
`ci.yml`'s own comment at the Sonar step records it, and records why
`actions/checkout` is deliberately left on `@v4` at every call site --
it is GitHub's own action, and Sonar's S7637 did not flag it. So not
every action here is SHA-pinned, and that is a decision rather than an
oversight.

**Two of the four consume a long-lived repository secret** rather than
an OIDC token exchanged per run: `secrets.CODECOV_TOKEN` and
`secrets.SONAR_TOKEN`, both in `ci.yml`. Those two are the part of this
section worth re-auditing when a maintainer leaves, when a service is
dropped, or on any schedule your organisation applies to third-party
credentials -- they cannot expire on their own the way the PyPI publish
path's token does, which is why that path deliberately has no
equivalent.

## ⚠ Residual risks and operating guidance

### PDFs and the local toolchain are trusted execution dependencies

A PDF is data to chitragupta, but it is input to substantial native and
Python parsing stacks. Pandoc and TeX process generated rendering inputs.
Keep Poppler, Pandoc, TeX Live, Python, and optional enrichment
dependencies current through the package-management process appropriate
to your host.

Do not process a suspicious corpus with elevated privileges. For material
from an untrusted source, prefer a separate unprivileged account or an
isolated disposable environment that meets your organisation's operating
requirements. This project does not supply that isolation.

### Local permissions remain decisive

The pipeline runs with the permissions of the invoking account. Restrict
access to the project, bibliography, PDFs, `content/`, logs, backups, and
archives according to the sensitivity of the corpus. Check ownership and
permissions after running installation or scheduled jobs, especially when
using `sudo`.

Backups and `dossier export` bundles can contain drafts, review reports,
and rendered outputs. Protect them with the same care as the original
corpus.

### Archive restore denial-of-service limits

`dossier restore` validates archive member type and path before
extraction. It refuses links, device nodes, traversal paths, and members
outside `drafts/`, `dossiers/`, `rendered/`, and `review/`.

Those checks reduce traversal-style risk, but the current implementation
does **not** enforce hard limits on member count, per-member size, or
total extracted bytes. A path-valid archive can still consume excessive
disk space, inode budget, memory, or runtime when restored with
`--force`.

Operator guidance: restore only trusted archives, keep the default dry
run first, and preflight unusually large bundles before extraction. When
possible, restore in a quota-limited workspace or disposable environment
so an oversized archive cannot exhaust shared host resources.

### Operational requirement: local filesystem for runlock

The runlock (`content/pipeline.lock.db`) and the ledger depend on SQLite
locking semantics that are reliable on local filesystems. Treat local
storage for `content/` as a deployment requirement for any writer
workflow (`sync`, `enrich`, and scheduled runs).

On network or synchronised filesystems (for example NFS, SMB, or
cloud-sync mounts), lock visibility and ordering are not reliable. That
can allow overlapping writers, partial-read races, and inconsistent
pipeline state despite the lock file being present.

Mitigation options: keep the writable `content/` tree on local disk; use
one designated writer host and replicate outputs afterwards; or serialize
writes through external orchestration while avoiding shared writable
network mounts for the active pipeline state.

### Configuration and environment are part of the trust boundary

`CONFIG_PATH`, `CHITRAGUPTA_PROJECT`, `BIB_FILE`, `CONTENT_DIR`, and the
other documented setting environment variables can alter which files are
read or written and which optional components run. Environment values
override `config.toml`.

Use an explicit, minimal environment for cron, systemd, CI, or other
automation. Do not run scheduled jobs from a shell profile that imports
unreviewed environment variables. Limit write access to `config.toml` and
avoid pointing `CONTENT_DIR` at a shared or unintended location.
[CONFIG.md](CONFIG.md#-how-configuration-is-loaded) gives the precedence
rules.

### Generated drafting content needs human review

The citation gate proves citekey membership in the ledger, not factual
correctness, citation entailment, copyright compliance, or the absence of
harmful wording. Review generated drafts, citations, quotations,
references, and final rendered output before publication. The review
commands are evidence for a human decision and deliberately do not block
a draft.

### Optional external AI sessions may create egress

The corpus, gate, rendering, and review commands do not require an LLM
API key. If you use the shipped Claude Code skills or another AI-assisted
workflow, the session itself may send prompts, excerpts, paths, or other
context to an external service depending on your client and settings.

Before using AI assistance with confidential, licensed, personal, or
export-controlled research material, assess the service's data-handling
terms and your organisation's rules. Minimise the context shared, use an
approved account and client configuration, and choose a local workflow
when external processing is not acceptable.

## ✅ Safe operating practices

1. Keep `papers/`, `content/`, `config.toml`, logs, and backups under
   permissions appropriate for the corpus. Run the pipeline as an
   unprivileged user.
2. Treat imported BibTeX exports, PDFs, archives, custom CSL files, TeX,
   and configuration overrides as inputs that require review.
3. Keep `content/` on a local filesystem. Do not run concurrent writers
   against an NFS, SMB, cloud-synchronised, or otherwise shared content
   directory.
4. Let `sync` and `enrich` finish; treat exit code `2` as a competing
   writer rather than a reason to bypass the lock. Investigate repeated
   failures and the pipeline log rather than deleting lock files.
5. Use `dossier restore` without `--force` first. Review the planned new
   and overwritten files before permitting the extraction.
6. Install and update dependencies from the reviewed lockfile or released
   package path. Review dependency, action, and workflow changes as
   security-sensitive changes.
7. Run `python -m chitragupta.draft gate <draft>` immediately before
   sharing or publishing a draft. Then perform the relevant human review
   and advisory checks.
8. Use the project's normal documented release workflow. Do not add PyPI
   API tokens to repository files, configuration, or CI logs.
9. For scheduled runs, use explicit absolute paths, an explicit working
   directory, and a minimal service environment. Follow the examples in
   [CLI.md](CLI.md#-running-sync-on-a-schedule).

## 📣 Reporting a suspected security issue

Do not include credentials, private PDFs, unpublished drafts, personal
data, or a working exploit in a public issue.

Check the repository's GitHub **Security** page and any current
project-maintainer guidance for a private reporting channel, and use
that channel when it is available. Note that GitHub reads
`docs/SECURITY.md` -- this file -- as the repository's security policy,
so the Security page shows you this text. Do not read finding it there
as evidence that a private channel exists; the presence of a policy and
the presence of a channel are separate facts. If no private channel is
published,
disclose only the minimum non-sensitive information needed to request a
private conversation; do not assume an email address, response time,
bounty, or coordinated-disclosure policy that the project has not
published.

A useful initial report states the affected released version or commit,
operating system, command or component, expected and observed behaviour,
security impact, and safe reproduction steps. Maintainers determine
triage, remediation, release, and disclosure arrangements.
