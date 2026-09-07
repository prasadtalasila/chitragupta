"""The two views that write a file instead of printing one: `--html`
(one static page) and `--app` (the interactive directory).

Together here because they share one contract, and reading them side by
side is how it stays shared: nothing reaches stdout before the write, a
failure line goes to stderr in both modes because diagnostics are never
part of a payload, and the success report is shaped by `--json` because
under that flag it *is* the payload. Both take the `--origins` selection
and hand it to the builder, so an exported artefact contains what it
says it contains rather than hiding topics on screen (#742).

Split out of `__init__` when the module crossed the 250-code-line limit
(docs/CODE-STANDARDS.md): "write the graph somewhere and report where"
is one responsibility, and it is not the resolution ladder's.
"""

import sys

from chitragupta.discover import _app, _page
from chitragupta.discover._views import emit


def app_view(args, origins: set) -> int:
    try:
        written = _app.write_app(args.app, origins)
    except OSError as failure:
        print(f"Could not write the app to {args.app}: {failure}", file=sys.stderr)
        return 1
    emit(args, {"written": written}, f"written: {written}")
    return 0


def html_view(args, origins: set) -> int:
    try:
        written = _page.write_page(args.html, origins)
    except OSError as failure:
        print(f"Could not write the page to {args.html}: {failure}", file=sys.stderr)
        return 1
    emit(args, {"written": written}, f"written: {written}")
    return 0
