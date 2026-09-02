# Retrieval calls

<!-- Appended by `python -m chitragupta.draft retrieve ... --log <draft>`, never by
     hand.

     `asked` is how much that call requested -- `--k` for search,
     `--windows` for evidence. `chars` is the size of the payload it
     handed back: the thing that then sits in the caller's context for
     the rest of the run. Together with evidence.md's and rejected.md's
     counts, this is what turns "retrieval is where the tokens go" from
     an estimate into a measurement for a particular draft.

     A row with mode `revision` is not a call: `python -m chitragupta.draft dossier
     mark-revision` writes one, at the start of each draft-reviser pass,
     so `dossier status` can total retrieval cost per revision instead of
     only as one lifetime figure -- the date column alone can't tell two
     same-day revisions apart.

     `collection` is the Zotero collection `--collection` scoped the call
     to, empty for a corpus-wide call -- which is also how every row
     written before this column existed reads, since an absent seventh
     cell is padded in the same way (#254). Without it, a scoped call and
     a corpus-wide one write byte-identical rows, and `dossier status`
     re-asks a scoped draft's queries against the whole corpus.

     `origin` is `declared` or `extended` (#455) -- whether the query came
     verbatim from outline.md or was added with `--origin extended`
     because a declared section came up thin. Empty for a call that named
     neither, padded in the same way for a row written before this column
     existed -- but unlike `collection`'s empty reading, that is not read
     as "declared": a pre-outline.md call was neither. Without this
     column, "did this draft follow the outline it declared?" has no
     evidence to answer from. -->

| date | mode | query | asked | results | chars | collection | origin |
|---|---|---|---|---|---|---|---|
| 2026-09-02 | search | operator trust override log authority | 5 | 2 | 950 |  | declared |
