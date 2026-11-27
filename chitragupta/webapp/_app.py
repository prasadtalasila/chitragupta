"""Routes never authenticate: GuardMiddleware wraps the whole app.

Never add `Depends(...)` auth, and keep every route under /api/
(tests/test_webapp_app.py::test_route_census). The generated docs are
off because they would sit outside /api/ and so outside the token.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from chitragupta import config
from chitragupta.webapp._middleware import GuardMiddleware

WORKBENCH_DIR = config.shipped("assets", "webapp", "workbench")


def status_payload() -> dict[str, str]:
    from chitragupta.__main__ import _version

    return {"project": config.PROJECT_ROOT.name, "version": _version()}


def build_app(*, port: int, token: str, static_dir=WORKBENCH_DIR) -> GuardMiddleware:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, debug=False)
    # Not include_router: FastAPI wraps it in one route the census cannot inspect.
    app.add_api_route("/api/status", status_payload, methods=["GET"])
    app.mount("/", StaticFiles(directory=static_dir, html=True))
    return GuardMiddleware(app, port=port, token=token)
