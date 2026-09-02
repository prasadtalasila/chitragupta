# Scope

- genre: tutorial
- language: en-GB
- draft: content/drafts/dt-overview/staleness-tutorial.md
- created: 2026-09-02
- corpus: 5 citekeys, digest `ded95cf5e89c`
- draft digest: `197d0946b059`

## Reader

A developer at a keyboard with Python installed, twenty minutes, and no
digital-twin background -- they follow the steps and end with a working
staleness monitor they watched catch a failure.

## Covers

One path: simulate a state file, read it naively, read it with
staleness marking, break the link, see the difference.

## Does not cover

Synchronisation strategies, reconnection replay, and anything about
choosing the staleness budget -- the lesson builds one mechanism and
stops.

## Glossary

- **Staleness** -- the age of the twin's newest synchronised value at
  the moment of a read.
