# 🗂 Synthetic dossier files, one pair per genre

Status: **illustrations.** Written 2026-09-15.

**Written for** an author filling in a dossier for the first time and
wanting to see a finished one for their genre. Each subdirectory holds
the two files **you** write by hand -- `scope.md` and `outline.md` --
filled in the way that genre wants them.

**These are hand-written illustrations, not pipeline output.** That is
the difference between this directory and
[`../sample-project/`](../sample-project/), where every file is a real
artefact of a real run over the five committed sample papers. Nothing
here was produced by a `corpus sync` or a genre skill; the citekeys in
the `queries:` blocks are search *terms*, not citekeys, and no citekey
appears in these files at all. Treat them as shapes to copy, not as
evidence of anything.

The other six files in a dossier -- `evidence.md`, `rejected.md`,
`sections.md`, `retrieval.md`, `steering.md`, `revisions.md` -- are
written **for** you as the draft is produced, so they are not here. See
[`../sample-project/content/dossiers/`](../sample-project/content/dossiers/)
for real ones.

| Genre | Files | The tutorial that walks through it |
| --- | --- | --- |
| Survey | [`survey/scope.md`](survey/scope.md), [`survey/outline.md`](survey/outline.md) | [WRITE-A-SURVEY.md](../../WRITE-A-SURVEY.md) |
| Thesis chapter | [`thesis-chapter/scope.md`](thesis-chapter/scope.md), [`thesis-chapter/outline.md`](thesis-chapter/outline.md) | [WRITE-A-THESIS-CHAPTER.md](../../WRITE-A-THESIS-CHAPTER.md) |
| Textbook chapter | [`textbook-chapter/scope.md`](textbook-chapter/scope.md), [`textbook-chapter/outline.md`](textbook-chapter/outline.md) | [WRITE-A-TEXTBOOK-CHAPTER.md](../../WRITE-A-TEXTBOOK-CHAPTER.md) |
| Tutorial | [`tutorial/scope.md`](tutorial/scope.md), [`tutorial/outline.md`](tutorial/outline.md) | [WRITE-A-TUTORIAL.md](../../WRITE-A-TUTORIAL.md) |
| Deep research | [`deep-research/scope.md`](deep-research/scope.md), [`deep-research/outline.md`](deep-research/outline.md) | [WRITE-A-DEEP-RESEARCH-REPORT.md](../../WRITE-A-DEEP-RESEARCH-REPORT.md) |
| Book (a different file: the outline the **book** track signs) | [`book/spec.md`](book/spec.md) | [WRITE-A-BOOK.md](../../WRITE-A-BOOK.md) |

A book's `spec.md` is not a dossier file at all -- it lives under
`content/specs/` and describes the whole book's structure, while each of
its chapters still gets its own `scope.md` and `outline.md` from the list
above. It is kept here because it is the other file an author writes by
hand before any prose exists.

## 🧾 The fields, once

**`scope.md`** is created by `dossier init` with every heading present
and empty. You fill in four of them, plus one line:

| Field | What goes in it | Why it is asked for |
| --- | --- | --- |
| `language:` | a BCP-47 tag -- `en-GB`, `en-US`, `en-IN` | ships **unset**; a draft whose dialect nobody chose silently gets the model's own. Set it with `dossier set-language`, or edit the line |
| `## Reader` | one concrete sentence: who this is for and what they already know | every later revision is judged against it |
| `## Covers` | what the draft will address | the positive half of scope |
| `## Does not cover` | what it deliberately will not, **including any sub-theme the corpus turned out too thin to support** | so a reader can tell an omission from an oversight |
| `## Glossary` | each recurring term with the one definition the whole draft uses | this is what stops terminology drifting between revisions |

The `genre:`, `draft:`, `created:` and `corpus:` lines are stamped by
`init`; `draft digest:` is filled by `dossier stamp` once the draft is
ready.

**`outline.md`** is opt-in (`dossier init --outline`). Per `##`-or-deeper
heading:

| Field | What goes in it | How it is used |
| --- | --- | --- |
| `brief:` | steering, in your words | consumed once, **never appears in the draft** |
| `claim:` | your own prose, a sentence or short block | rewritten and grounded -- every sentence that cannot be grounded in the corpus is reported rather than shipped |
| `queries:` | a `-` list of search terms | run **verbatim** instead of the skill inventing sub-themes |

A section needs at least a `brief:` or a `claim:`. `queries:` is optional
even then -- plenty of sections are framing prose with nothing to
retrieve. A level-1 (`#`) line is the file's own title and is passed
over.

Validate the shape before drafting:

```bash
chitragupta draft dossier outline content/drafts/<slug>.md --check
```

It exits 1 if a section has neither a `brief:` nor a `claim:`.
