# No dossier yet: bootstrap one

Read this only when the draft you were asked to revise has no dossier
under `content/dossiers/`. Paths here are from the project root.

Drafts written before `chitragupta/dossier/` existed have none, and so do
drafts written by hand. Bootstrap one rather than refusing:

```bash
python -m chitragupta.draft dossier init content/drafts/<path> --genre <genre>
```

Then fill in what the draft itself can tell you -- `sections.md` from
`python -m chitragupta.draft dossier sections`, and `scope.md`'s reader/covers/excludes
from the draft's own scope paragraph if it has one. Leave `evidence.md`
and `rejected.md` empty and **say so in chat**: the first revision of a
bootstrapped draft cannot check a claim against recorded evidence, and
may have to re-retrieve for a sub-theme that a real dossier would have
answered from disk. It gets cheaper from the second revision on.

Do not invent evidence entries to fill the file. An empty `evidence.md`
is honest; a fabricated one is the same failure class as a fabricated
citekey.
