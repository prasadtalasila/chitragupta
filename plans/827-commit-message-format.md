# ✉ 827: the commit body is written in the documented format, not scraped

Status: **built**, in the same pull request as this plan, for issue
827. Written 2026-10-01; the open questions were settled the same day
(see [Decisions](#-decisions)). Built as designed, with four changes on
the way:

- `CommitBody` is a plain class validated in `__init__`, not a frozen
  dataclass with a `parse()` constructor: the tests load the script by
  path without registering it in `sys.modules`, and `dataclasses` needs
  that to resolve annotations. Constructing one is still the only way to
  get one, so holding one still proves the text conforms.
- `FormatError` carries one message rather than `(line_number,
  reason)` fields. The message names the line number, the rule and the
  line as `repr()`, so an invisible character shows up escaped.
- The template's instruction is an HTML comment *above* the `## Commit
  message` heading, not text inside the section, because the section
  must be the fence alone.
- `_CLOSING_RE` was widened to every reference form GitHub closes on:
  `Fixes: #12`, `owner/repo#12` and an issue URL, besides `#12`.

The `BLANK` setting and the required check are not applied yet; they
need the repository owner, after merge (step 6 below).

Issue #827 reports that `scripts/merge_pr.py` copies every non-checkbox
bullet in a PR description into `main`'s history verbatim, so a trailer,
a live closing keyword, an ANSI escape or a bidi override in a bullet
lands permanently. It proposes three filters on the copied text: a
character-stripping `_sanitise`, a trailer-shaped regex, and a closing
keyword promoted from warning to refusal.

This plan solves the issue's problem a different way. The scraping is
what goes wrong, and the issue's filters would add more of it.
DEVELOPER-AGENTS.md's "Commit messages" section already defines what a
squash body is: bullets, each one starting with a present-tense verb, no
preamble. Nothing in the pipeline asks anyone to write that. The script
assembles a body from whatever bullets a review document happens to
contain. So the author writes the body once, in that format, in one
known place. The script **validates** that text against the format and
lands it **unchanged**, or refuses. It does not strip, join, rewrite or
fall back.

**Written for** whoever implements it. `scripts/merge_pr.py`,
`tests/test_merge_pr.py`, `.github/pull_request_template.md`, a new
`.github/workflows/commit-message.yml`, and DEVELOPER-AGENTS.md's
"Commit messages" and "Merging" sections move together, along with one
repository setting. **Assumed** you have read those two
DEVELOPER-AGENTS.md sections and `merge_pr.py`'s module docstring, which
explains why the body is supplied at merge time and why no repository
setting can do it. **Not covered here:** the PR *title*. It is already
closed by `squash_merge_commit_title = PR_TITLE`, and this plan leaves it
alone (see [Decisions](#-decisions)).

## 🧭 Table of contents

- [Why the documented format is never what lands](#-why-the-documented-format-is-never-what-lands)
- [The design](#-the-design)
- [The format, as a grammar](#-the-format-as-a-grammar)
- [What `merge_pr.py` becomes](#-what-merge_prpy-becomes)
- [Checking it when the PR is opened, not at merge time](#-checking-it-when-the-pr-is-opened-not-at-merge-time)
- [The repository setting](#-the-repository-setting)
- [Documentation and template changes](#-documentation-and-template-changes)
- [What the tests must pin](#-what-the-tests-must-pin)
- [Order of work](#-order-of-work)
- [How this meets the issue's success criteria](#-how-this-meets-the-issues-success-criteria)
- [Decisions](#-decisions)

## 🔍 Why the documented format is never what lands

The six squash commits at the tip of `main` (#906, #910 to #914), read
with `git log origin/main -6 --format='%s%n%b'`:

- **Every bullet appears twice.** #910, #912 and #913 each carry a
  `## Description` bullet block followed by a `## What changed` bullet
  block that says the same thing again. The scraper takes both, because
  it takes every non-checkbox section.
- **Some bullets are not changes.** #906's body includes "The figure
  warning for a refused escaping link still says 'not a readable file'"
  and "One ragged docstring reflow in `_assets.py`", which are reviewer
  notes. #913's first three bullets are design rationale ("The issue
  proposed a lazy import of `__main__` itself. That would load...").
- **Bullets in the user's point of view are not change bullets.** The
  template's "What changed, from the user's point of view" asks for
  exactly that, and the scraper puts it into the commit body as if it
  were one.
- **The wrapping is lost.** `_bullets_in` joins continuation lines with
  a space, so every bullet lands as one long line. Its docstring already
  admits that this sometimes breaks a token in two.

None of these is an authoring mistake. The PR template asks for a review
document, and the script mines it for a commit message, so the
documented format can only appear by chance. The security findings in
issue 827 are the same fault: text written for one reader is copied to
another without anyone writing it for that second reader.

## 🧩 The design

```text
PR description                         merge_pr.py                     main
--------------------------------       -----------------------------   ----------------
## Commit message                      1. find the one ```text fence   squash commit:
```text                                   under "## Commit message"      title = PR title
- Fix ...                         -->  2. CommitBody.parse(fence)  -->   body  = fence,
  continuation                            (refuse on any violation)              byte for byte
- Add ...                              3. version-bump check
```                                    4. gh pr merge --body-file -
```

Three properties follow from it:

1. **One source.** The body comes from one named section's one fenced
   block. No other section is read. There is no fallback to commit
   subjects. The fallback exists today only because the scrape could
   come up empty, and that fallback is the `* <title>` shape #357 was
   opened to remove.
2. **No transformation.** The fenced text is either accepted or refused,
   so what the author previews is exactly what lands, wrapping included.
   This deletes `_bullets_in`, `_outside_fences`, `_BULLET_RE`,
   `_CHECKBOX_RE`, `_EXCLUDED_HEADINGS`, `bullets_from_description`,
   `bullets_from_commits` and `_pr_commit_subjects`: roughly 120 lines
   of the script, plus about 30 tests that pin scraping edge cases (PR
   518's `~~~` truncation, the M-29 fence bug in
   `plans/code-review-2026-09.md`) which can no longer happen.
3. **Allowlist, not blocklist.** The issue's `_sanitise` and
   `_looks_like_trailer` describe what is forbidden, so each new trick
   (another invisible code point, another trailer token) needs a new
   rule. The grammar below describes what is *allowed*. A trailer, an
   escape sequence or a bidi override fails because it is not a bullet
   in the documented shape. None of them needs a rule of its own.

The fence is a ```` ```text ```` block because GitHub renders it as
preformatted text. The author and the reviewer both see the exact bytes,
wrapping included, with no Markdown rendering in between. A Markdown
list outside a fence would render differently from the text that lands.

## 📐 The format, as a grammar

This is DEVELOPER-AGENTS.md's "Body" paragraph, written so a machine can
check it. It replaces that paragraph's prose as the definition, and the
paragraph then points here, or better, to `CommitBody`'s docstring.

```text
body         := bullet+                           (at least one, no blank lines)
bullet       := "- " verb rest NEWLINE continuation*
continuation := "  " non-space rest NEWLINE       (exactly two spaces of indent)
verb         := a word of letters only, first letter upper-case
                (Fix, Add, Remove, Migrate, Upgrade, Rename, ...)
```

It also imposes four constraints on the whole text:

- **Every line is printable**: `line.isprintable()` is true. Python's
  definition already excludes C0 and C1 controls, DEL, every `Cf`
  format character (the bidi overrides U+202A to U+202E and U+2066 to
  U+2069, and the zero-width characters U+200B to U+200F) and
  non-ASCII spaces. Checked on 2026-10-01 against `\x1b`, U+202E,
  U+200B, U+2066, `\x7f` and U+00A0: all six are rejected. The issue's
  hand-written code-point ranges are not needed, and the range cannot
  fall behind a new Unicode version.
- **No closing keyword** anywhere (`_CLOSING_RE`, which already exists).
  A keyword in the PR *description* already closes the issue when the
  PR merges. One in the *commit* is redundant at best, and at worst
  closes an issue the PR never linked. The issue's "unless the PR's
  issue links already list it" exception is therefore unnecessary,
  which saves a `closingIssuesReferences` API call.
- **No line is a git trailer.** The grammar already rules this out: a
  bullet starts with a dash and a space, and a continuation with two
  spaces, so no line starts with a token followed by a colon. The test
  suite pins the outcome by running `git interpret-trailers --parse` on
  the accepted output of every adversarial fixture and asserting that
  it returns nothing. That is git's own parser, not a reimplementation
  of it.
- **No line is longer than 72 characters**, counted as `len(line)`,
  continuation indent included. 72 is git's own convention for a body:
  `git log` indents it by four, so it still fits an 80-column terminal.
  The limit is a module constant, `MAX_LINE = 72`, named in the refusal
  message. Counting code points rather than display cells is
  deliberate: a full-width character counts once but displays twice,
  and getting that right needs `unicodedata.east_asian_width`, which is
  more than an English-language repository needs. Whoever hits it can
  wrap earlier.

What the grammar deliberately does **not** check:

- **That the verb is really a verb.** A capitalised letters-only first
  word excludes the hostile cases (`Co-authored-by:`, `Signed-off-by:`
  and `Closes:` all contain a hyphen or a colon). Telling "Fix" from
  "Fixed" or "The" is a review question, and a word list would refuse
  real verbs no one thought to add.
- **The title.** Out of scope, as stated above.

`CommitBody` holds the text and validates it on construction. On
failure it raises `FormatError`, naming the **first** line that breaks
the grammar and the rule it breaks, for example `commit message line
3: is neither a ``- Verb ...`` bullet nor a continuation indented two
spaces: ' three'`. Reporting only the first failure keeps the parser a
single pass. The author fixes one line and re-runs `--dry-run`, which is
the loop the issue's "exit non-zero with the bullet named" criterion
asks for.

## 🛠 What `merge_pr.py` becomes

The public surface, after the change:

| Name | Role |
| --- | --- |
| `CommitBody`, `FormatError` | the grammar above; `str(body)` returns the text unchanged |
| `commit_body(pr_body) -> CommitBody` | find `## Commit message` with the existing `_sections`, require exactly one ```` ```text ```` fence and nothing but whitespace around it, then call `CommitBody.parse` on the fence's contents |
| `inert_closing_keywords` | **kept** as a warning. It is about the *Description*, where a backticked `Closes #N` silently fails to close the issue, and that problem is unchanged |
| `_gh`, `_pr_body`, `_merge`, `_version_rules` | unchanged |
| `main` | prints the body, warns about inert keywords, runs the version check, then merges, all in today's order. A `FormatError` prints and returns 1 **before** the version check, since there is nothing to merge |

**Finding the fence** is the one place that reads Markdown. It does not
need a Markdown parser. The section is defined as *one fence and nothing
else*, so the check is "after stripping, the section starts with
```` ```text ```` and ends with ```` ``` ````, and no other fence
appears". Anything else, including a prose explanation beside the fence,
is a `FormatError` that tells the author to move the prose to
Description. `markdown-it-py` and `marko` are both in the lock file, but
only through the `enrich` extra, and a dev script should not depend on
that.

**A missing section** is a refusal, not a fallback. The message prints
an empty skeleton of the section, the heading and an empty fence, so
the fix is a paste followed by writing. It does not generate bullets.
Pre-filled content would be scraped text again.

Every new helper stays under CODE-STANDARDS.md's 25-statement bound.
The module docstring's "Source of the bullets, and why not raw commits"
paragraph is rewritten to give this plan's reasoning. Its
producer-is-enforcement paragraph stays, but is no longer the whole
enforcement story (next section).

## 🚦 Checking it when the PR is opened, not at merge time

The format "is never followed" partly because the only check runs at
merge, at the end of a long session. That is the moment DEVELOPER-AGENTS.md
already names as the one where a format gets forgotten. A merge-time
refusal is still necessary, but it is the latest possible feedback.

So the same validator also runs as a PR check:

- `python scripts/merge_pr.py --check` reads a PR body on stdin and
  validates it. It makes no `gh` call and runs no version check, and it
  exits 0 or 1 with the same messages as a merge. `pr_number` becomes
  optional when `--check` is given.
- A new `.github/workflows/commit-message.yml` runs on `pull_request`
  with `types: [opened, edited, synchronize, reopened]`. `edited` is the
  reason for a separate workflow: adding it to `ci.yml` would re-run the
  full suite on every description edit. The job needs only
  `actions/setup-python` and the stdlib, so it finishes in seconds.
- **The body reaches the script through `env:`, never through `${{ }}`
  interpolated into `run:`.** The body is attacker-controlled text, and
  interpolating it into a shell line is a script-injection hole:
  `env: { BODY: ${{ github.event.pull_request.body }} }`, then
  `printf '%s' "$BODY" | python scripts/merge_pr.py --check`. Use
  `permissions: {}`, because the job reads nothing from the repository
  API.

The check is made **required** on `main` (decision 2). That is a
branch-protection change, and it has two practical constraints:

- **GitHub only offers a check as required once it has reported at
  least once.** So the requirement is added after this PR's own run of
  the workflow, in step 6 of the order of work, not before.
- **The session token cannot do it.** On 2026-10-01 the PAT in this
  container got HTTP 403 from
  `branches/main/protection/required_status_checks`. The repository has
  a ruleset named `main` (id 22029593) whose `enforcement` is
  `disabled`. The owner adds the `commit-message` check either to that
  ruleset, enabling it, or to classic branch protection, in the GitHub
  UI. Whichever is used, record it in DEVELOPER-AGENTS.md's settings
  section beside `BLANK`, so the requirement is a documented fact and
  not a setting someone has to rediscover.

## ⚙ The repository setting

Switch `squash_merge_commit_message` from `PR_BODY` to `BLANK`, as the
issue proposes:

```bash
gh api -X PATCH repos/prasadtalasila/chitragupta -f squash_merge_commit_message=BLANK
```

A web-UI merge then lands the title alone, with no body. That is wrong,
but it is wrong *visibly* and harmlessly, where today's `PR_BODY` lands
the whole review document, tick-boxes and any injected trailer
included. `merge_pr.py` stays the only route that writes a body. Apply
the setting **after** the code merges: the change PR itself is merged
by the old script, and the setting has no effect on `--body-file`
either way. Record the date in DEVELOPER-AGENTS.md's settings section,
as that section already does for #238.

## 📝 Documentation and template changes

- **`.github/pull_request_template.md`**: add a `## Commit message`
  section after `## Description`, holding an empty ```` ```text ````
  fence, preceded by an HTML-comment instruction: "The squash commit
  body, exactly as it will land: `- Verb ...` bullets, continuation
  lines indented two spaces, every line at most 72 characters, no
  closing keywords. Checked by CI; nothing else in this description is
  copied into the commit." The
  `## What changed` section
  stays as the reviewer-facing summary. It is no longer copied anywhere,
  so its bullets can stop duplicating the commit's.
- **DEVELOPER-AGENTS.md "Commit messages"**: keep the example, but
  rewrap it. Its first bullet line is 74 characters, so as written it
  would fail its own check. Add "lines wrap at 72 characters" to the
  "Body" paragraph. Replace
  "This body shape is still not what lands by default, and you still
  have to state it at merge time" and the paragraphs after it with: the
  body is written in the PR's `## Commit message` section, checked at
  PR time and at merge, and lands byte for byte.
- **DEVELOPER-AGENTS.md "Merging"**: rewrite "It composes the squash
  body from the PR's own description (falling back to...)" and the
  "A body on stdin is still needed" paragraph to match. Update the
  settings block and its `PR_BODY` bullet to record the `BLANK` change.
  Release-cycle step 9 is unchanged.
- **docs/TECHNICAL-DEBT.md**: the three passages at lines 562, 629 and
  650 to 660 describe `merge_pr.py` *composing* the body. Reword them
  to "validating". The debt entry itself is unchanged, since
  producer-is-enforcement still describes the merge path.
- **Not edited**: `plans/781-tikz-library-hoist.md:1715` and
  `plans/code-review-2026-09.md`'s M-29 row. `plans/README.md` allows
  plans to go stale.
- **After merge**: update the auto-memory note "merge_pr.py body needs
  bullets", which describes the scraping this plan removes.

## 🧪 What the tests must pin

Tests are written first and confirmed failing, per DEVELOPER-AGENTS.md.
The suite must stay at 100% line and branch coverage.

`CommitBody.parse`:

- the DEVELOPER-AGENTS.md example, once rewrapped, parses, and `str()`
  returns it byte for byte (the round trip). Read it from the file
  rather than copying it into the test, so the example cannot drift
  out of the format it illustrates
- a 72-character line is accepted and a 73-character one refused, for a
  bullet and for a continuation line
- each of the issue's four probe lines is refused with its line number:
  the `\x1b[31m` escape, U+202E, `- Co-authored-by: ...`,
  `- Signed-off-by: ...`, and `- Closes #N`. The trailers fail the verb
  rule and the keyword fails its own rule. Add one case each for a
  zero-width space, U+2066 and a NBSP
- `Closes #N`, `fixes #N` and `Resolved #N` are refused *mid-bullet*,
  not only at the start of one
- a continuation line with one, three or a tab of indent; a blank line
  between bullets; a `*` marker; a lowercase first word; an empty body.
  Each is refused with its rule named
- **git agrees**: for every accepted fixture, `git interpret-trailers
  --parse` on `"Title\n\n" + str(body)` prints nothing. Run it through
  `subprocess` the same way `check_version_bump._git` does

`commit_body`:

- a missing section, a section with no fence, two fences, a `~~~` or an
  untyped fence, and prose beside the fence are all refused with a
  message naming the problem
- the bullets in `## Description` and `## What changed` are **ignored**
  when a valid `## Commit message` is present. This is the regression
  pin for the duplication measured above

`main`:

- `--dry-run` and a real merge both print the body and exit 1 on a
  `FormatError`, without calling `_version_rules` or `_merge`
- `--check` reads stdin and calls neither `gh` nor `_version_rules`
- the existing version-check ordering, inert-keyword warning and
  cosmetic-merge-failure tests carry over unchanged

## 🪜 Order of work

One PR, a PATCH bump (tooling and CI only, per DEVELOPER-AGENTS.md's
versioning rules):

1. Write the failing tests for `CommitBody` and `commit_body`, then
   implement them.
2. Rewire `main`, add `--check`, delete the scraping code and its
   tests, and rewrite the module docstring.
3. Add the workflow and the template section.
4. Update the docs listed above.
5. Write this PR's own description with a `## Commit message` section,
   so the change is merged by the code it introduces. Run
   `merge_pr.py <N> --dry-run` from the branch to confirm it.
6. After merge: apply the `BLANK` setting; have the owner make
   `commit-message` a required check; record both, with dates, in
   DEVELOPER-AGENTS.md's settings section; update the memory note; and
   mark this plan shipped with the PR number.

PRs that are open when this lands have no `## Commit message` section
and will be refused at merge. That is intended: the refusal prints the
skeleton, and adding it is a one-minute edit.

## ✅ How this meets the issue's success criteria

| Criterion | Met by |
| --- | --- |
| A trailer-shaped or control-character bullet makes `merge_pr.py --dry-run` exit non-zero with the bullet named | `FormatError(line_number, reason)`, which reports the first offending line, and the same refusal from `--check` in CI before merge |
| A web-UI squash merge cannot land an unfiltered PR body | `squash_merge_commit_message = BLANK` |
| Line and branch coverage stays at 100% | the test list above, and the scraping code and its tests deleted together |

The issue's own three helpers are **not** built. Each is replaced by a
rule the grammar already enforces.

## ✔ Decisions

Settled with the maintainer on 2026-10-01.

1. **The fence holds the body only, not the title.** The PR title is
   already the commit title through `squash_merge_commit_title =
   PR_TITLE`. A second copy in the fence could drift from it and would
   need a mismatch check of its own.
2. **`commit-message` is a required status check.** This is the step
   that makes the format impossible to skip, not just checked at the
   end. See
   [Checking it when the PR is opened](#-checking-it-when-the-pr-is-opened-not-at-merge-time)
   for how and when it is applied.
3. **The grammar enforces a 72-character line limit**, as set out in
   [The format, as a grammar](#-the-format-as-a-grammar). The
   documented example is rewrapped to meet it in the same PR. Open PRs
   are refused on day one regardless, for the missing section, so the
   limit adds no new breakage.
4. **The commit message is written in the PR description, not passed in
   at merge time.** GitHub stores no commit message on a PR ahead of a
   merge: the REST merge call (`gh pr merge --body-file`, which
   `merge_pr.py` already uses), the web UI's editable box, and the
   auto-merge API (`allow_auto_merge` is `false` here) all set it at
   merge time. The alternative considered was
   `merge_pr.py <N> --message-file`, checked against the same grammar.
   It needs no template section and no workflow, but nobody would
   review the message before it lands, and it would leave decision 2
   with nothing to check while the PR is open. Rejected for that
   reason.
