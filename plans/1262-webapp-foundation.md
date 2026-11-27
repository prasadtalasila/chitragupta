# WA-2: the loopback-only, token-authenticated server foundation (#1262)

Status: **design, approved by the owner 2026-11-27.**
Epic: #1260. Built before WA-1 (#1261), which adds the panes and the
agent on top of it.

## Intent

`chitragupta webapp` will run a coding agent behind an HTTP server
(WA-1). Whoever can send that server an authenticated request can prompt
an agent that runs commands in the project, so the server must be
reachable only from the author's own browser on the author's own
machine, with a secret it printed for them. WA-2 builds that server and
nothing else: every later feature (the panes, the agent, serving the
topic graph) plugs into it as a route and inherits its controls without
being able to skip them.

The owner's framing: there is one **core** (the modules under
`chitragupta/`), and the CLI and the web app are two front ends on it.
The web app reads through the same functions the CLI calls and never
duplicates their logic. The core stays at its own tier; only the web
front end adds dependencies (FastAPI and uvicorn).

## Goals

1. `chitragupta webapp [--port N] [--no-browser]` starts a server on
   `127.0.0.1` only and opens the browser on a placeholder page that
   proves the controls work end to end.
2. Every request passes the same checks, in the same order, before any
   route sees it (approach B below).
3. Built on FastAPI + uvicorn, installed as an optional `webapp` extra.
   The core modules it calls stay tier 1; without the extra, `chitragupta
   webapp` refuses with the install command and nothing else breaks.

## Non-goals

- Any pane, any corpus read beyond the project name, any agent: WA-1.
- Streaming responses: WA-1 adds them (`StreamingResponse`). WA-2 only
  makes sure the middleware passes a streamed body through untouched,
  with a test.
- Serving the topic-graph app: a later sub-issue of #1260.

## Anti-goals (a failure even if it works)

- Any way to bind a non-loopback address: flag, `config.toml` key,
  environment variable.
- A route that can be reached without passing the checks.
- Web-app-only logic that duplicates what a CLI module already does.
- A web dependency imported by anything outside `chitragupta/webapp/`,
  or at `chitragupta --help` time.
- Authentication done per route (`Depends(...)`) instead of in the one
  middleware.
- A cookie, or the token in a query string, a log line or a process's
  command line.

## Decisions (made with the owner, 2026-11-27)

| Topic | Decision |
| --- | --- |
| Network | Loopback only, no override of any kind |
| Command | `chitragupta webapp`, a package-level command in `COMMANDS` beside `init` and `doctor` (not a top-level `--webapp` flag). #1260, #1261 and #1262 are reworded to match |
| `--port N` | Optional. Absent: bind port `0`, so the OS picks a free port. Present: that port or exit 2 with a clear message if it is taken or outside 1–65535. Never falls back to another port, so the printed URL is always the one asked for |
| `--no-browser` | Print the URL, do not open a browser. Needed by headless tests and by SSH-tunnel use |
| Project | Mandatory: outside a chitragupta project (no `config.toml`, `config.PROJECT_MARKER`) it refuses with exit 2 and says to run `chitragupta init` |
| Stack | FastAPI + uvicorn (chosen 2026-11-27 over the standard library, Starlette alone, and Hypercorn). FastAPI for pydantic validation of WA-1's `POST` bodies; uvicorn as the most common pairing and because it carries no unused HTTP/2 parser |
| Dependencies | An optional `webapp` extra in `pyproject.toml` (`fastapi`, `uvicorn`; `httpx` in the dev group for `TestClient`), like the `images` extra. Imported lazily inside `chitragupta/webapp/`, so the CLI and the gate chain never load them. Without the extra, `chitragupta webapp` exits 2 naming `pip install 'chitragupta-cli[webapp]'` |
| Interpreter | The core modules the web app calls stay tier 1. A later feature that needs the `enrich` extra upgrades itself when present, as `corpus discover`'s semantic rung does |
| Instances | One server per project. A second start exits 2 with "already running on port N; use the URL printed in its terminal" |
| What WA-2 shows | Option A: a placeholder page that calls one authenticated endpoint and shows the project name and the version. The command is hidden from `chitragupta --help` until WA-1 lands |
| Request handling | Approach B, as one pure ASGI middleware, below |
| Windows | Supported natively. File modes (`0700`/`0600`) are no-ops there, so the launch file relies on the user-profile ACLs, and Ctrl-C is the only stop signal. Both are recorded as residual risks; tests that check POSIX modes skip on Windows |
| Security docs | A "Local web workbench" section in `docs/SECURITY.md` (controls and #1262's residual risks), although that page is outside the mkdocs site |

## Approaches considered

Request handling:

- **B, chosen: one check point.** One pure ASGI middleware wraps the
  whole app (routers and the static mount included) and runs every check
  in a fixed order before routing. Routes never authenticate. New
  features add routes and cannot reorder or skip a check.
- **A: checks per route** (`Depends(check_token)`, FastAPI's usual
  idiom). One forgotten `Depends` in a later feature opens a route.
  Rejected.

Server stack (the owner weighed each):

- **FastAPI + uvicorn, chosen.** Typed request validation for WA-1;
  async streaming with client-disconnect detection for the agent; the
  most common pairing.
- **Standard library `ThreadingHTTPServer`.** Tier 1 and no dependencies,
  but a thread and a queue per agent stream, late disconnect detection,
  and an HTTP parser its own docs call unfit for production. Rejected.
- **Starlette + uvicorn.** Fewest dependencies among the frameworks;
  request bodies validated by hand. Rejected for FastAPI's validation.
- **Hypercorn instead of uvicorn.** Its HTTP/2 and HTTP/3 need TLS to
  reach a browser, so they buy nothing here, and its h2c parser is
  reachable pre-auth by a non-browser local process. Rejected.
- **Relying on `.venv-full`'s `enrich` extra** (uvicorn and aiohttp
  arrive through chromadb). Rejected: transitive dependencies a chromadb
  release can drop, and several GB for a reader.

