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
     evidence to answer from.

     `expanded` is what `chitragupta/retrieval_expansion.py` added to the
     query before ranking it -- `DT -> digital twin`, an acronym and the
     terms its expansion contributed (#789). Empty for a call that added
     nothing, which is every call until `[retrieval].acronym_expansion`
     is turned on, and also how every row written before this column
     existed reads. Without it, a result that surfaced on a word the
     caller never typed leaves no record of why.

     `k1` and `b` are the two Okapi BM25 settings in force when the call
     ran (#788) -- `[retrieval].k1` and `[retrieval].b`, which shape
     term-frequency saturation and length normalization. Unlike the four
     columns above, these are written from config rather than passed in
     by the caller: they describe the ranker that actually ran rather
     than anything the caller asked for, and a caller who forgot would
     write a blank indistinguishable from a row predating the columns.

     The shipped values are written out rather than left blank. "Blank
     means default" is the one encoding that cannot work, because blank
     already means "logged before these columns existed" and a default
     that moved later would retroactively change what every old blank row
     claimed. A `revision` marker row leaves them empty by writing the
     shorter pre-column shape, as it already does for `expanded`.

     Without these, a session that tuned either setting mid-draft leaves
     a log whose rows cannot be compared with each other, and the replay
     `bench/bench_retrieval_live_logs.py` builds its ground truth from
     silently mixes two rankers. -->

| date | mode | query | asked | results | chars | collection | origin | expanded | k1 | b |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-02 | search | what is a digital twin definition concepts | 15 | 5 | 2145 |  |  |  | 1.5 | 0.75 |
| 2026-10-02 | search | digital twin synchronisation data sync model update | 15 | 5 | 2357 |  |  |  | 1.5 | 0.75 |
| 2026-10-02 | search | digital twin factory manufacturing applications smart factory | 15 | 5 | 2145 |  |  |  | 1.5 | 0.75 |
| 2026-10-02 | search | digital twin interoperability standards OPC UA industry 4.0 | 15 | 5 | 2161 |  |  |  | 1.5 | 0.75 |
| 2026-10-02 | evidence | digital twin definition taxonomy | 2 | 2 | 1089 |  |  |  | 1.5 | 0.75 |
| 2026-10-02 | evidence | digital twin synchronisation strategies | 2 | 2 | 1096 |  |  |  | 1.5 | 0.75 |
| 2026-10-02 | evidence | digital twin factory case study manufacturing | 2 | 2 | 1086 |  |  |  | 1.5 | 0.75 |
| 2026-10-02 | evidence | interoperability standards OPC UA industrial asset | 2 | 2 | 1097 |  |  |  | 1.5 | 0.75 |
| 2026-10-02 | evidence | anomaly detection digital twin state stream | 2 | 1 | 500 |  |  |  | 1.5 | 0.75 |
