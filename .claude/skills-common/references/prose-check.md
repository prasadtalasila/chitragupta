# The prose check: what it sees and how to report it

Read this at the prose-check step, once you have run the
`python -m chitragupta.draft style` command that step names. Paths here
are from the project root.

**It checks only what `docs/WRITING-STANDARDS.md` §9 marks decidable**
-- §2's defect markers, an acronym never expanded at first use, a
glossary acronym whose expansion has drifted from the vocabulary, §8's
dialect against `scope.md`'s `language:` line, and an uncaptioned table
or figure. It says nothing about whether a paragraph leads with its
point or whether a hedge carries information, and a clean report on the
classes it does not check says nothing about them. It cannot tell a
quotation from the draft's own voice, so a marker inside a quoted
passage reports and is correct as it stands. Fenced code is skipped; a
LaTeX fragment is scanned as Markdown, so its `verbatim` environments
and `\cite` arguments are skipped and its prose is not.

**Report every finding and fix none of them.** A finding is a place to
look, not a defect: the first pass of this check over this repository's
own docs kept 59 of its 73 marker hits on inspection. Acting on one is a
separate change, made in a copy-edit pass that reads the recorded
dialect and logs one `revisions.md` entry -- never an edit made at this
step.

**Report the header lines too.** `dialect: not checked` means nobody
ever recorded one, so a short list is not a clean draft.

**A review aid, not a gate.** It exits 0 whatever it finds, and a
missing `vale` binary is a one-line warning that blocks nothing.
