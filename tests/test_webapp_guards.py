import pytest

from chitragupta.webapp import _guards as g

PORT = 8123
TOKEN = "t" * 43
GOOD_HOST = {"host": ["127.0.0.1:8123"]}


def test_header_map_lowercases_decodes_and_keeps_duplicates():
    raw = [(b"Host", b"127.0.0.1:8123"), (b"X-A", b"\xe9"), (b"x-a", b"2")]
    assert g.header_map(raw) == {"host": ["127.0.0.1:8123"], "x-a": ["\xe9", "2"]}


@pytest.mark.parametrize(
    "path, expected",
    [("/api", True), ("/api/", True), ("/api/status", True), ("/apix", False), ("/", False),
     ("/index.html", False), ("//api/status", False)],
)
def test_is_api(path, expected):
    assert g.is_api(path) is expected


@pytest.mark.parametrize("values", [["127.0.0.1:8123"], ["localhost:8123"]])
def test_host_allowed(values):
    assert g.check_host({"host": values}, PORT) is None


@pytest.mark.parametrize(
    "values", [["evil.example:8123"], ["127.0.0.1:9999"], ["127.0.0.1"], [], ["LOCALHOST:8123"]]
)
def test_host_refused(values):
    assert g.check_host({"host": values}, PORT).status == 403


def test_duplicate_host_is_a_bad_request():
    assert g.check_host({"host": ["127.0.0.1:8123"] * 2}, PORT).status == 400


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_method_allowed(method):
    assert g.check_method(method) is None


@pytest.mark.parametrize("method", ["PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
def test_method_refused(method):
    assert g.check_method(method).status == 405


@pytest.mark.parametrize(
    "method, origin",
    [("GET", None), ("GET", ["http://localhost:8123"]), ("POST", ["http://127.0.0.1:8123"])],
)
def test_origin_allowed(method, origin):
    headers = {} if origin is None else {"origin": origin}
    assert g.check_origin(method, headers, PORT) is None


@pytest.mark.parametrize(
    "method, origin",
    [("POST", None), ("GET", ["http://evil.example"]), ("POST", ["null"]),
     ("GET", ["http://127.0.0.1:9999"]), ("GET", ["https://127.0.0.1:8123"])],
)
def test_origin_refused(method, origin):
    headers = {} if origin is None else {"origin": origin}
    assert g.check_origin(method, headers, PORT).status == 403


def test_duplicate_origin_is_a_bad_request():
    headers = {"origin": ["http://127.0.0.1:8123"] * 2}
    assert g.check_origin("GET", headers, PORT).status == 400


def test_token_allowed():
    assert g.check_token({"authorization": [f"Bearer {TOKEN}"]}, TOKEN) is None


@pytest.mark.parametrize(
    "values",
    [None, ["Bearer"], ["Bearer wrong"], [f"bearer {TOKEN}"], [f"Basic {TOKEN}"],
     [f"Bearer {TOKEN} "], ["Bearer \xe9"], [f"Bearer {TOKEN}\xe9"]],
)
def test_token_refused(values):
    headers = {} if values is None else {"authorization": values}
    assert g.check_token(headers, TOKEN).status == 401


def test_duplicate_authorization_is_a_bad_request():
    headers = {"authorization": [f"Bearer {TOKEN}"] * 2}
    assert g.check_token(headers, TOKEN).status == 400


@pytest.mark.parametrize(
    "method, length, expected",
    [("GET", None, None), ("POST", ["10"], None), ("POST", [str(g.MAX_BODY)], None),
     ("POST", [str(g.MAX_BODY + 1)], 413), ("POST", None, 411), ("POST", ["abc"], 400),
     ("POST", ["-1"], 400), ("POST", ["1", "1"], 400), ("POST", ["\xb2"], 400)],
)
def test_body_size(method, length, expected):
    headers = {} if length is None else {"content-length": length}
    refusal = g.check_body_size(method, headers)
    assert (refusal and refusal.status) == expected


def test_static_get_needs_neither_token_nor_origin():
    assert g.run_checks("GET", "/index.html", GOOD_HOST, PORT, TOKEN) is None


def test_api_without_token_is_unauthorised():
    assert g.run_checks("GET", "/api/status", GOOD_HOST, PORT, TOKEN).status == 401


def test_host_runs_before_everything():
    headers = {"host": ["evil.example:8123"]}
    assert g.run_checks("PUT", "/index.html", headers, PORT, TOKEN).status == 403


def test_method_runs_before_the_token():
    assert g.run_checks("PUT", "/api/status", GOOD_HOST, PORT, TOKEN).status == 405


def test_origin_runs_before_the_token():
    headers = {**GOOD_HOST, "origin": ["http://evil.example"]}
    assert g.run_checks("GET", "/api/status", headers, PORT, TOKEN).status == 403


def test_a_complete_api_post_passes():
    headers = {
        **GOOD_HOST,
        "origin": ["http://127.0.0.1:8123"],
        "authorization": [f"Bearer {TOKEN}"],
        "content-length": ["2"],
    }
    assert g.run_checks("POST", "/api/status", headers, PORT, TOKEN) is None


def test_an_oversized_api_post_is_refused_after_auth():
    headers = {
        **GOOD_HOST,
        "origin": ["http://127.0.0.1:8123"],
        "authorization": [f"Bearer {TOKEN}"],
        "content-length": [str(g.MAX_BODY + 1)],
    }
    assert g.run_checks("POST", "/api/x", headers, PORT, TOKEN).status == 413
