---
name: demo-recorder
description: Records chitragupta's feature demo for this repository's developers -- a numbered CLI tour against a throwaway copy of docs/examples/sample-project, captured with asciinema, retimed, rendered to GIF and SVG, plus a headless-Chrome capture of the offline topic map, joined into MP4 and WebM with ffmpeg. Triggers when a developer asks to record, re-record or refresh the demo, screencast or feature tour, or to add a command to it. Writes no draft and cites nothing. Developer-only -- no wheel, release zip or `chitragupta init` project carries it.
tags: [developer, demo, recording]
metadata:
  audience: developer
---

# demo-recorder

A developer tool. You are changing or exercising this repository, so
`DEVELOPER-AGENTS.md` governs the session, not `AGENTS.md`. Paths in
this skill are from the project root. The `audience: developer` line
above keeps this skill and its `scripts/` out of every distribution
(see `chitragupta/developer_skills.py`). Keep that line, and put any
new recording code under `.claude/skills/demo-recorder/scripts/` so it
is left out with them.

## What you need

| Tool | For | Where to get it |
| --- | --- | --- |
| a venv with the enrich extra | running the tour | `.venv-full/bin/python`; pass it as `PY` |
| asciinema | recording the terminal | `pip install asciinema` (2.x writes the v2 `.cast` the scripts read; on 3.x add `--output-format asciicast-v2`) |
| agg | `.cast` to GIF | the release binary from github.com/asciinema/agg |
| svg-term-cli, puppeteer-core | `.cast` to SVG; driving Chrome | `npm install --prefix "$OUT/node" svg-term-cli puppeteer-core` |
| Chrome | the topic-map capture | `npx @puppeteer/browsers install chrome-headless-shell@stable`, which needs fewer system libraries than a full Chrome; pass the binary as `CHROME_PATH` |
| ffmpeg | frames to video, joining, WebM | the system one, or `imageio-ffmpeg`'s bundled binary |

None of these is a dependency of this repository; install them outside
it. Pick an output folder `OUT` outside the checkout too. Recordings are
binaries and never go into git.

## Steps

1. **Read the tour.** `.claude/skills/demo-recorder/scripts/tour.sh`
   copies the sample project to a temporary folder and runs each step
   from there, because `corpus sync` and `enrich` rewrite the project
   they run in and the committed one is pipeline output. To change what
   the demo shows, edit the tour. Each step's command must be in
   `docs/CLI.md`, and each citekey must be one in
   `docs/examples/sample-project/papers/bibliography.bib`. Keep the
   `# N. ...` headings, which the retiming step matches.
   *Done when* the tour names only commands and citekeys that exist.
2. **Dry-run it.** `PAUSE=0 PY=<venv python> bash
   .claude/skills/demo-recorder/scripts/tour.sh`, about a minute. Read
   every step's output. A traceback, a usage error or a host path such
   as your home folder means fix the tour, then dry-run again. *Done
   when* every step prints what its heading promises, and
   `git status` shows the sample project unchanged.
3. **Record.** From the repository root:

   ```bash
   PY=<venv python> asciinema rec --cols 112 --rows 32 --idle-time-limit 2 \
     -c 'bash .claude/skills/demo-recorder/scripts/tour.sh' "$OUT/tour.cast"
   ```

   Without a terminal of your own, wrap it in `script -qec '...' /dev/null`
   with `TERM=xterm-256color` set.
4. **Retime.** Speed up the `pip install` scroll:

   ```bash
   python3 .claude/skills/demo-recorder/scripts/retime_cast.py \
     "$OUT/tour.cast" "$OUT/tour.final.cast" --start '# 1.' --end '# 2.' --speed-up 4
   ```

   `--tail` stretches everything after the span (a factor above 1
   slows it down). The script prints the old and new length.
5. **Render the terminal.**
   `agg --font-size 14 "$OUT/tour.final.cast" "$OUT/tour.gif"` and
   `"$OUT/node/node_modules/.bin/svg-term" --in "$OUT/tour.final.cast"
   --out "$OUT/tour.svg" --window`.
6. **Capture the topic map.**

   ```bash
   NODE_PATH="$OUT/node/node_modules" CHROME_PATH=<chrome> \
     node .claude/skills/demo-recorder/scripts/capture_topic_map.js \
     docs/examples/sample-project/content/topic_map.html "$OUT/frames"
   ffmpeg -y -framerate 10 -i "$OUT/frames/f%04d.png" \
     -c:v libx264 -pix_fmt yuv420p "$OUT/topic-map.mp4"
   ```

   It clicks the first five topic dots and opens the hierarchy tree,
   150 frames in all. Fewer means a selector (`#dot-N`, `#treebox`)
   moved in the viewer: fix the script.
7. **Join.** Bring the GIF to the same size and rate, then concatenate
   and make the WebM:

   ```bash
   ffmpeg -y -i "$OUT/tour.gif" -vf "fps=10,scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" \
     -c:v libx264 -pix_fmt yuv420p "$OUT/tour.mp4"
   printf "file '%s'\n" "$OUT/tour.mp4" "$OUT/topic-map.mp4" > "$OUT/concat.txt"
   ffmpeg -y -f concat -safe 0 -i "$OUT/concat.txt" -c copy "$OUT/demo.mp4"
   ffmpeg -y -i "$OUT/demo.mp4" -c:v libvpx-vp9 -b:v 0 -crf 40 "$OUT/demo.webm"
   ```

8. **Check and hand over.** `grep -c "$HOME" "$OUT/tour.final.cast"`
   must print 0. Look at a few frames of `demo.mp4`
   (`ffmpeg -ss 30 -i "$OUT/demo.mp4" -frames:v 1 "$OUT/at30.png"`).
   Report each output's path, length and size. *Done when* `demo.mp4`,
   `demo.webm`, `tour.gif` and `tour.svg` exist, play, and show no host
   path.
