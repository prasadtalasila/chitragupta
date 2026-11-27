import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import Mount

from chitragupta import config
from chitragupta.webapp._app import WORKBENCH_DIR, build_app, status_payload

PORT = 8123
TOKEN = "t" * 43
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def app():
    return build_app(port=PORT, token=TOKEN)


@pytest.fixture
def client(app):
    return TestClient(app, base_url=f"http://127.0.0.1:{PORT}")


def test_status_with_token(client):
    response = client.get("/api/status", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == status_payload()
    assert set(response.json()) == {"project", "version"}
    assert response.json()["project"] == config.PROJECT_ROOT.name


def test_status_without_token(client):
    assert client.get("/api/status").status_code == 401


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
@pytest.mark.parametrize("headers", [{}, AUTH])
def test_docs_endpoints_absent(client, path, headers):
    assert client.get(path, headers=headers).status_code == 404


def test_debug_off(app):
    assert app.app.debug is False


def test_the_workbench_directory_ships():
    assert (WORKBENCH_DIR / "index.html").is_file()


def test_index_served_without_token(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


@pytest.mark.parametrize(
    "path", ["/../config.toml", "/%2e%2e/config.toml", "/..%2fconfig.toml", "/%2e%2e%2fconfig.toml"]
)
def test_static_traversal_refused(client, path):
    response = client.get(path)
    assert response.status_code != 200 or "[" not in response.text


@pytest.mark.parametrize(
    "path", ["/api", "//api/status", "/API/status", "/x/../api/status", "/%2e%2e/api/status",
             "/api/status/", "/api%2fstatus"]
)
def test_api_path_spellings_never_leak_without_the_token(client, path):
    response = client.get(path)
    assert not (response.status_code == 200 and "project" in response.text)


def test_route_census(app, client):
    api_routes = [r for r in app.app.routes if isinstance(r, APIRoute)]
    others = [r for r in app.app.routes if not isinstance(r, APIRoute)]
    assert api_routes
    for route in api_routes:
        assert route.path.startswith("/api/")
        for method in route.methods:
            origin = {"Origin": f"http://127.0.0.1:{PORT}"}
            assert client.request(method, route.path, headers=origin).status_code == 401
    assert [(type(r), r.path) for r in others] == [(Mount, "")]
