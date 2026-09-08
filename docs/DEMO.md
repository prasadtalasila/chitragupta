# 🎬 Demo recording

Status: **reference.** Written 2026-09-08.

**Written for** anyone who wants to see the pipeline run before reading
the rest of the documentation. One pass through the spine -- corpus
sync, topic discovery, an already-drafted unit and its dossier, the
citation gate, the review agenda, one more review aid -- then a look at
the offline topic-graph viewer in a browser. Recorded against the
committed sample project ([docs/examples/](examples/README.md)), so
every command in it is real and every citekey it cites is real; nothing
here was invented for the recording.

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

## 🛠 How it was made

Terminal segment: `asciinema` recorded a real shell session against
`docs/examples/sample-project` (installed package resolution shown via
`pip install --dry-run`, everything after that a real
`python -m chitragupta.*` invocation), then the boring, non-narrative
span (the dependency-resolution scroll) was sped up by dividing its
recorded event timestamps -- not by a player's speed control, since the
inline SVG has none -- before rendering to SVG (`svg-term-cli`, a CSS
`@keyframes` animation, no `<script>`) and to video (`agg`, then
`ffmpeg`). The browser segment drove the committed
`content/topic_map.html` over CDP with Puppeteer against a headless
Chrome, screenshotting each interaction and assembling the frames into
video with `ffmpeg`. Nothing in either segment touched a real project:
the sample project's committed drafts, dossiers and reviews were only
read, and the one command that writes tracked files
(`review agenda`) was re-run to its committed state afterwards.