## The design

### Module layout

A new package `chitragupta/webapp/`, each module under C2's 250 lines of
code and every function under C1's 25 statements
(`docs/CODE-STANDARDS.md`):

| Module | Holds |
| --- | --- |
| `__main__.py` | `main(argv)`: argparse for `--port` / `--no-browser`, the project check, the extra check, the lock, start and shutdown. Imports nothing from FastAPI or uvicorn at module level |
| `_server.py` | Binds a socket to the constant `127.0.0.1` itself, asserts the bound address is loopback, and hands the socket to `uvicorn.Server.serve(sockets=[sock])`. uvicorn's own `host` setting is never used |
| `_guards.py` | Pure checks on a scope's method, path and headers: Host, method, Origin, token, body size. Each returns `None` or a refusal (status, reason). No FastAPI import, so they test without it |
| `_middleware.py` | The one pure ASGI middleware: runs the guards in fixed order, sends refusals, and adds the security headers to every `http.response.start`, streamed or not. Not `BaseHTTPMiddleware`, which mishandles streaming |
| `_app.py` | `build_app(token, port)`: `FastAPI(docs_url=None, redoc_url=None, openapi_url=None, debug=False)`, the `/api/` router, the `StaticFiles` mount of `assets/webapp/workbench/`, wrapped by the middleware |
| `_launch.py` | Token generation, the launch file, opening the browser |

`chitragupta/__main__.py` gains `"webapp": "chitragupta.webapp.__main__"`
in `COMMANDS`; `chitragupta/command_help.py` gains its entry, kept out of
the `--help` tree until WA-1.

### The request pipeline (fixed order, in the middleware)

1. **Host.** Exactly `127.0.0.1:<port>` or `localhost:<port>`, else
   `403`, empty body. Runs before everything, static files included.
   Closes DNS rebinding; also refuses forwarders that rewrite `Host`.
2. **Method.** `GET` or `POST`, else `405`.
3. **Static or API.** A path outside `/api/` goes to the `StaticFiles`
   mount of `assets/webapp/workbench/` with no token (it holds no project
   data). `StaticFiles` refuses traversal and lists no directories; a test
   still sends `..` and encoded variants.
4. **Origin** (`/api/` only). If present it must be
   `http://127.0.0.1:<port>` or `http://localhost:<port>`; on `POST` it
   must be present. Else `403`.
5. **Token** (`/api/` only). `Authorization: Bearer <token>`, compared
   with `hmac.compare_digest`, else `401`.
6. **Body size** (`/api/` `POST`). `Content-Length` above 1 MiB is `413`
   before the body is read; a missing `Content-Length` on `POST` is
   `411`.
7. **Route.** FastAPI routes and validates the body (`422` on a bad
   one).

Starlette's `TrustedHostMiddleware` is not used: it compares the host
name without the port, looser than check 1.

Every response, refusals included, carries:
`Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and
on `/api/` `Cache-Control: no-store`. No response carries an
`Access-Control-*` header. Relaxing a directive needs a recorded reason
beside it.

uvicorn's access log is off (`access_log=False`); the middleware logs
refusals to the package logger at debug level, never with headers.

### Token and launch

- `secrets.token_urlsafe(32)`, in memory only, new on every start.
- Launch URL: `http://127.0.0.1:<port>/#token=<token>`. The fragment
  never reaches the server.
