"""The token, the launch URL and the two runtime files (#1262).

The token rides in the URL fragment, which a browser never sends to the
server. The browser is opened on `open.html`, a private file that
redirects to that URL, so the token is never on a process's command line
where another user's `ps` would show it (Jupyter's approach).
`server.json` records the port for a second start's refusal; it never
holds the token.

Both files live in `content/.webapp/` (0700) as 0600 files. On Windows
those modes are no-ops and the user-profile ACLs are what protect them
(docs/SECURITY.md, "Local web workbench").
"""

import html
import json
import os
import secrets
import webbrowser
from collections.abc import Callable
from pathlib import Path

from chitragupta import config
from chitragupta._atomic_write import temp_sibling

OPEN_FILE = "open.html"
SERVER_FILE = "server.json"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def launch_url(port: int, token: str) -> str:
    return f"http://127.0.0.1:{port}/#token={token}"


def runtime_dir() -> Path:
    directory = config.CONTENT_DIR / ".webapp"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    return directory


def _write_private(path: Path, text: str) -> Path:
    """Created 0600 from the first byte, then moved into place whole."""
    tmp = temp_sibling(path)
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return path


def write_open_file(directory: Path, url: str) -> Path:
    safe = html.escape(url, quote=True)
    page = (
        '<!doctype html>\n<meta charset="utf-8">\n'
        f'<meta http-equiv="refresh" content="0;url={safe}">\n'
        f'<p><a href="{safe}">Open the chitragupta workbench</a></p>\n'
    )
    return _write_private(directory / OPEN_FILE, page)


def write_server_file(directory: Path, port: int, pid: int) -> Path:
    return _write_private(directory / SERVER_FILE, json.dumps({"port": port, "pid": pid}))


def read_server_port(directory: Path) -> int | None:
    try:
        data = json.loads((directory / SERVER_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    port = data.get("port") if isinstance(data, dict) else None
    return port if isinstance(port, int) else None


def remove_runtime_files(directory: Path) -> None:
    for name in (OPEN_FILE, SERVER_FILE):
        (directory / name).unlink(missing_ok=True)


def open_browser(page: Path, opener: Callable[[str], bool] = webbrowser.open) -> bool:
    return opener(page.as_uri())
