# 📘 CLAUDE.md

This file is deliberately short. It is loaded into every session in this
repository, whichever task you are here for. It names the one rule that
binds every task and then sends you to the file that governs yours.

## 🧭 Which file governs you

Routing goes by what you are about to do, not by who you are. Someone who
unzipped a release, someone who cloned the repository, and someone who
`pip install`ed the package and ran `chitragupta init` all read the same
two files for drafting. Which file applies after that changes the moment
they start editing `chitragupta/`.

| If you are... | Read | Then stop |
| --- | --- | --- |
| **Drafting content** with this pipeline (a survey, thesis chapter, textbook chapter, tutorial, deep-research report) or revising one | **[AGENTS.md](AGENTS.md)** | That file and the skill you are running are the whole contract. You do not need anything below |
| **Changing this repository's own code**: anything under `chitragupta/`, `scripts/`, `tests/`, `bench/`, `.github/`, `assets/webapp/` | **`DEVELOPER-AGENTS.md`**, which governs, then **[docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md)** for what the code must look like | -- |
| **Changing this repository's prose**: `docs/`, `README.md`, or these files | `DEVELOPER-AGENTS.md` for the commit/PR conventions | -- |
| **In a `pip install`ed, `chitragupta init`-scaffolded project directory**, with no `chitragupta/`, `scripts/`, `tests/`, `bench/` or `.github/` to change (`chitragupta init` deliberately does not scaffold them; see [docs/PACKAGING.md](docs/PACKAGING.md)) | **[AGENTS.md](AGENTS.md)**. The drafting row above is your whole contract, same as anyone else | You have no `DEVELOPER-AGENTS.md` route here, and that is correct: nothing is missing. Changing the pipeline's own code means changing the git checkout it was installed from, which is a different project directory entirely |

Doing both in one session is normal, for example drafting with the
pipeline and then fixing a bug you hit. Re-read this table at the switch:
the developer rules do not apply to a draft, and the drafting rules do not
apply to `chitragupta/`.

[SOUL.md](SOUL.md) explains the reasons behind all of it on one page, and
it is the tie-breaker when two files seem to disagree.

## 🔑 The one rule that binds every task

> **A citekey may be used only if it appears in the human's own `.bib`
> export *and* was picked up into the ledger by a real parse of a real
> PDF.**

Never fabricate, guess, generate or rewrite a citekey: not in a draft,
not in a test fixture, not in an example in a doc. Fabricated placeholder
references have reached real published papers, and this project exists to
prevent that. [AGENTS.md](AGENTS.md) states the rule in operational terms;
[SOUL.md](SOUL.md) explains why it cannot bend.

## 💡 Why this file is a router and not the guidance itself

Three reasons, recorded so the next person does not merge it back into
one file:

1. **The two audiences need opposite things.** A drafting session should
   not carry the release process, the coverage bar and the module
   boundaries in its context, and a refactoring session should not carry
   the dossier format. Splitting by task limits each session's standing
   instructions to what applies to it.
2. **Everything ships.** `scripts/release.py` bundles every prose
   document (`AGENTS.md`, `DEVELOPER-AGENTS.md`, `SOUL.md`, `docs/`),
   because they cross-reference each other by name and dropping one
   leaves dangling links in the rest. The developer guidance therefore
   reaches a release consumer anyway. What the routing prevents is that
   guidance reaching a *drafting session*, and that is the distinction
   that matters.
3. **It has to degrade.** Different agents load different files:
   `CLAUDE.md`, `AGENTS.md`, or neither. This file therefore duplicates
   no guidance and imports nothing. Whichever of the two an agent picks
   up, it finds a pointer to the other by name instead of half a ruleset.
   [AGENTS.md](AGENTS.md) carries the same pointer in the other
   direction, and has since before this file existed.