- The browser is opened on `content/.webapp/open.html`, a file that
  redirects to the launch URL, so the token is never on a command line
  (Jupyter's approach). Directory mode `0700`, file mode `0600`, written
  with `chitragupta/_atomic_write.py`.
- The terminal prints the launch URL once (for `--no-browser`, a second
  browser, or a closed tab). A lost token means restarting the server.
- The page (`assets/webapp/workbench/token.js`, pure and tested under
  `node --test`) reads the fragment, stores the token in
  `sessionStorage`, removes it from the address bar with
  `history.replaceState`, and sends it as a bearer header on every
  `fetch`. No cookie is set: cookies on `127.0.0.1` are shared across
  ports.

### One server per project

`runlock.pipeline_lock` already gives a cross-process mutex that a
`kill -9` releases at once. WA-2 uses the same class with its own path,
`content/.webapp/server.lock`, so it never takes the corpus writer lock
and `corpus sync` keeps working alongside. `runlock` itself is not
changed.

*Builder-check call:* `webapp` catches `AlreadyRunning` and writes its
own refusal from `content/.webapp/server.json` (`{"port", "pid"}`, mode
`0600`, never the token), written once the port is bound and deleted on
shutdown. The lock is taken before binding, so a second start that
races the first in that window finds no `server.json` and says "another
webapp is starting in this project; try again in a moment".

### Shutdown

Ctrl-C (and `SIGTERM`, through uvicorn's own handling) stops the
server, deletes `open.html` and `server.json`, releases the lock, exits
0.

### The placeholder page

`assets/webapp/workbench/index.html`, `workbench.js`, `token.js`,
`style.css`. No inline script or handler. It calls `GET /api/status`
and shows `{"project": <project directory name>, "version": <installed
version>}` with `textContent`. With no token, or a `401`, it says to
open the URL printed in the terminal.

## Tests

- pytest, 100% line and branch: the guards table-driven with no FastAPI;
  the app through `TestClient` with raw `Host`/`Origin` values
  (`evil.example:<port>` included); a streamed test response passing the
  middleware with headers added; `/docs`, `/redoc`, `/openapi.json` all
  `404`; `debug` off; a taken `--port`; an out-of-range `--port`; outside
  a project; the extra missing; the second-instance refusal; launch file
  modes on POSIX; the bind constant and the post-bind assertion; one
  real uvicorn start on port `0` driven with `http.client`.
- **Route census:** a test walks `app.routes` and asserts every `/api/`
  route refuses a request without the token, and that nothing else is
  mounted but the static files. A route added later without protection
  fails here, whatever convention its author followed.
- CI installs the `webapp` extra on every pytest leg, Windows included,
  so the 100% bar covers it.
- `node --test` over `token.js` and `workbench.js` with fake
  `location`, `history` and `sessionStorage`, including a project name
  that is an HTML payload, rendered as text.
- *Builder-check call:* `assets/webapp/workbench/*.js` follows the
  topic-graph modules' conventions (UMD, pure logic split from DOM
  wiring) and joins the same `node --test` coverage step and C1/C2
  scan, by widening their globs in `ci.yml`, `scripts/check_local.sh`
  and `scripts/webapp_code_standards.js`.
- `tests/webapp/code_standards.test.js` already ratchets
  `assets/webapp/`; add a check that no file under `workbench/` uses
  `innerHTML`, inline handlers or inline scripts.
- The headless-browser smoke test (`tests/webapp/browser_smoke.test.js`
  pattern): token gone from the address bar, no cookie, status shown.
  It runs on a developer host (`scripts/check_local.sh`), not in CI,
  like the existing one.

## Documentation and release

- *Builder-check call:* `docs/CLI.md` gets the `webapp` command,
  loopback-only, and the SSH tunnel `ssh -L <port>:127.0.0.1:<port>
  <host>` in WA-1, when the command leaves hiding. WA-2 adjusts any
  docs-agreement test that would otherwise demand an entry for a hidden
  command, and says why beside the adjustment.
- `docs/SECURITY.md`: a "Local web workbench" section with the controls
  and #1262's residual risks, plus the two Windows ones.
- `docs/PACKAGING.md` / install docs: the `webapp` extra, if the page
  lists the other extras.
- Issues #1260, #1261 and #1262 reworded: `chitragupta webapp` instead of
  `--webapp`, the `--port` / `--no-browser` flags, one server per
  project, FastAPI + uvicorn as a `webapp` extra.
- New command: MINOR version bump.

## Left to the builder

- Exact names of the helpers and the refusal type.
- Version ranges for `fastapi` and `uvicorn` in the extra (current
  releases, PEP 621 ranges, re-locked with `uv lock`).
- The wording of every refusal message, provided each says what to do.
- How the command is kept out of the `--help` tree.
