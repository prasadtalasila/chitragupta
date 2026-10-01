# 🎬 Demo recording

Status: **reference.** Terminal segment recorded 2026-09-18 against
`main`; browser segment re-recorded 2026-10-01 (#809).

**Written for** anyone who wants to see the pipeline run before reading
the rest of the documentation. One pass through the spine -- corpus sync,
topic discovery, an already-drafted unit and its dossier, the citation
gate, the review agenda, one more review aid -- then a look at the
offline topic-graph viewer in a browser. Recorded against the committed
sample project ([docs/examples/](examples/README.md)), so every command
in it is real and every citekey it cites is real; nothing here was
invented for the recording.

The animated terminal segment alone is embedded inline in
[README.md](../README.md) as `docs/images/demo.svg`. The full recording,
including the browser segment, is below.

<video controls width="100%" poster="images/demo-webapp.png">
  <source src="images/demo.webm" type="video/webm">
  <source src="images/demo.mp4" type="video/mp4">
  Your browser does not render an inline video here -- the source files
  are <a href="images/demo.webm">demo.webm</a> and
  <a href="images/demo.mp4">demo.mp4</a>.
</video>

A palette-optimised GIF of the same recording is also available:
[`docs/images/demo.gif`](images/demo.gif) -- useful anywhere a `<video>`
tag or the two source formats above are inconvenient, at the usual cost
of a GIF being larger than either video encode for the same content.

## 🧭 The longer all-features tour

A second, longer recording exists: thirty-seven steps across all four
layers -- `corpus`, `enrich`, `draft` and `review` -- ending on the same
browser segment. It is the one to watch to learn what the tool actually
has, rather than what a first run looks like.

It is **deliberately not shipped in this repository.** At roughly two and
a half minutes it is several times the size of the recording above, it
dates faster than the reel does because it names individual commands, and
`scripts/release.py` bundles all of `docs/` into the release archive. It
lives instead beside the corpus it was recorded against, in
`content/chitragupta-demo-recordings/`, alongside the shell script that
produced it -- so it can be re-recorded against a later `main` without a
commit.

### 🚫 What the tour leaves out, and why

The tour is a tour of the command surface, not proof of coverage of it.
Three groups of commands are absent on purpose:

- **The verbs that write to the sample project.** `dossier init`, `spec
  sign`, `unit accept`, `tldr write` and `registry build` are the
  acceptance half of the book track, and arguably the most interesting
  thing the pipeline does -- but each one changes committed sample state,
  and a recording that leaves the repository dirty is a recording nobody
  can re-run. [WRITE-A-BOOK.md](WRITE-A-BOOK.md) walks that half in
  prose.
- **`review union`.** It reads an assembled `book.tex`, and the sample
  project's `twin-basics` deliberately ships as un-assembled units. There
  is nothing in the checkout for it to read.
- **The live-LLM skills, and the `docling` stage.** The genre skills
  (survey, thesis chapter, tutorial, …) need a model, and `docling` is
  the slowest stage in the pipeline with nothing committed depending on
  it -- the sample project's own `regenerate.sh` skips it for the same
  reason. `draft figures` is still shown, reporting honestly that the
  stage has not run.

## 🛠 How they were made

Terminal segments: `asciinema` recorded a real shell session (112x32)
against `docs/examples/sample-project` -- installed package resolution
shown via `pip install --dry-run`, everything after that a real
`python -m chitragupta.*` invocation -- then the boring, non-narrative
span (the dependency-resolution scroll) was sped up and the rest slowed
slightly by dividing the recorded event timestamps, not by a player's
speed control, since the inline SVG has none. The result was rendered to
SVG (`svg-term-cli --window`, a CSS `@keyframes` animation, no
`<script>`) and to video (`agg`, then `ffmpeg` at 1280x720/15fps).

The browser segment drove the committed
`docs/examples/sample-project/content/topic_map.html` over CDP with
Puppeteer against a headless Chrome, screenshotting each interaction and
assembling the frames into video with `ffmpeg`. The capture script
asserts the number of rendered topic circles against the topic count the
page itself embeds, and fails the run on a mismatch, rather than letting
a selector that has moved yield a video of the same establishing shot
repeated -- which is exactly what the viewer's markup change since the
first recording would otherwise have produced. It also checks, after
every click, that the panel names the topic just clicked.

The browser segment was re-recorded on its own on 2026-10-01, when the
sample page was re-emitted in merge-tree leaf order (#809) and its
circle moved. Only the browser segment shows that circle, so the
terminal segment was kept as it was: the first 40.4 seconds of
`demo.mp4` are stream-copied from the previous file, cut on the
keyframe where the browser segment starts, and decode to the same
frames. The new browser segment was encoded with the same `libx264
-crf 20` settings and joined on after them. `demo.webm` (`libvpx-vp9
-crf 32 -b:v 0`) and `demo.gif` (`fps=10`, `scale=640`, a single
`palettegen`/`paletteuse` pass) were then re-encoded from the new
`demo.mp4`. The GIF chain reproduces the previous `demo.gif` byte for
byte from the previous `demo.mp4`; the VP9 encode does not, though its
keyframe layout and size match to within 1%. `demo-webapp.png` is the
topic-1 frame of the new capture. `demo.svg` is terminal-only and did
not change.

Nothing in either segment touched a real project. The sample project's
committed drafts, dossiers and reviews were only read; the commands that
do write tracked files (`draft evidence`, `draft render`, `review
agenda`) were run against it and the tree restored afterwards, and a
recording is only kept if `git status` on
`docs/examples/sample-project/` comes back empty.
