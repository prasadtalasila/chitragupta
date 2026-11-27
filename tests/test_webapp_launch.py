import json
import stat
import sys

import pytest

from chitragupta.webapp import _launch

POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="file modes are no-ops on Windows")


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_token_shape():
    first, second = _launch.new_token(), _launch.new_token()
    assert first != second
    assert len(first) >= 43


def test_launch_url():
    assert _launch.launch_url(8123, "abc") == "http://127.0.0.1:8123/#token=abc"


def test_runtime_dir_lives_under_content(isolated_config):
    directory = _launch.runtime_dir()
    assert directory == isolated_config.CONTENT_DIR / ".webapp"
    assert directory.is_dir()


@POSIX_ONLY
def test_runtime_dir_is_private(isolated_config):
    assert _mode(_launch.runtime_dir()) == 0o700


def test_open_file_redirects(isolated_config):
    url = _launch.launch_url(8123, "abc")
    page = _launch.write_open_file(_launch.runtime_dir(), url)
    text = page.read_text(encoding="utf-8")
    assert f'<meta http-equiv="refresh" content="0;url={url}">' in text
    assert f'<a href="{url}">' in text


@POSIX_ONLY
def test_open_file_is_private(isolated_config):
    page = _launch.write_open_file(_launch.runtime_dir(), "http://127.0.0.1:1/#token=x")
    assert _mode(page) == 0o600


def test_server_file_has_no_token(isolated_config):
    directory = _launch.runtime_dir()
    path = _launch.write_server_file(directory, 8123, 42)
    assert json.loads(path.read_text(encoding="utf-8")) == {"port": 8123, "pid": 42}
    assert _launch.read_server_port(directory) == 8123


@POSIX_ONLY
def test_server_file_is_private(isolated_config):
    assert _mode(_launch.write_server_file(_launch.runtime_dir(), 1, 1)) == 0o600


@pytest.mark.parametrize("content", [None, "not json", '{"pid": 1}', '{"port": "x"}', "[]"])
def test_read_server_port_tolerates_a_bad_file(isolated_config, content):
    directory = _launch.runtime_dir()
    if content is not None:
        (directory / _launch.SERVER_FILE).write_text(content, encoding="utf-8")
    assert _launch.read_server_port(directory) is None


def test_overwrites_a_leftover_file(isolated_config):
    directory = _launch.runtime_dir()
    _launch.write_server_file(directory, 1, 1)
    _launch.write_server_file(directory, 2, 2)
    assert _launch.read_server_port(directory) == 2


def test_browser_gets_a_file_uri_not_the_token(isolated_config):
    seen = []
    page = _launch.write_open_file(_launch.runtime_dir(), "http://127.0.0.1:1/#token=secret")
    assert _launch.open_browser(page, opener=lambda uri: seen.append(uri) or True) is True
    assert seen == [page.as_uri()]
    assert "secret" not in seen[0]


def test_remove_is_idempotent(isolated_config):
    directory = _launch.runtime_dir()
    _launch.write_open_file(directory, "http://127.0.0.1:1/#token=x")
    _launch.write_server_file(directory, 1, 1)
    _launch.remove_runtime_files(directory)
    _launch.remove_runtime_files(directory)
    assert not (directory / _launch.OPEN_FILE).exists()
    assert not (directory / _launch.SERVER_FILE).exists()


def test_a_failed_write_leaves_no_temp_file(isolated_config, monkeypatch):
    directory = _launch.runtime_dir()

    def refuse(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(_launch.os, "replace", refuse)
    with pytest.raises(OSError):
        _launch.write_server_file(directory, 1, 1)
    assert list(directory.iterdir()) == []
