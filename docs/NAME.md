# 🏷 Chitragupta

Status: **reference.**

A divine record keeper who keeps the ledger of deeds and audits souls against it.

## 🪶 The figure

Chitragupta is the registrar of the Hindu cosmos: the deity who
maintains the complete record of every action of every being, from
birth to death. When a soul arrives in Yama's court, it is Chitragupta
who produces the itemized account, and judgment is passed on the
strength of it.

He is depicted holding a pen (*lekhani*), an inkpot, and the ledger
itself. His name is usually parsed as *chitra* + *gupta*: "the one in
whom all the records reside, kept safe."

## 💡 Why the name fits this project

This pipeline turns a curated BibTeX bibliography into grounded drafts
and books, with every citation mechanically verified against a ledger of
real, parsed PDFs. The correspondence holds point for point:

1. **The ledger is the whole identity.** Other knowledge deities
   preside over learning broadly; Chitragupta *is* his ledger. This
   project's center of gravity is `content/ledger.sqlite`, a
   complete, per-citekey record of what exists and what state it is
   in.

2. **He records; he never composes.** Chitragupta's authority comes
   precisely from the fact that no entry in his book was invented.
   That is this project's hard invariant: a citekey exists in the
   record only because a real parse of a real PDF put it there, and the
   pipeline never invents or renames one.

3. **Judgment happens against the record.** In Yama's court, claims
   about a life are checked against the book, and the book wins. That
   is `draft gate` exactly: a draft's claims are checked against
   the ledger at the moment of reckoning, and a `FAIL` is final.

4. **The audit is incorruptible, not well-intentioned.** Chitragupta
   is characterized as impartial: the record cannot be argued with or
   flattered. This project's enforcement is likewise mechanical: a hook
   or plugin runs the gate after every write an agent's file tools make
   under `content/drafts/`, and `draft render` runs it again before any
   document is produced, so grounding does not depend on anyone
   remembering to be honest. "Enforced by architecture, not by prompt"
   (README) could be his epithet.

5. **Evidence, quoted.** Judgment in the stories is not a bare
   verdict; the deeds are read out. `citation_provenance`, which quotes
   the supporting passage from each cited source, does the same: the
   record can establish *that* a source exists and can also produce
   *what in it* supports the claim.
