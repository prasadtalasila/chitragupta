"""The checks every request passes before any route sees it (#1262).

Pure functions over a method, a path and the request headers, so they
test without FastAPI. `run_checks` fixes the order: Host first (it closes
DNS rebinding and runs for static files too), then the method, then --
for `/api/` only -- Origin, the bearer token and the body size.

Headers arrive as `{lower-case name: [values]}`, every value decoded as
latin-1 the way the bytes came off the wire. A security header sent more
than once is refused outright: picking "the first one" is how two parsers
in a chain come to disagree about which value they checked.
"""

import hmac
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

MAX_BODY = 1_048_576
ALLOWED_METHODS = frozenset({"GET", "POST"})

Headers = Mapping[str, list[str]]


@dataclass(frozen=True)
class Refusal:
    status: int
    reason: str


def header_map(raw: Iterable[tuple[bytes, bytes]]) -> dict[str, list[str]]:
    headers: dict[str, list[str]] = {}
    for name, value in raw:
        headers.setdefault(name.decode("latin-1").lower(), []).append(value.decode("latin-1"))
    return headers


def is_api(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def _single(headers: Headers, name: str) -> "str | None | Refusal":
    """The one value of `name`, `None` when absent, a 400 when repeated."""
    values = headers.get(name, [])
    if len(values) > 1:
        return Refusal(400, f"{name} header sent more than once")
    return values[0] if values else None


def check_host(headers: Headers, port: int) -> Refusal | None:
    host = _single(headers, "host")
    if isinstance(host, Refusal):
        return host
    if host not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
        return Refusal(403, "Host is not this server's loopback address")
    return None


def check_method(method: str) -> Refusal | None:
    if method not in ALLOWED_METHODS:
        return Refusal(405, f"method {method} not allowed")
    return None


def check_origin(method: str, headers: Headers, port: int) -> Refusal | None:
    origin = _single(headers, "origin")
    if isinstance(origin, Refusal):
        return origin
    if origin is None:
        return Refusal(403, "POST without Origin") if method == "POST" else None
    if origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
        return Refusal(403, "Origin is not this server")
    return None


def check_token(headers: Headers, token: str) -> Refusal | None:
    """Compared as bytes: `hmac.compare_digest` raises on non-ASCII `str`."""
    value = _single(headers, "authorization")
    if isinstance(value, Refusal):
        return value
    expected = f"Bearer {token}".encode("latin-1")
    if value is None or not hmac.compare_digest(value.encode("latin-1"), expected):
        return Refusal(401, "missing or wrong token")
    return None


def check_body_size(method: str, headers: Headers) -> Refusal | None:
    if method != "POST":
        return None
    length = _single(headers, "content-length")
    if isinstance(length, Refusal):
        return length
    if length is None:
        return Refusal(411, "POST without Content-Length")
    if not (length.isascii() and length.isdigit()):
        return Refusal(400, "Content-Length is not a number")
    if int(length) > MAX_BODY:
        return Refusal(413, "body larger than the limit")
    return None


def run_checks(method: str, path: str, headers: Headers, port: int, token: str) -> Refusal | None:
    refusal = check_host(headers, port) or check_method(method)
    if refusal or not is_api(path):
        return refusal
    return (
        check_origin(method, headers, port)
        or check_token(headers, token)
        or check_body_size(method, headers)
    )
