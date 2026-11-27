"""The two views that write a file instead of printing one: `--html`
(one static page) and `--app` (the interactive directory).

One shared contract: nothing reaches stdout before the write, a failure
line goes to stderr in both modes, and the success report is shaped by
`--json` because it then *is* the payload. Both filter by `--origins`
so an export contains what it says (#742).
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
