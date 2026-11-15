# Digest: working the report down, one item at a time

Read a section of this file when the step that sent you here cites it;
each section opens with when it applies. Paths here are from the
project root.

## 1. Working the report

Read this when the user has asked for a repair pass, before the first
repair. Without that request the report is shown, never worked.

Take the items one at a time, worst class first, as the report orders
them:

- `unsupported-text`: cite the source that says it, replace it with
  that source's words, or delete it. Where the NLI support report marks
  the sentence entailed, the repair is to cite it correctly, not to
  delete it.
- `copy-mismatch`: open the source at the page named and restore the
  exact words.
- `dangling-reference`: show the item, substitute it in brackets,
  delete the marker, or move the run's start or end.
- `repeated-text`: keep the first copy, cut the later one, and point
  back to it in a sentence of your own.
- `unquoted-text`: close the sentence with a `see` citation, replace it
  with a copied passage that does its job, or delete it.

**Keep a repair only if** the gate passes, the item is in `resolved`,
no class count rose, `new` is empty, and the unsupported fraction did
not rise; the baseline comparison prints `fell: yes` exactly when the
last four hold. Otherwise revert it.

**Log every attempt**, kept or reverted, in the dossier's
`revisions.md`: the date, the item id, the class, what you did, and the
fraction before and after.

**Stop** when the user says so, when no item is left, or after three
passes whose fraction did not fall.
