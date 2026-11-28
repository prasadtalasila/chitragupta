import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse, StreamingResponse
from starlette.routing import Route
from starlette.websockets import WebSocketDisconnect

from chitragupta.webapp._middleware import CSP, GuardMiddleware

PORT = 8123
TOKEN = "t" * 43
AUTH = {"Authorization": f"Bearer {TOKEN}"}
BASE = f"http://127.0.0.1:{PORT}"


def _chunks():
    yield b"one,"
    yield b"two,"
    yield b"three"


inner_calls = []


async def _record(scope, receive, send):
    inner_calls.append(scope["type"])
    await _inner(scope, receive, send)


_inner = Starlette(
    routes=[
        Route("/api/ok", lambda r: JSONResponse({"ok": True})),
        Route("/api/stream", lambda r: StreamingResponse(_chunks())),
        Route("/page", lambda r: PlainTextResponse("page")),
        Route(
            "/loose",
            lambda r: PlainTextResponse("x", headers={"Content-Security-Policy": "default-src *"}),
        ),
    ]
)


@pytest.fixture
def client():
    inner_calls.clear()
    return TestClient(GuardMiddleware(_record, port=PORT, token=TOKEN), base_url=BASE)


def _assert_security_headers(response):
    assert response.headers["content-security-policy"] == CSP
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_refusal_has_security_headers_and_empty_body(client):
    response = client.get("/page", headers={"Host": f"evil.example:{PORT}"})
    assert response.status_code == 403
    assert response.content == b""
    _assert_security_headers(response)
    assert inner_calls == []


def test_allowed_api_response_gets_no_store(client):
    response = client.get("/api/ok", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers["cache-control"] == "no-store"
    _assert_security_headers(response)


def test_static_response_gets_headers_but_not_no_store(client):
    response = client.get("/page")
    assert response.status_code == 200
    _assert_security_headers(response)
    assert "no-store" not in response.headers.get("cache-control", "")


def test_api_without_token_is_refused(client):
    assert client.get("/api/ok").status_code == 401
    assert inner_calls == []


def test_streamed_body_passes_untouched(client):
    response = client.get("/api/stream", headers=AUTH)
    assert response.content == b"one,two,three"
    _assert_security_headers(response)


@pytest.mark.parametrize("path, headers", [("/page", {}), ("/api/ok", AUTH), ("/api/ok", {})])
def test_no_cors_headers(client, path, headers):
    response = client.get(path, headers={"Origin": "http://evil.example", **headers})
    assert not [name for name in response.headers if name.lower().startswith("access-control-")]


def test_websocket_refused_before_the_app(client):
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/api/ws", headers=AUTH):
            pass
    assert excinfo.value.code == 1008
    assert inner_calls == []


def test_lifespan_passes_through():
    with TestClient(GuardMiddleware(_record, port=PORT, token=TOKEN), base_url=BASE):
        pass
    assert "lifespan" in inner_calls


def test_a_route_cannot_weaken_the_policy(client):
    response = client.get("/loose")
    assert response.headers.get_list("content-security-policy") == [CSP]
