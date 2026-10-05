# 🧳 Backing up, restoring and moving a project

Status: **reference.** Written 2026-10-05, for 6.133.0.

**Written for** anyone who wants a copy of their drafts somewhere safe,
needs last month's draft back, or is moving a project to a new directory,
a new computer, or into a container. **Assumed:** a working project, set
up as [CLI.md](CLI.md#-installing) describes. **Not covered here:** the
Poetry-to-uv lockfile change, which has its own page,
[UV-MIGRATION.md](UV-MIGRATION.md), and has nothing to do with your data.

## 🧭 Table of contents

- [The short answer](#-the-short-answer)
- [What a project holds](#-what-a-project-holds)
- [Backing up drafts: dossier export and restore](#-backing-up-drafts-dossier-export-and-restore)
- [A full backup](#-a-full-backup)
- [The ledger path change in 6.133.0](#-the-ledger-path-change-in-61330)
- [Moving to another directory](#-moving-to-another-directory)
- [Moving to another computer](#-moving-to-another-computer)
- [Sharing a project between a container and the host](#-sharing-a-project-between-a-container-and-the-host)
- [When something looks wrong after a move](#-when-something-looks-wrong-after-a-move)

## ⚡ The short answer

- To keep your writing safe, run `chitragupta draft dossier export`. It
  writes one `.tar.gz` of your drafts, their dossiers and their review
  reports. `chitragupta draft dossier restore <archive>` puts them back.
  Restore only writes when you add `--force`.
- To move a project, copy the whole project directory with a tool that
  keeps file modification times (`rsync -a`, `cp -a` or `tar`). Then run
  `chitragupta corpus sync` in the new place. Since 6.133.0 that sync
  re-parses nothing.
- On a new computer, install chitragupta first, run `chitragupta doctor`,
  and check two things the copy cannot fix for you: absolute paths in
  `config.toml`, and absolute PDF paths inside `bibliography.bib`.

## 📦 What a project holds

A project is the directory that holds `config.toml`. Everything
chitragupta reads or writes for that project is under it, unless your
`config.toml` points somewhere else. The table sorts the contents by what
losing them costs you.

| Path | What it is | If you lose it |
| --- | --- | --- |
| `config.toml` | Your settings | Copy `config.toml.example` again and redo your edits |
| `papers/bibliography.bib` and its PDF folder | Your reference manager's export. The source of truth for every citekey | Export it again from your reference manager. chitragupta never writes it |
| `content/drafts/` | Your drafts | Lost, unless you have a bundle or a backup |
| `content/dossiers/` | The working state behind each draft: scope, kept evidence, rejected candidates, revision log | Lost. A reviser can still read the draft but no longer knows how it was made |
| `content/specs/` | A book's outline and its sign-off record | Lost, and a dossier bundle does not include it |
| `content/review/` | Review reports and the record of agenda items you accepted | Rerun the review aids. Accepted items come back as open items you judge again |
| `content/acronyms.toml`, `content/seed_topics.toml`, `content/verbatim_allowlist.toml`, `content/tldr/` | Files you wrote or approved by hand | Lost, and a dossier bundle does not include them |
| `content/rendered/` | PDFs and `.tex` built from your drafts | Run `chitragupta draft render` again |
| `content/ledger.sqlite` | What `sync` knows about each paper | Run `chitragupta corpus sync` |
| `content/parsed/` | The text extracted from each PDF | `corpus sync` parses every PDF again. With Docling the new text is not always byte-identical to the old |
| `content/docling/`, `content/docling_cache.json`, `content/chroma/`, topic files | The `enrich` layer's outputs | Run `chitragupta enrich` again. Slow on a large library |
| `content/retrieval_index.json`, `content/retrieval_passage_index.json`, `content/overlap/` | Search and overlap caches | Nothing to do. They rebuild the next time they are needed |
| `content/pipeline.lock.db` and its `.holder` file | The lock that stops two writers running at once | Nothing. The lock lives in the running process, not the file, so a copy is harmless but useless |
| `logs/`, `.venv-full/` | Logs and the Python environment of this machine | Do not copy them. Make a new venv on the new machine |

## 💾 Backing up drafts: dossier export and restore

`content/` is not in version control, on purpose: dossiers quote
copyrighted papers, and a draft is your own work to keep where you choose.
The bundle commands give you a backup without that.

```bash
# Everything: every draft, its dossier and its review reports
chitragupta draft dossier export

# One draft or one topic, plus its rendered PDFs
chitragupta draft dossier export digital-twins-for-software-engineers --with-rendered

# Choose the archive's name and place
chitragupta draft dossier export --out ~/backups/drafts.tar.gz

# Restore: the first command only reports, the second writes
chitragupta draft dossier restore drafts-all-2026-10-05.tar.gz
chitragupta draft dossier restore drafts-all-2026-10-05.tar.gz --force
```

`python -m chitragupta.draft dossier ...` does the same thing, if you
run the module rather than the console script.

### What goes in the bundle

- `drafts/` and `dossiers/`.
- `review/`, but only its `.md` and `.json` files. That includes each
  draft's `<stem>.accepted.json`, the record of agenda items you
  accepted.
- With `--with-rendered`, also `rendered/` and the rest of `review/`
  (its `.tex` and `.pdf` files). These are large.

Archive paths are relative to `content/`. A bundle therefore restores
correctly into a project whose `[content].dir` has a different name.

The default archive name is `drafts-<names>-<date>.tar.gz`, or
`drafts-all-<date>.tar.gz` when you name nothing, written to the current
directory.

### What stays out of the bundle

- `content/ledger.sqlite`, `content/parsed/` and the `enrich` outputs.
  They can all be made again from your PDFs.
- `papers/bibliography.bib` and the PDFs. That export belongs to your
  reference manager, so back it up wherever you back up your reference
  manager.
- `content/specs/`, `content/acronyms.toml`, `content/seed_topics.toml`,
  `content/verbatim_allowlist.toml`, `content/tldr/` and `config.toml`.
  Keep these with a [full backup](#-a-full-backup).

If you restore a bundle onto a machine that has never run `sync`, the
drafts and dossiers are all there and readable, but the citation gate
cannot confirm any citekey until `sync` has built the ledger, because it
refuses a citekey it cannot see.

### How restore protects you

- Without `--force` it only reports. The report lists the new files and
  the files it would overwrite. Read it first: overwriting is how a
  restore loses a newer copy of a draft.
- If any entry looks unsafe, it refuses the whole archive and writes
  nothing. An entry is unsafe if it is a link or a device file, if its
  path is absolute or climbs out with `..`, or if it is outside
  `drafts/`, `dossiers/`, `rendered/` and `review/`. You never end up
  with a partial restore that looks complete.
- It sets no limit on an archive's size or number of files, so restore
  only archives you made or trust. [SECURITY.md](SECURITY.md#archive-restore-denial-of-service-limits)
  has the details.

## 🗄 A full backup

A full backup keeps the whole project, so a restored copy works without
parsing your library again. Copy the project directory and keep the file
modification times:

```bash
# from the directory that contains the project
tar --exclude='project/.venv-full' \
    --exclude='project/logs' \
    --exclude='project/content/pipeline.lock.db*' \
    --exclude='project/content/.pipeline.lock.db*' \
    -czf project-backup-2026-10-05.tar.gz project
```

Replace `project` with your directory's name. Leave out
`papers/` if your reference manager already backs it up.

Make the backup when no `sync`, `enrich` or `render` is running, so
the ledger is not caught halfway through a write.

## 🔄 The ledger path change in 6.133.0

The ledger records, for each paper, where its parsed text and its PDF are.
Up to 6.132.0 it stored those as full paths on the machine that ran
`sync`, such as `/home/ana/thesis/content/parsed/smith2024.txt`.
Every reader checks that a path from the ledger lands inside
`content/parsed/` (for text) or the bib file's directory (for PDFs).
After a move, the old full paths pointed somewhere else, every row failed
that check, and `sync` printed `WARNING refusing ...` and parsed the
whole library again.

From 6.133.0 the ledger stores both paths relative to those directories:
`parsed_path` is just `<citekey>.txt`, and `pdf_path` is relative to the
directory the bib file is really in, after following symlinks.

You do not run a migration step:

- The first time a writer opens an older ledger (normally your next
  `chitragupta corpus sync`), every old `parsed_path` is rewritten to
  `<citekey>.txt`. This works even if the project has already moved,
  because the file name depends only on the citekey.
- The same `sync` rewrites every old `pdf_path` as it reads the bib file.
- Read-only commands (`search`, `evidence`, `tldr`) keep working on an
  older ledger in the meantime. They read an old full path where it
  still points, and ignore it with a warning where it no longer does.
- The search caches key on the stored path text, so each rebuilds once
  after the upgrade.

Two related fixes shipped with it. A relative `CHITRAGUPTA_PROJECT`
(such as `../thesis`) is now resolved from the directory you set it in,
so every later command finds the same project. And a project path that
contains `?`, `#` or `%` now works for read-only commands, which used to
open the wrong file and report the ledger as out of date.

> [!IMPORTANT]
> Every machine and container that shares one ledger should run 6.133.0
> or later. An older release reads `smith2024.txt` relative to whatever
> directory it runs in, finds nothing, and its `sync` writes full paths
> back into the ledger.

## 📁 Moving to another directory

On the same computer:

1. Let any running `sync`, `enrich` or `render` finish.
2. Move or copy the project directory, keeping modification times:
   `mv thesis ~/work/thesis`, or `rsync -a thesis/ ~/work/thesis/`.
3. Open `config.toml` in the new place and look at the path settings:
   `[bib].path`, `[content].dir`, `[render].csl`, `[style].vale_config`,
   `[style].acronyms` and `[enrich].keywords_path`. A relative value
   (the default, such as `papers/bibliography.bib`) moves with the
   project. An absolute value that pointed into the old directory has
   to be edited.
4. If you set `CHITRAGUPTA_PROJECT`, `BIB_FILE` or `CONTENT_DIR` in your
   shell profile or in a launcher, update those as well. Environment
   variables win over `config.toml`.
5. Run `chitragupta corpus sync` from inside the new directory. Expect
   `0 parsed` and every document `unchanged`.

If you copied without keeping modification times, `sync` checks every
PDF's contents again (a SHA-256 hash) before it decides that nothing
changed. That takes longer, but it still re-parses nothing. The `enrich`
layer's Docling cache is stricter: it compares the PDF's modification
time, so a copy that lost them makes the next `enrich` parse every PDF
with Docling again.

Renaming `content/` works the same way: rename the directory, set
`[content].dir` to the new name, and run `sync`.

## 💻 Moving to another computer

### 1. Install chitragupta on the new computer

Follow [CLI.md](CLI.md#-installing): make a fresh `.venv-full`, then
`pip install chitragupta-cli` (or the `[enrich]` extra, if you use the
`enrich` layer). On Windows, read [WINDOWS.md](WINDOWS.md) first. WSL2
is the easier route there, and the project belongs on the WSL2
filesystem, not under `/mnt/c/`. Install the same chitragupta version as
the old computer, or a newer one.

Do not copy `.venv-full` from the old machine. A virtual environment
records the absolute path of the Python that made it, and it breaks when
moved.

### 2. Copy the project

Bring the whole project directory across, keeping modification times.
Over the network:

```bash
rsync -a --exclude .venv-full --exclude logs \
      --exclude 'content/pipeline.lock.db*' --exclude 'content/.pipeline.lock.db*' \
      old-machine:thesis/ ~/thesis/
```

Or carry a [full backup](#-a-full-backup) and unpack it with
`tar -xzf`, which keeps the times stored in the archive.

If you only want your writing and are happy to rebuild the corpus, a
dossier bundle is enough. Run `chitragupta init` on the new computer,
copy `config.toml`, `papers/` and `content/specs/` across, restore the
bundle with `--force`, and run `sync`. Parsing and `enrich` then run
from scratch.

### 3. Check the paths the copy cannot fix

In `config.toml`, check the same six path settings as in
[Moving to another directory](#-moving-to-another-directory). An
absolute path from the old machine, such as
`/home/ana/Zotero/export.bib`, does not exist on the new one.

Then check the PDF paths inside `bibliography.bib`. Each entry's `file` field
says where its PDF is. chitragupta only reads a PDF that is inside the
bib file's own directory (or a folder below it). A relative path such as
`files/12/smith2024.pdf` moves with `papers/` and keeps working. An
absolute path from the old machine, such as
`/home/ana/Zotero/storage/ABCD1234/smith2024.pdf`, is outside the new
`papers/`. chitragupta refuses it without opening it, `sync` reports the
entry as having no PDF, and the run exits with code 3.

If your export holds absolute paths, the clean fix is to export again on
the new computer with the PDFs placed beside the bib file.
[ZOTERO.md](ZOTERO.md) shows the export settings that write relative
paths, and why the companion folder must keep its name. The other two
options are in [CLI.md](CLI.md): point `[bib].path` at the directory the
PDFs are really in, or remove the `file` field.

### 4. Check the machine

```bash
cd ~/thesis
chitragupta doctor
```

`doctor` reports missing programs (pdftotext, pandoc, LuaLaTeX, Vale), a
missing `enrich` extra, a PyTorch build that does not match the GPU, and
agent hooks that cannot start, and exits normally either way. Install
what it names before you need it: `sync` with the default parser
needs pdftotext, and `render` needs pandoc and LuaLaTeX.

### 5. Sync and look at the result

```bash
chitragupta corpus sync
```

With the project copied whole and its times kept, expect `0 parsed`.
Then check one thing that depends on the parsed text, for example
`chitragupta draft retrieve search "a phrase from your field"`, and run
`chitragupta draft dossier status --all` to see whether any draft's
evidence moved.

If `[parser].backend` is `docling` and the new machine re-parses a PDF,
the new text can differ slightly from the old. A quote kept in a dossier
still has its source, but the review aids may report it at a different
place. Copying `content/parsed/` across, rather than re-parsing, avoids
this.

## 🐳 Sharing a project between a container and the host

The Docker setup in [DOCKER.md](../DOCKER.md) mounts your project at
`/workspace` inside the container, so the same project has one path on
the host and another inside. Since 6.133.0 that is fine: the ledger
stores nothing that depends on where the project is mounted, so a
`sync` on the host followed by a `search` in the container (or the other
way round) finds the same text and parses nothing again.

Two conditions:

- The host and the container must both run 6.133.0 or later (see
  [above](#-the-ledger-path-change-in-61330)).
- The compose file mounts `papers/` read-only at `/workspace/papers`, so
  `[bib].path` has to stay inside the project, which is the default.

## 🩺 When something looks wrong after a move

| What you see | Why | What to do |
| --- | --- | --- |
| `WARNING refusing ...: it does not land inside ...` for every paper | An older release wrote the ledger, and a read-only command ran before any `sync` | Run `chitragupta corpus sync` once on 6.133.0 or later |
| Every document is re-parsed after a move | The machine runs a release older than 6.133.0, or another machine sharing the ledger does | Upgrade every machine, then `sync` |
| Entries reported as having no PDF, `pdf_outside_papers`, exit code 3 | The bib file's `file` fields hold absolute paths from the old machine | Export the bib file again with relative paths (see [step 3](#3-check-the-paths-the-copy-cannot-fix)) |
| `sync` takes as long as hashing the whole library, but parses nothing | The copy did not keep modification times | Nothing; the next `sync` is fast again |
| `enrich` runs Docling on every PDF again | The copy did not keep the PDFs' modification times | Let it run, or copy again with `rsync -a` |
| `No config file` on import | The command ran outside the project, so chitragupta did not find `config.toml` | `cd` into the project, or set `CHITRAGUPTA_PROJECT` |
| The citation gate cannot confirm citekeys after a restore | `sync` has not built the ledger on this machine yet | Run `chitragupta corpus sync` |
