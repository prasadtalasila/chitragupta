"""The FastAPI app behind `chitragupta webapp` (#1262).

Routes never authenticate: `GuardMiddleware` wraps the whole app and has
already checked Host, Origin, the token and the body size before any
route runs. Never add `Depends(...)` auth here -- that is the per-route
pattern (approach A) the design rejected, because one forgotten
dependency opens a route. `tests/test_webapp_app.py::test_route_census`
fails for any route outside `/api/` and for any `/api/` route a request
without the token can reach.

The generated docs (`/docs`, `/redoc`, `/openapi.json`) are off: they
would sit outside `/api/` and so outside the token.
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
    # Added on the app, not through `include_router`: recent FastAPI wraps an
    # included router in one opaque route, which the census could not see into.
    app.add_api_route("/api/status", status_payload, methods=["GET"])
    app.mount("/", StaticFiles(directory=static_dir, html=True))
    return GuardMiddleware(app, port=port, token=token)
