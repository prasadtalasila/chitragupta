# WA-2 Loopback Server Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
superpowers:subagent-driven-development (recommended) or
superpowers:executing-plans to implement this plan task-by-task. Steps use
checkbox (`- [ ]`) syntax for tracking.

**Goal:** `chitragupta webapp [--port N] [--no-browser]` starts a FastAPI app on
uvicorn, bound to `127.0.0.1` only, behind one ASGI middleware that checks Host,
method, Origin, bearer token and body size before any route, and serves a
placeholder page that proves it end to end.

**Architecture:** Pure guard functions (`_guards.py`) run in fixed order inside
one plain ASGI middleware (`_middleware.py`) that wraps the whole FastAPI app
(`_app.py`). We bind the socket ourselves (`_server.py`) and hand it to uvicorn.
`__main__.py` does the project check, the extra check, a per-project lock, the
launch file and the shutdown cleanup (`_launch.py`).

**Tech Stack:** Python ≥3.12, FastAPI + uvicorn (new optional `webapp` extra),
`httpx` (dev, for `TestClient`), pytest at 100% line and branch, `node --test`
for `assets/webapp/workbench/*.js`.

**Spec:** `plans/1262-webapp-foundation.md` (read it first; this plan argues
from it). Issue #1262, epic #1260.

## Global Constraints

- Bind address is the constant `"127.0.0.1"`. No flag, `config.toml` key or
  environment variable changes it.
- Allowed Host values: exactly `127.0.0.1:<port>` and `localhost:<port>`.
  Allowed Origins: `http://127.0.0.1:<port>` and `http://localhost:<port>`.
- Token: `secrets.token_urlsafe(32)`, new per start, never in a query string,
  log line, cookie or command line.
- Launch URL: `http://127.0.0.1:<port>/#token=<token>`.
- Body limit: `1_048_576` bytes.
- CSP, verbatim: `default-src 'self'; script-src 'self'; style-src 'self';
  connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none';
  form-action 'none'; frame-ancestors 'none'`. Also `X-Content-Type-Options:
  nosniff`, `Referrer-Policy: no-referrer`, and on `/api/` `Cache-Control:
  no-store`. No `Access-Control-*` header ever.
- `FastAPI(docs_url=None, redoc_url=None, openapi_url=None, debug=False)`. Auth
  never via `Depends`. Middleware is plain ASGI, never `BaseHTTPMiddleware`.
- `fastapi`/`uvicorn` are imported only inside `chitragupta/webapp/`, and never
  at module level of `chitragupta/webapp/__main__.py`.
- Runtime files live in `config.CONTENT_DIR / ".webapp"` (dir `0o700`;
  `open.html`, `server.json` `0o600`; `server.lock`). POSIX mode assertions skip
  on `win32`.
- Exit codes: `0` clean stop, `2` every refusal (outside a project, extra
  missing, port taken/out of range, already running).
- C1: ≤25 statements per function; C2: ≤250 lines of code per module
  (`docs/CODE-STANDARDS.md`).
- The command is absent from the `chitragupta --help` tree until WA-1.
- Version: `7.2.1` → `7.3.0` (MINOR: new command).
- Rebase onto `origin/main` before Task 1 and before opening the PR.

## Review Focus

1. **Duplicate security headers** (two `Host`, two `Origin`, two
   `Authorization`): refused `400`, never "first one wins". Test in Task 2.
2. **Non-ASCII bytes in `Authorization`**: `401`, not a `500` from
   `hmac.compare_digest` on non-ASCII `str`. Compare bytes. Test in Task 2.
3. **A WebSocket upgrade**: refused (`websocket.close`, code `1008`) before
   reaching the app. Test in Task 3.
4. **Path spellings around `/api`** (`/api`, `//api/status`, `/API/status`,
   `/x/../api/status`, `/%2e%2e/api/status`): never a `200` without the token.
   Test in Task 4.
5. **Leftover runtime files after a `kill -9`** (`server.json`, `open.html`
   present, lock free): the next start succeeds and overwrites them. Test in
   Task 6.

