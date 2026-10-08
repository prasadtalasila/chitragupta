# Acronym realignment: the two edits

Read this once you have said you are in acronym-realignment mode and
named the term(s). Paths here are from the project root.

**The check only ever compares `scope.md`'s glossary to the vocabulary.**
It cannot see whether the draft's own first-use expansion has drifted
the same way, independently, or not at all -- that is prose, not a file
diff, and no mechanical check here reads it. Two edits, not one:

1. **Rewrite the glossary bullet** in `scope.md` to the vocabulary's
   current expansion. This is what the finding named, so it is never
   optional.
2. **Find the term's own first-use expansion in the draft body** (the
   same "Name (ACRONYM)" shape `chitragupta/acronyms.py` looks for, or whatever
   shape this draft actually used) and update it too, if it disagrees.
   You can see this half because you are reading the section anyway;
   the check cannot. Say in the `revisions.md` entry that this half was
   read by eye, not verified by a check -- the same honesty the finding
   itself practises about what it can and cannot see.

Same guardrails as copy-edit mode: no claim changed, no citation added or
dropped, no argument reordered. One `revisions.md` entry,
naming the term(s) and every file touched:

```text
2026-08-14 -- acronym realignment: DT's recorded expansion changed from
"Digital twin" to "Digital Twin System" in content/acronyms.toml;
updated scope.md's glossary bullet and the chapter's own first-use
expansion (section 2) to match. The glossary half came from the style
check; the body half was read by eye, not re-verified by a check.
```

Re-run the prose check at the end: the finding should be gone. If it
isn't, say so rather than presenting a draft that still fails the check
you were asked to fix.
