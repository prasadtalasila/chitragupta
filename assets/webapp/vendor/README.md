# Vendored: cytoscape.js

`cytoscape.min.js` is [cytoscape.js](https://js.cytoscape.org/) **3.34.2**,
fetched once from
`https://unpkg.com/cytoscape@3.34.2/dist/cytoscape.min.js` and committed
verbatim -- the MIT licence header at the top of the file is the
Cytoscape Consortium's own.

Vendored rather than fetched for the reason `assets/csl/ieee.csl` is:
the app directory `corpus discover --app` writes must keep working from
`file://` on a machine with no network, forever, and a CDN URL in
`index.html` would break that contract the first time the viewer is
offline. `chitragupta/discover/_app.py` copies this file (and the rest
of `assets/webapp/`) into the output directory unchanged.

To upgrade: replace the file with the new pinned version, update the
version in this README and in `docs/TOPIC-DISCOVERY.md`, and re-run the
`tests/test_discover_app.py` suite -- the copy is asserted byte-identical
there, so a stale copy in an output directory is detectable by size.