---

### Task 1: The `webapp` extra and the command skeleton

**Files:**

- Modify: `pyproject.toml` (new extra `webapp`; `httpx` in `dev`; version
  `7.3.0`), `uv.lock` (`uv lock`)
- Modify: `scripts/install_full_pipeline.sh:718` and `:976` (add `--extra
  webapp` to both `uv_sync` calls)
- Modify: `chitragupta/__main__.py` (`COMMANDS["webapp"] =
  "chitragupta.webapp.__main__"`, docstring line)
- Modify: `chitragupta/command_help.py` (a `"webapp"` entry, kept out of the
  `--help` tree)
- Create: `chitragupta/webapp/__init__.py`, `chitragupta/webapp/__main__.py`
- Test: `tests/test_webapp_cli.py`, `tests/test_package_entrypoint.py`

**Interfaces:**

- Produces: `chitragupta.webapp.__main__.main(argv: list[str] | None = None) ->
  int`; `build_parser() -> argparse.ArgumentParser` with `--port` (type
  `port_arg`, default `0`) and `--no-browser` (store_true); `port_arg(value:
  str) -> int` (accepts 1–65535, else `argparse.ArgumentTypeError`);
  `REQUIRED_MODULES = ("fastapi", "uvicorn")`; `missing_extra() -> list[str]`.
- Produces: `EXIT_REFUSED = 2`.

- [ ] **Step 1: Write the failing tests** in `tests/test_webapp_cli.py`:
  - `test_port_arg_bounds`: `port_arg("1") == 1`, `port_arg("65535") == 65535`;
    `"0"`, `"65536"`, `"-1"`, `"abc"` raise `argparse.ArgumentTypeError`.
  - `test_outside_a_project_refuses(monkeypatch, capsys)`: patch
    `config.discover_project_root` to return `None`; `main(["--no-browser"]) ==
    2`; stderr contains `chitragupta init`.
  - `test_missing_extra_refuses(monkeypatch, capsys)`: patch
    `importlib.util.find_spec` to return `None` for `fastapi`;
    `main(["--no-browser"]) == 2`; stderr contains `pip install
    'chitragupta-cli[webapp]'`.
  - `test_main_does_not_import_web_stack`: in a subprocess
    (`tests.conftest.run_python`), `import chitragupta.webapp.__main__` and
    `chitragupta.__main__ --help`; assert `"fastapi" not in sys.modules` and
    `"uvicorn" not in sys.modules`.
  - In `tests/test_package_entrypoint.py`: `"webapp" in entry.COMMANDS`;
    `"webapp"` absent from the rendered `chitragupta --help` text;
    `entry.main(["webapp", "--help"])` exits 0 and prints `--port`.

- [ ] **Step 2: Run them, expect failure**
  Run: `uv run --active --no-sync python -m pytest tests/test_webapp_cli.py
  tests/test_package_entrypoint.py -q`
  Expected: FAIL (`ModuleNotFoundError: chitragupta.webapp`).

