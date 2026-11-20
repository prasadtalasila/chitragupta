# 🎬 Demo recording

Status: **reference.**

**Written for** anyone who wants to see the pipeline run before reading
the rest of the documentation. The recording makes one pass through the
spine (corpus sync, topic discovery, an already-drafted unit and its
dossier, the citation gate, the review agenda, one more review aid), then
opens the offline topic-graph viewer in a browser. It was recorded
against the committed sample project ([docs/examples/](examples/README.md)),
so every command and every citekey in it is real. The terminal segment
alone is embedded in [README.md](../README.md) as `docs/images/demo.svg`.

<video controls width="100%" poster="images/demo-webapp.png">
  <source src="images/demo.webm" type="video/webm">
  <source src="images/demo.mp4" type="video/mp4">
  Your browser does not render an inline video here; the source files
  are <a href="images/demo.webm">demo.webm</a> and
  <a href="images/demo.mp4">demo.mp4</a>.
</video>

A GIF of the earlier 112-column recording,
[`docs/images/demo.gif`](images/demo.gif), serves wherever a `<video>`
tag is inconvenient, though it is larger than either video encode.

## 🧭 The longer all-features tour

A second recording, about two and a half minutes, runs thirty-seven
steps across all four layers and ends on the same browser segment. It is
the one to watch to learn what the tool has. It is deliberately not
shipped: it is several times the size of the recording above, it dates
faster because it names individual commands, and `scripts/release.py`
bundles all of `docs/` into the release archive. It lives beside the
corpus it was recorded against, in `content/chitragupta-demo-recordings/`,
with the script that produced it.

Three groups of commands are absent from the tour on purpose:

- **The verbs that write to the sample project** (`dossier init`, `spec
  sign`, `unit accept`, `tldr write`, `registry build`), because a
  recording that leaves the repository dirty cannot be re-run.
  [WRITE-A-BOOK.md](WRITE-A-BOOK.md) walks that half in prose.
- **`review union`**, which reads an assembled `book.tex`; the sample
  project's `twin-basics` deliberately ships un-assembled.
- **The live-LLM skills and the `docling` stage.** The genre skills need
  a model, and `docling` is the slowest stage with nothing committed
  depending on it. `draft figures` is still shown, reporting that the
  stage has not run.

## 🛠 How they were made

Terminal segments: `asciinema` recorded a real shell session (80x32)
against `docs/examples/sample-project`; package resolution was shown via
`pip install --dry-run`, and everything after was a real
`python -m chitragupta.*` invocation. The dependency-resolution scroll
was sped up and the rest slowed slightly by dividing the recorded
timestamps, since the inline SVG has no speed control. The result was
rendered to SVG (`svg-term-cli --window`, a CSS `@keyframes` animation,
no `<script>`) and to video (`agg`, then `ffmpeg` at 704x648, the
recording's own size).

The browser segment drove the committed
`docs/examples/sample-project/content/topic_map.html` over CDP with
Puppeteer and headless Chrome, screenshotting each interaction. The
capture script fails the run if the number of rendered topic circles
differs from the topic count the page embeds, so a moved selector cannot
yield a video of one repeated shot, and checks after every click that
the panel names the topic just clicked. Frames are captured at 1040x957,
so every label stays inside the canvas, and scaled into the same
704x648.

The two segments are encoded separately and joined: `demo.mp4` with
`libx264 -crf 28`, then `demo.webm` (`libvpx-vp9 -crf 40 -b:v 0`).
`demo.gif` (`fps=10`, `scale=640`, one `palettegen`/`paletteuse` pass)
was re-encoded from the earlier 1280x720 `demo.mp4`; from this one it
came out at 12 MB. To re-record one segment, cut `demo.mp4` on the
keyframe where the browser segment starts and stream-copy the other half.
`demo-webapp.png` is a separate still of the topic map with topic-1
selected, captured at 1040x600 and twice the pixel density so the README
can show it near its own size.

Nothing touched a real project. The commands that write tracked files
(`draft evidence`, `draft render`, `review agenda`) were run against the
sample project and the tree restored, and a recording is kept only if
`git status` on `docs/examples/sample-project/` comes back empty.
