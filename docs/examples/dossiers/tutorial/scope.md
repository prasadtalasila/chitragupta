# Scope

- genre: tutorial
- language: en-GB
- draft: content/drafts/labs/first-twin.md
- created: 2026-09-15
- corpus: 214 citekeys, digest `a31f0c4b77de`
- draft digest: not recorded (run `dossier stamp` once the draft is ready)

## Reader

A second-year student who has written Python before, has never used a
message queue, and is sitting at a lab machine with 45 minutes. They
have read chapter 3, so they know what an estimate and a variance are;
they have never built anything that runs continuously.

## Covers

The destination artifact: **a running digital twin of a water tank that
prints the estimated level once a second and visibly corrects itself
when you change the inflow by hand.**

Getting a Python environment up, writing the tank model, feeding it
readings from the provided simulator, and watching the estimate
converge. The capability left behind is "I have built one of these and
seen it work".

## Does not cover

Deployment, containers, or anything that runs on hardware. Deliberate:
every one of them adds an install before the lesson starts, and the
lesson has 45 minutes.

Tuning. The gain is given as a constant with a one-line justification
and a pointer onward. A student who asks why gets an answer in "where to
go next", not a detour.

Error handling beyond the one case the simulator produces. Named in the
lesson so nobody mistakes the code for production code.

## Glossary

- **Tank** -- the simulated physical asset. Always "the tank", never
  "the system" or "the plant".
- **Twin** -- the Python process holding the estimate. Always "the
  twin", never "the model", which in this lesson means only the two
  lines of arithmetic inside it.
- **Reading** -- one noisy level measurement from the simulator.
- **Estimate** -- the twin's current best level, printed each second.