- [ ]  **Step 3: Implement.** `pyproject.toml`: `webapp = ["fastapi>=…,<…",
      "uvicorn>=…,<…"]` with PEP 621 ranges on the current releases (look them
      up on PyPI; lower bound = current, upper = next major, or next minor while
      `0.x`); `"httpx>=…,<…"` in `dev`. Run `uv lock`. Check that every pytest
      leg in `ci.yml`, the Windows one included, installs through a stage that
      now passes `--extra webapp`; add it wherever one does not. `main` for now:
      parse, project check, extra check, return `0`; Task 6 extends it. Hide
      from help the way `chitragupta/__main__.py:tree_rows` reads `HELP`: skip
      names in a module-level `HIDDEN = frozenset({"webapp"})` there, with a
      comment naming WA-1 (#1261) as when it goes.

- [ ] **Step 4: Run, expect pass**
  Run: same command. Expected: PASS. Also `uv lock --check` passes.

- [ ] **Step 5: Commit**

  ```bash
  git add pyproject.toml uv.lock scripts/install_full_pipeline.sh chitragupta/__main__.py chitragupta/command_help.py chitragupta/webapp tests/test_webapp_cli.py tests/test_package_entrypoint.py
  git commit -m "Add the hidden webapp command and its optional extra (#1262)"
  ```

### Task 2: The guards

**Files:**

- Create: `chitragupta/webapp/_guards.py`
- Test: `tests/test_webapp_guards.py`

**Interfaces:**

- Produces (no FastAPI import in this module):
  - `@dataclass(frozen=True) class Refusal: status: int; reason: str`
  - `Headers = Mapping[str, list[str]]` (lower-case names, latin-1-decoded
    values)
  - `MAX_BODY = 1_048_576`
  - `header_map(raw: Iterable[tuple[bytes, bytes]]) -> dict[str, list[str]]`
  - `is_api(path: str) -> bool` (true for `/api` and anything under `/api/`)
  - `check_host(headers: Headers, port: int) -> Refusal | None`
  - `check_method(method: str) -> Refusal | None`
  - `check_origin(method: str, headers: Headers, port: int) -> Refusal | None`
  - `check_token(headers: Headers, token: str) -> Refusal | None`
  - `check_body_size(method: str, headers: Headers) -> Refusal | None`
  - `run_checks(method: str, path: str, headers: Headers, port: int, token:
    str) -> Refusal | None` (order: host, method, then on API only: origin,
    token, body size)

- [ ]  **Step 1: Write failing table-driven tests**, one `parametrize` per
      check, `PORT = 8123`, `TOKEN = "t" * 43`:
  - host: `["127.0.0.1:8123"]` and `["localhost:8123"]` → `None`;
    `["evil.example:8123"]`, `["127.0.0.1:9999"]`, `["127.0.0.1"]`, `[]`,
    `["127.0.0.1:8123", "127.0.0.1:8123"]` → `Refusal(403, …)` except the
    duplicate → `Refusal(400, …)`.
  - method: `GET`, `POST` → `None`; `PUT`, `DELETE`, `OPTIONS`, `HEAD` → `405`.
  - origin: GET with no Origin → `None`; POST with no Origin → `403`;
    `http://localhost:8123` → `None`; `http://evil.example`, `null`,
    `http://127.0.0.1:9999` → `403`; two Origin values → `400`.
  - token: `Bearer <TOKEN>` → `None`; missing, `Bearer`, `Bearer wrong`,
    `bearer <TOKEN>`, `Basic <TOKEN>`, `Bearer <TOKEN>` plus a trailing
    space → `401`; `"Bearer \xe9"` → `401` (no exception); two Authorization
    values →
    `400`.
  - body: GET → `None`; POST `content-length: 10` → `None`; POST `1048577` →
    `413`; POST missing → `411`; POST `abc` or `-1` → `400`.
  - `run_checks`: a static GET (`/index.html`) with no token and no Origin →
    `None`; `/api/status` with good Host and no token → `401`; bad Host on a
    static path → `403` (Host runs first).

- [ ] **Step 2: Run, expect failure**
  Run: `uv run --active --no-sync python -m pytest tests/test_webapp_guards.py
  -q`. Expected: FAIL (module missing).

- [ ]  **Step 3: Implement** the functions above. `check_token` compares
      `value.encode("utf-8", "surrogateescape")` against `f"Bearer
      {token}".encode()` with `hmac.compare_digest`. The scheme is
      case-sensitive (`Bearer`): the page is the only client.

- [ ]  **Step 4: Run, expect pass**, with `--cov=chitragupta/webapp/_guards.py
      --cov-branch --cov-fail-under=100`.

- [ ] **Step 5: Commit** `git commit -m "Add the webapp request guards (#1262)"`

### Task 3: The middleware

**Files:**

- Create: `chitragupta/webapp/_middleware.py`
- Test: `tests/test_webapp_middleware.py`

**Interfaces:**

- Consumes: `run_checks`, `header_map`, `is_api`, `Refusal` (Task 2).
- Produces: `class GuardMiddleware: __init__(self, app: ASGIApp, *, port: int,
  token: str)`; `async __call__(scope, receive, send)`; `CSP: str` (the constant
  above); `SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...]`.

- [ ]  **Step 1: Write failing tests**, wrapping a tiny Starlette app (`/api/ok`
      → JSON, `/api/stream` → `StreamingResponse` of three chunks, `/page` →
      text) in `GuardMiddleware`, through `fastapi.testclient.TestClient(app,
      base_url="http://127.0.0.1:8123")`:
  - `test_refusal_has_security_headers_and_empty_body`: `Host:
    evil.example:8123` → 403, body `b""`, CSP header equals `CSP`, `nosniff`,
    `no-referrer`.
  - `test_allowed_api_response_gets_no_store`: `/api/ok` with token → 200,
    `cache-control: no-store`, CSP present; `/page` → 200, CSP present, no
    `cache-control: no-store`.
  - `test_streamed_body_passes_untouched`: `/api/stream` with token → body is
    the three chunks joined, CSP present.
  - `test_no_cors_headers`: no response header name starts with
    `access-control-`, for allowed and refused requests.
  - `test_websocket_refused`: `client.websocket_connect("/api/ws")` raises
    `WebSocketDisconnect` with code `1008`; the inner app is never called
    (assert a flag).
  - `test_lifespan_passes_through`: a `lifespan` scope reaches the inner app.

- [ ] **Step 2: Run, expect failure.**

- [ ]  **Step 3: Implement.** On `http`: build headers with
      `header_map(scope["headers"])`, call `run_checks(scope["method"],
      scope["path"], …)`; on a refusal, send `http.response.start` (status,
      `SECURITY_HEADERS`, `content-length: 0`) and an empty
      `http.response.body`; log `reason` at debug, never headers. Otherwise call
      the app with a wrapped `send` that appends `SECURITY_HEADERS` (and
      `no-store` when `is_api`) to `http.response.start`. On `websocket`: send
      `{"type": "websocket.close", "code": 1008}` without calling the app.

- [ ] **Step 4: Run, expect pass** at 100% for the module.

- [ ]  **Step 5: Commit** `git commit -m "Add the webapp guard middleware
      (#1262)"`

### Task 4: The app, the status route, the static mount, the route census

**Files:**

- Create: `chitragupta/webapp/_app.py`
- Create (placeholder content, finished in Task 7):
  `assets/webapp/workbench/index.html`
- Test: `tests/test_webapp_app.py`

**Interfaces:**

- Consumes: `GuardMiddleware` (Task 3).
- Produces: `WORKBENCH_DIR = config.shipped("assets", "webapp", "workbench")`;
  `status_payload() -> dict[str, str]` returning `{"project":
  config.PROJECT_ROOT.name, "version": chitragupta.__main__._version()}`;
  `build_app(*, port: int, token: str, static_dir: Path = WORKBENCH_DIR) ->
  GuardMiddleware` whose `.app` is the `FastAPI` instance.

- [ ]  **Step 1: Write failing tests** (`TestClient`,
      `base_url="http://127.0.0.1:8123"`, header `Authorization: Bearer
      <token>`):
  - `test_status_with_token`: `GET /api/status` → 200, JSON keys exactly
    `{"project", "version"}`.
  - `test_status_without_token`: → 401.
  - `test_docs_endpoints_absent`: `/docs`, `/redoc`, `/openapi.json`,
    `/docs/oauth2-redirect` → 404 (with token too).
  - `test_debug_off`: `build_app(...).app.debug is False`.
  - `test_index_served_without_token`: `GET /` → 200, `text/html`.
  - `test_static_traversal_refused`: `/../config.toml`, `/%2e%2e/config.toml`,
    `/..%2fconfig.toml` → never 200, body never contains `[` from config.toml.
  - `test_api_path_spellings` (Review Focus 4): `/api`, `//api/status`,
    `/API/status`, `/x/../api/status`, `/%2e%2e/api/status` without token → none
    is 200 with a JSON body containing `"project"`.
  - `test_route_census`: for every route in `app.app.routes` that is an
    `APIRoute`, its path starts with `/api/` and a tokenless request to it is
    401; every other route is the static `Mount` at `/`. A new route outside
    `/api/` fails this test.

- [ ] **Step 2: Run, expect failure.**

- [ ]  **Step 3: Implement** `build_app`: `FastAPI(docs_url=None,
      redoc_url=None, openapi_url=None, debug=False)`, an
      `APIRouter(prefix="/api")` with `GET /status`, then `app.mount("/",
      StaticFiles(directory=static_dir, html=True))`, returned wrapped in
      `GuardMiddleware(app, port=port, token=token)`. Module docstring states:
      routes never authenticate; the middleware does.

- [ ] **Step 4: Run, expect pass** at 100%.

- [ ]  **Step 5: Commit** `git commit -m "Add the webapp app with its status
      route and route census (#1262)"`

### Task 5: Launch files and browser opening

**Files:**

- Create: `chitragupta/webapp/_launch.py`
- Test: `tests/test_webapp_launch.py`

**Interfaces:**

- Produces: `new_token() -> str`; `launch_url(port: int, token: str) -> str`;
  `runtime_dir() -> Path` (`config.CONTENT_DIR / ".webapp"`, created `0o700`);
  `write_open_file(directory: Path, url: str) -> Path` (`open.html`, `0o600`);
  `write_server_file(directory: Path, port: int, pid: int) -> Path`
  (`server.json`, `{"port": …, "pid": …}`, `0o600`);
  `read_server_port(directory: Path) -> int | None`;
  `remove_runtime_files(directory: Path) -> None` (both files, missing ones
  ignored); `open_browser(page: Path, opener: Callable[[str], bool] =
  webbrowser.open) -> bool`.

- [ ] **Step 1: Write failing tests** (use `isolated_config`):
  - `test_token_shape`: two calls differ; `len(new_token()) >= 43`.
  - `test_launch_url`: `launch_url(8123, "abc") ==
    "http://127.0.0.1:8123/#token=abc"`.
  - `test_open_file_redirects_and_is_private`: content contains the URL in a
    `<meta http-equiv="refresh">` and a visible link; on POSIX, mode `0o600` and
    dir mode `0o700`.
  - `test_server_file_has_no_token`: JSON is exactly `{"port", "pid"}`;
    `read_server_port` returns the port; returns `None` when missing or
    unparseable.
  - `test_browser_gets_a_file_uri_not_the_token`: a fake opener records its
    argument; it starts with `file://` and does not contain the token.
  - `test_remove_is_idempotent`: removing twice raises nothing.

- [ ] **Step 2: Run, expect failure.**

- [ ]  **Step 3: Implement.** Write private files by `os.open(tmp,
      O_WRONLY|O_CREAT|O_EXCL, 0o600)` then `os.replace`, reusing
      `_atomic_write.temp_sibling` for the temp name. `open_browser` passes
      `page.as_uri()`.

- [ ] **Step 4: Run, expect pass** at 100%.

- [ ]  **Step 5: Commit** `git commit -m "Add webapp launch files that keep the
      token off command lines (#1262)"`

### Task 6: Binding, serving, the lock, and shutdown

**Files:**

- Create: `chitragupta/webapp/_server.py`
- Modify: `chitragupta/webapp/__main__.py`
- Test: `tests/test_webapp_server.py`, `tests/test_webapp_cli.py`

**Interfaces:**

- Consumes: `build_app` (Task 4), everything in `_launch` (Task 5),
  `runlock.pipeline_lock`, `runlock.AlreadyRunning`.
- Produces: `LOOPBACK = "127.0.0.1"`; `class PortUnavailable(OSError)`;
  `bind_socket(port: int) -> socket.socket` (binds `LOOPBACK`, `listen()`,
  raises `PortUnavailable` on `EADDRINUSE`/`EACCES`, raises `RuntimeError` if
  `getsockname()[0]` is not loopback); `serve(app, sock: socket.socket) -> None`
  (`uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="warning",
  lifespan="off")).run(sockets=[sock])`).

- [ ] **Step 1: Write failing tests**:
  - `test_bind_is_loopback_on_port_zero`: `bind_socket(0).getsockname()[0] ==
    "127.0.0.1"` and port > 0.
  - `test_taken_port_raises`: bind one socket, `bind_socket(its_port)` raises
    `PortUnavailable`.
  - `test_non_loopback_bind_is_fatal`: monkeypatch `LOOPBACK` to `"0.0.0.0"`;
    `bind_socket(0)` raises `RuntimeError`.
  - `test_real_uvicorn_round_trip`: start `serve` in a thread on a
    `bind_socket(0)`, poll until up, then with `http.client`: `GET /api/status`
    with `Host: 127.0.0.1:<port>` and the token → 200; with `Host:
    evil.example:<port>` → 403. Stop via `server.should_exit` (expose the
    `uvicorn.Server` through a small `make_server(app) -> uvicorn.Server` seam
    if needed).
  - In `tests/test_webapp_cli.py`, with `serve` monkeypatched to return
    immediately and `isolated_config`:
  - `test_clean_run_prints_url_and_cleans_up`: `main(["--no-browser"]) == 0`;
      stdout contains `http://127.0.0.1:` and `#token=`; afterwards `open.html`
      and `server.json` are gone.
  - `test_port_taken_refuses`: occupy a port; `main(["--no-browser",
      "--port", str(p)]) == 2`; stderr names the port.
  - `test_second_instance_refuses_with_port`: hold
      `pipeline_lock(runtime_dir()/"server.lock")` and write `server.json` with
      port 8123; `main([...]) == 2`; stderr contains `8123`. Without
      `server.json`: stderr contains `starting`.
  - `test_does_not_take_the_corpus_lock`: while `main` runs (inside the
      patched `serve`), `pipeline_lock()` (the default corpus lock) can be
      acquired.
  - `test_stale_runtime_files_are_overwritten` (Review Focus 5): pre-create
      `server.json` (port 1) and `open.html`, lock free; `main(["--no-browser"])
      == 0`.
  - `test_browser_opened_unless_no_browser`: a fake `open_browser` is called
      once without `--no-browser`, never with it.
  - `test_keyboard_interrupt_is_a_clean_stop`: patched `serve` raises
      `KeyboardInterrupt`; `main` returns 0 and the files are gone.

- [ ] **Step 2: Run, expect failure.**

- [ ]  **Step 3: Implement** `_server.py`, then extend `main`: project check →
      extra check → `runtime_dir()` → `with pipeline_lock(dir / "server.lock")`
      (on `AlreadyRunning`: port from `read_server_port`, refuse with it or with
      "another webapp is starting in this project; try again in a moment") →
      `bind_socket(args.port)` (on `PortUnavailable`: refuse naming the port) →
      token, `write_server_file`, `write_open_file`, print the launch URL once,
      `open_browser` unless `--no-browser` → `serve(build_app(...), sock)`
      inside `try/finally: remove_runtime_files(dir)`; `KeyboardInterrupt`
      returns 0. Split into helpers to stay within C1.

- [ ]  **Step 4: Run, expect pass**; whole `chitragupta/webapp/` at 100% line
      and branch.

- [ ]  **Step 5: Commit** `git commit -m "Serve the webapp on a loopback socket
      with one server per project (#1262)"`

### Task 7: The placeholder page

**Files:**

- Create: `assets/webapp/workbench/index.html`, `style.css`, `token.js`,
  `workbench.js`
- Create: `tests/webapp/workbench_token.test.js`,
  `tests/webapp/workbench_status.test.js`,
  `tests/webapp/workbench_smoke.test.js`
- Modify: `.github/workflows/ci.yml:614-615` and `scripts/check_local.sh:147`
  (coverage include also `assets/webapp/workbench/*.js`)
- Modify: `tests/webapp/code_standards.test.js` (new check over `workbench/`)

**Interfaces:**

- Produces (UMD, the same shape as `assets/webapp/absence.js`):
  - `token.js`: `takeToken(location, history, storage) -> string | null` (reads
    `#token=`, stores under key `"chitragupta.token"`, calls
    `history.replaceState(null, "", location.pathname)`, falls back to the
    stored value); `authHeaders(token) -> {Authorization: "Bearer " + token}`.
  - `workbench.js`: `renderStatus(doc, root, status) -> void` (only
    `createElement`/`textContent`); `renderNoToken(doc, root) -> void` (text:
    open the URL printed in the terminal); DOM wiring at the bottom runs only
    when `document` exists.

- [ ] **Step 1: Write failing node tests:**
  - token: fragment present → returned, stored, `replaceState` called with the
    path and no fragment; fragment absent and stored → stored value,
    `replaceState` not called; neither → `null`; `#token=` empty → `null`.
  - status: `renderStatus` with `project: '<img src=x onerror=alert(1)>'` →
    `root.textContent` contains that literal string and
    `root.querySelector("img")` is `null` (use the fake DOM already used in
    `tests/webapp/fixture.js`, or a minimal one in the test).
  - code standards: no file under `assets/webapp/workbench/` contains
    `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval(`, `
  on[a-z]+=` in HTML, or an inline `<script>` without `src`.
  - smoke (developer host only, the `browser_smoke.test.js` pattern, skips in
    GitHub Actions): start `python -m chitragupta webapp --no-browser --port 0`
    in a temp project, read the URL from stdout, open it; assert the address bar
    has no `#token`, `document.cookie === ""`, and the page shows the project
    name.

- [ ] **Step 2: Run, expect failure**
  Run: `node --test tests/webapp/workbench_*.test.js
  tests/webapp/code_standards.test.js`.

- [ ]  **Step 3: Implement** the four files. `index.html` loads `token.js`,
      `workbench.js` and `style.css` by `src`/`href` only.

- [ ]  **Step 4: Run, expect pass** with the widened coverage command from
      `scripts/check_local.sh` at 100% lines.

- [ ]  **Step 5: Commit** `git commit -m "Add the webapp placeholder page that
      proves the token flow (#1262)"`

### Task 8: Security docs, issues, and the full check

**Files:**

- Modify: `docs/SECURITY.md` (new `### Local web workbench` under "Controls in
  the implementation", and residual risks under "Residual risks and operating
  guidance"; update its table of contents)
- Modify: `docs/PACKAGING.md` only if it lists the extras (add `webapp`)

- [ ]  **Step 1: Write the `docs/SECURITY.md` section**: the seven controls from
      `plans/1262-webapp-foundation.md` in prose, then the residual risks: port
      forwarders (SSH `-L`, Docker `-p`, VS Code/Codespaces) extend reach;
      same-user processes can read the launch file; browser extensions; prompt
      injection limited by the allowlist (WA-1); on Windows the file modes are
      no-ops and Ctrl-C is the only stop.

- [ ] **Step 2: Run the full local check**
  Run: `bash scripts/check_local.sh`
  Expected: all steps pass, coverage 100%, `check_version_bump` sees `7.3.0`.

- [ ]  **Step 3: Commit** `git commit -m "Document the webapp's security
      controls and residual risks (#1262)"`

- [ ]  **Step 4: Reword the issues** through the REST API (`gh` is not logged in
      here; see the memory note on `GH_TOKEN`): #1260's table and text, #1261
      and #1262 use `chitragupta webapp`, `--port`/`--no-browser`, one server
      per project, FastAPI + uvicorn as the `webapp` extra. Show the owner the
      diff of each body before sending.

- [ ]  **Step 5: Rebase onto `origin/main`, push, and open the PR** only when
      the owner asks, using `.github/pull_request_template.md`.
