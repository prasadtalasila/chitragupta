"""Plain ASGI around the whole app, so no route can skip a check.

Not BaseHTTPMiddleware, which mishandles streamed responses.
"""

import logging
from collections.abc import Awaitable, Callable

from chitragupta.webapp._guards import Refusal, header_map, is_api, run_checks

log = logging.getLogger(__name__)

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'none'; "
    "frame-ancestors 'none'"
)
SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"content-security-policy", CSP.encode("latin-1")),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
)
NO_STORE = (b"cache-control", b"no-store")
POLICY_VIOLATION = 1008


def _headers_for(path: str, existing: list) -> list:
    # Ours replace any the app set, so a route cannot weaken them.
    ours = list(SECURITY_HEADERS) + ([NO_STORE] if is_api(path) else [])
    names = {name for name, _ in ours}
    return [h for h in existing if h[0].lower() not in names] + ours


class GuardMiddleware:
    def __init__(self, app, *, port: int, token: str) -> None:
        self.app = app
        self.port = port
        self.token = token

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": POLICY_VIOLATION})
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = header_map(scope["headers"])
        refusal = run_checks(scope["method"], scope["path"], headers, self.port, self.token)
        if refusal:
            await self._refuse(scope["path"], refusal, send)
            return
        await self.app(scope, receive, self._wrap(scope["path"], send))

    @staticmethod
    async def _refuse(path: str, refusal: Refusal, send) -> None:
        log.debug("refused %s: %s %s", path, refusal.status, refusal.reason)
        headers = _headers_for(path, [(b"content-length", b"0")])
        await send({"type": "http.response.start", "status": refusal.status, "headers": headers})
        await send({"type": "http.response.body", "body": b""})

    @staticmethod
    def _wrap(path: str, send) -> Callable[[dict], Awaitable[None]]:
        async def guarded_send(message) -> None:
            if message["type"] == "http.response.start":
                message = {**message, "headers": _headers_for(path, list(message["headers"]))}
            await send(message)

        return guarded_send
