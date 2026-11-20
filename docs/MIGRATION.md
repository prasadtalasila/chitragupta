# 🧳 Backing up, restoring and moving a project

Status: **how-to.**

For keeping a copy of your drafts safe, getting last month's draft
back, or moving a working project ([CLI.md](CLI.md#-installing)) to a
new directory, computer or container.

## ⚡ The short answer

- `chitragupta draft dossier export` writes one `.tar.gz` of your
  drafts, their dossiers and review reports;
  `chitragupta draft dossier restore <archive> --force` puts them back.
- To move a project, copy the whole directory keeping file modification
  times (`rsync -a`, `cp -a` or `tar`), then run `chitragupta corpus
  sync` there. It re-parses nothing.
- On a new computer, install chitragupta, run `chitragupta doctor`, and
  check absolute paths in `config.toml` and absolute PDF paths in
  `bibliography.bib`.

## 📦 What a project holds

A project is the directory that holds `config.toml`, and everything
chitragupta reads or writes is under it unless `config.toml` points
elsewhere. `content/` here means whatever `[content].dir` (or the
`CONTENT_DIR` environment variable) names, `content` by default. The
ledger stores parsed-text paths relative to `parsed/` and PDF paths
relative to the bib file's directory, so a moved project finds every
file without re-parsing. The table sorts the contents by what losing
them costs.

| Path | What it is | If you lose it |
| --- | --- | --- |
| `config.toml` | Your settings | Copy `config.toml.example` again and redo your edits |
| `papers/bibliography.bib` and its PDF folder | Your reference manager's export, the source of truth for every citekey | Export it again. chitragupta never writes it |
| `content/drafts/` | Your drafts | Lost, without a bundle or backup |
| `content/dossiers/` | Each draft's scope, kept evidence, rejected candidates and revision log | Lost. A reviser no longer knows how the draft was made |
| `content/specs/` | A book's outline and sign-off record | Lost; not in a dossier bundle |
| `content/review/` | Review reports and accepted agenda items | Rerun the review aids; accepted items come back open |
| `content/acronyms.toml`, `content/seed_topics.toml`, `content/verbatim_allowlist.toml`, `content/tldr/` | Files you wrote or approved by hand | Lost; not in a dossier bundle |
| `content/rendered/` | PDFs and `.tex` built from your drafts | Run `chitragupta draft render` again |
| `content/ledger.sqlite` | What `sync` knows about each paper | Run `chitragupta corpus sync` |
| `content/parsed/` | The text extracted from each PDF | `corpus sync` re-parses; Docling's new text may differ slightly |
| `content/docling/`, `content/docling_cache.json`, `content/chroma/`, topic files | The `enrich` layer's outputs | Run `chitragupta enrich` again (slow) |
| `content/retrieval_index.json`, `content/retrieval_passage_index.json`, `content/overlap/` | Search and overlap caches | Nothing; they rebuild when needed |
| `content/pipeline.lock.db` and its `.holder` file | The lock that stops two writers at once | Nothing; the lock lives in the process, so a copy is useless but harmless |
| `logs/`, `.venv-full/` | This machine's logs and Python environment | Do not copy; make a new venv |

## 💾 Backing up drafts: dossier export and restore

`content/` is deliberately not in version control: dossiers quote
copyrighted papers, and a draft is yours to keep where you choose. The
bundle commands give you a backup instead.

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

### What goes in the bundle

`drafts/`, `dossiers/` and the `.md` and `.json` files of `review/`
(each draft's `<stem>.accepted.json` included). `--with-rendered` adds
`rendered/` and the rest of `review/`, which are large. Paths are
relative to `content/`, so a bundle restores into a project whose
`[content].dir` has another name. The default name is
`drafts-<names>-<date>.tar.gz`, or `drafts-all-<date>.tar.gz`, in the
current directory.

### What stays out of the bundle

- `content/ledger.sqlite`, `content/parsed/` and the `enrich` outputs,
  which can be made again from your PDFs.
- `papers/bibliography.bib` and the PDFs, which belong with your
  reference manager's backup.
- `content/specs/`, `content/acronyms.toml`, `content/seed_topics.toml`,
  `content/verbatim_allowlist.toml`, `content/tldr/` and `config.toml`.
  Keep these with a [full backup](#-a-full-backup).

On a machine that has never run `sync`, a restored draft is readable,
but the citation gate cannot confirm any citekey until `sync` has built
the ledger.

### How restore protects you

- Without `--force` it only lists the new files and the files it would
  overwrite. Read it first: overwriting is how a restore loses a newer
  draft.
- If any entry is a link or device file, has an absolute path, climbs
  out with `..`, or lies outside `drafts/`, `dossiers/`, `rendered/` and
  `review/`, it refuses the whole archive and writes nothing.
- It sets no limit on an archive's size or file count, so restore only
  archives you made or trust ([SECURITY.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/SECURITY.md#archive-restore-denial-of-service-limits)).

## 🗄 A full backup

A full backup keeps the whole project, so a restored copy needs no
re-parse. Keep file modification times:

```bash
# from the directory that contains the project
tar --exclude='project/.venv-full' \
    --exclude='project/logs' \
    --exclude='project/content/pipeline.lock.db*' \
    --exclude='project/content/.pipeline.lock.db*' \
    -czf project-backup-2026-10-05.tar.gz project
```

Replace `project` with your directory's name; leave out `papers/` if
your reference manager backs it up. Back up while no `sync`, `enrich`
or `render` is running, so the ledger is not caught mid-write.

## 📁 Moving to another directory

On the same computer:

1. Let any running `sync`, `enrich` or `render` finish.
2. Move or copy the directory keeping modification times:
   `mv thesis ~/work/thesis` or `rsync -a thesis/ ~/work/thesis/`.
3. In the new `config.toml`, check `[bib].path`, `[content].dir`,
   `[render].csl`, `[style].vale_config`, `[style].acronyms` and
   `[enrich].keywords_path`. A relative value (the default) moves with
   the project; an absolute one into the old directory must be edited.
4. Update `CHITRAGUPTA_PROJECT`, `BIB_FILE` or `CONTENT_DIR` if you set
   them in a shell profile or launcher; they win over `config.toml`.
5. Run `chitragupta corpus sync` inside the new directory. Expect
   `0 parsed` and every document `unchanged`.

If the copy lost modification times, `sync` hashes every PDF (SHA-256)
before deciding nothing changed: slower, but no re-parse. The `enrich`
Docling cache compares modification times, so it re-parses every PDF.

To rename `content/`, rename the directory, set `[content].dir`, and
run `sync`.

## 💻 Moving to another computer

### 1. Install chitragupta on the new computer

Follow [CLI.md](CLI.md#-installing): make a fresh `.venv-full` and
`pip install chitragupta-cli` (with the `[enrich]` extra if you use it),
at the old computer's version or newer. On Windows, read
[WINDOWS.md](WINDOWS.md) first; WSL2 is easier, with the project on the
WSL2 filesystem, not under `/mnt/c/`. Do not copy `.venv-full`: a venv
records its Python's absolute path and breaks when moved.

### 2. Copy the project

Bring the whole directory across, keeping modification times:

```bash
rsync -a --exclude .venv-full --exclude logs \
      --exclude 'content/pipeline.lock.db*' --exclude 'content/.pipeline.lock.db*' \
      old-machine:thesis/ ~/thesis/
```

Or unpack a [full backup](#-a-full-backup) with `tar -xzf`, which keeps
the stored times.

To bring only your writing and rebuild the corpus, run `chitragupta
init`, copy `config.toml`, `papers/` and `content/specs/` across,
restore a dossier bundle with `--force`, and run `sync`. Parsing and
`enrich` then start from scratch.

### 3. Check the paths the copy cannot fix

Check the six path settings from
[Moving to another directory](#-moving-to-another-directory): an
absolute path such as `/home/ana/Zotero/export.bib` does not exist on
the new machine.

Then check each `file` field in `bibliography.bib`. chitragupta reads a
PDF only inside the bib file's directory or below it. A relative path
such as `files/12/smith2024.pdf` moves with `papers/`. An absolute one
such as `/home/ana/Zotero/storage/ABCD1234/smith2024.pdf` is refused
unopened, `sync` reports the entry as having no PDF, and the run exits
with code 3.

The clean fix is to export again on the new computer with the PDFs
beside the bib file; [ZOTERO.md](ZOTERO.md) shows the settings that
write relative paths, and why the companion folder must keep its name.
[CLI.md](CLI.md) has the other two options: point `[bib].path` at the
PDFs' real directory, or remove the `file` field.

### 4. Check the machine

```bash
cd ~/thesis
chitragupta doctor
```

`doctor` reports missing programs (pdftotext, pdftoppm, pdfinfo,
pandoc, LuaLaTeX, Vale), a missing `enrich` extra, a PyTorch build that
does not match the GPU, and agent hooks that cannot start. `sync` with
the default parser needs pdftotext, `render` needs pandoc and LuaLaTeX,
and `figure look` needs pdftoppm (and pdfinfo with a draft).

### 5. Sync and look at the result

```bash
chitragupta corpus sync
```

Expect `0 parsed`. Then try something that reads the parsed text, such
as `chitragupta draft retrieve search "a phrase from your field"`, and
run `chitragupta draft dossier status --all` to see whether any draft's
evidence moved. With the `docling` backend a re-parsed PDF's text can
differ slightly, so the review aids may place a kept quote elsewhere;
copying `content/parsed/` across avoids this.

## 🐳 Sharing a project between a container and the host

[DOCKER.md](../DOCKER.md) mounts your project at `/workspace` in the
container. The ledger stores nothing that depends on the mount point, so
a `sync` on the host and a `search` in the container (or the reverse)
find the same text and parse nothing again. The compose file mounts
`papers/` read-only at `/workspace/papers`, so `[bib].path` must stay
inside the project, as it does by default.

## 🩺 When something looks wrong after a move

| What you see | Why | What to do |
| --- | --- | --- |
| Every document is re-parsed after a move | A machine sharing the ledger runs an older chitragupta | Install the same release everywhere, then `sync` |
| Entries reported as having no PDF, `pdf_outside_papers`, exit code 3 | The bib file's `file` fields hold absolute paths from the old machine | Export the bib file again with relative paths (see [step 3](#3-check-the-paths-the-copy-cannot-fix)) |
| `sync` is slow but parses nothing | The copy lost modification times | Nothing; the next `sync` is fast |
| `enrich` runs Docling on every PDF again | The copy lost the PDFs' modification times | Let it run, or copy again with `rsync -a` |
| `No config file` on import | The command ran outside the project | `cd` into the project, or set `CHITRAGUPTA_PROJECT` |
| The citation gate cannot confirm citekeys after a restore | `sync` has not built the ledger on this machine yet | Run `chitragupta corpus sync` |
