"""The loopback-only browser workbench behind `chitragupta webapp` (#1262).

A front end on the same core the CLI uses. FastAPI and uvicorn come from
the optional `webapp` extra and are imported only inside this package,
never by the CLI, the hooks or the gate chain. plans/1262-webapp-foundation.md
records the design and every control.
"""
