"""The skill-bench skill's `install_tools.sh --check` and `serve_models.sh`.

The check is what a session runs first to learn whether it can bench at
all, and what decides what the install half fetches. It runs here for
real, in bash, against a PATH of fakes and a BENCH_TOOLS folder holding a
fake build and a sparse model file of the pinned size, so nothing hashes
22 GB: the model's verified stamp is what the check trusts while the
file's size and mtime still match it. The install half needs apt, sudo,
a GPU and the network, so it was run for real on the A40 host instead
(PR description). `serve_models.sh` runs against a fake `llama-server`
that answers `/v1/models` on the port it is given.
"""

import os
import shutil
import socket
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT, fake

BASH = shutil.which("bash")
SCRIPTS = REPO_ROOT / ".claude" / "skills" / "skill-bench" / "scripts"
CHECK = SCRIPTS / "install_tools.sh"
SERVE = SCRIPTS / "serve_models.sh"
MODEL = "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
MODEL_BYTES = 22134528992
MODEL_SHA256 = "ac0e2c1189e055faa36eff361580e79c5bd6f8e76bffb4ce547f167d53e31a61"

pytestmark = pytest.mark.skipif(
    BASH is None or sys.platform == "win32", reason="bash scripts for a Linux GPU host"
)


def everything(tmp_path, codex="codex-cli 0.159.3", cuda=True, model_bytes=MODEL_BYTES):
    """A PATH and BENCH_TOOLS holding every tool, as their real versions
    answer, and a model whose stamp matches it."""
    bin_dir, tools = tmp_path / "bin", tmp_path / "tools"
    build = tools / "llama.cpp-b11321" / "build" / "bin"
    models = tools / "models"
    for d in (bin_dir, build, models):
        d.mkdir(parents=True)
    fake(bin_dir, "codex", f'echo "{codex}"')
    fake(bin_dir, "opencode", 'echo "1.18.34"')
    fake(bin_dir, "claude", "echo '{\"loggedIn\": true}'")
    for name in ("pdftotext", "lualatex", "stat", "cut", "sha256sum"):
        real = shutil.which(name)
        if real is None:
            fake(bin_dir, name, "exit 0")
        else:
            (bin_dir / name).symlink_to(real)
    fake(build, "llama-server", "exit 0")
    if cuda:
        (build / "libggml-cuda.so").write_bytes(b"")
    model = models / MODEL
    with model.open("wb") as f:
        f.truncate(model_bytes)
    stat = model.stat()
    (models / f"{MODEL}.verified").write_text(
        f"{stat.st_size} {int(stat.st_mtime)} {MODEL_SHA256}\n", encoding="utf-8"
    )
    return bin_dir, tools


def check(path, tools, **env):
    return subprocess.run(
        [BASH, str(CHECK), "--check"],
        env={"PATH": str(path), "HOME": str(tools.parent), "BENCH_TOOLS": str(tools), **env},
        capture_output=True,
        text=True,
        check=False,
    )


def test_everything_present_passes_and_prints_the_path(tmp_path):
    bin_dir, tools = everything(tmp_path)
    result = check(bin_dir, tools)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "model: " in result.stdout and "(sha256 verified)" in result.stdout
    assert result.stdout.splitlines()[-1] == f"PATH={tools}/npm/bin:$PATH"


def test_nothing_present_names_every_tool_and_installs_nothing(tmp_path):
    (tmp_path / "bin").mkdir()
    tools = tmp_path / "tools"
    tools.mkdir()
    result = check(tmp_path / "bin", tools)
    assert result.returncode == 1
    for name in ("codex", "opencode", "llama-server", "model", "claude", "pdftotext", "lualatex"):
        assert f"{name}: missing" in result.stdout, name
    assert list(tools.iterdir()) == []


def test_another_codex_version_is_not_enough(tmp_path):
    """The versions are pinned so every baseline in the series stays
    comparable with the one before it."""
    bin_dir, tools = everything(tmp_path, codex="codex-cli 0.160.0")
    result = check(bin_dir, tools)
    assert result.returncode == 1
    assert "codex: missing, or not 0.159.3 (codex-cli 0.160.0)" in result.stdout


def test_a_cpu_build_of_llama_server_does_not_count(tmp_path):
    bin_dir, tools = everything(tmp_path, cuda=False)
    result = check(bin_dir, tools)
    assert result.returncode == 1
    assert "llama-server: missing, built without CUDA" in result.stdout


def test_a_model_of_the_wrong_size_fails_without_hashing(tmp_path):
    """A partial download is caught by its size, before a minute of
    hashing; its stale stamp is not trusted."""
    bin_dir, tools = everything(tmp_path, model_bytes=1024)
    result = check(bin_dir, tools)
    assert result.returncode == 1
    assert f"model: missing, 1024 bytes, not {MODEL_BYTES}" in result.stdout


def test_a_claude_that_is_not_logged_in_does_not_count(tmp_path):
    bin_dir, tools = everything(tmp_path)
    fake(bin_dir, "claude", "echo '{\"loggedIn\": false}'")
    result = check(bin_dir, tools)
    assert result.returncode == 1
    assert "claude: missing, or not logged in" in result.stdout


FAKE_SERVER = """#!{python}
import http.server, sys
port = int(sys.argv[sys.argv.index("--port") + 1])
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/v1/models" else 404)
        self.end_headers()
    def log_message(self, *args):
        pass
http.server.HTTPServer(("127.0.0.1", port), H).serve_forever()
"""


def free_gpu_index():
    """A GPU index whose port 18080+i nothing on this host listens on."""
    for index in range(40, 400):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", 18080 + index)) != 0:
                return index
    pytest.skip("no free port in 18120-18479")


@pytest.mark.skipif(shutil.which("curl") is None, reason="serve_models.sh waits with curl")
def test_serve_models_starts_one_server_a_gpu_and_stops_them(tmp_path):
    tools = tmp_path / "tools"
    server = tmp_path / "llama-server"
    server.write_text(FAKE_SERVER.format(python=sys.executable), encoding="utf-8")
    server.chmod(0o755)
    model = tmp_path / "model.gguf"
    model.write_bytes(b"")
    first = free_gpu_index()
    env = {
        **os.environ,
        "BENCH_TOOLS": str(tools),
        "LLAMA_SERVER": str(server),
        "MODEL_FILE": str(model),
        "WAIT": "30",
    }
    run = lambda *args: subprocess.run(  # noqa: E731
        [BASH, str(SERVE), *args], env=env, capture_output=True, text=True, check=False
    )
    try:
        started = run("1", str(first))
        assert started.returncode == 0, started.stdout + started.stderr
        port = 18080 + first
        assert started.stdout.splitlines()[-1] == f"--base-url http://127.0.0.1:{port}/v1"
        assert (tools / "run" / "servers.pid").read_text(encoding="utf-8").strip()
    finally:
        stopped = run("--stop")
    assert stopped.returncode == 0 and "stopped" in stopped.stdout
    assert not (tools / "run" / "servers.pid").exists()


def test_serve_models_refuses_a_bad_count_and_a_missing_build(tmp_path):
    env = {**os.environ, "BENCH_TOOLS": str(tmp_path)}
    usage = subprocess.run(
        [BASH, str(SERVE), "zero"], env=env, capture_output=True, text=True, check=False
    )
    assert usage.returncode == 2 and "usage:" in usage.stderr
    nothing = subprocess.run(
        [BASH, str(SERVE), "1"], env=env, capture_output=True, text=True, check=False
    )
    assert nothing.returncode == 1 and "run install_tools.sh" in nothing.stderr
    quiet = subprocess.run(
        [BASH, str(SERVE), "--stop"], env=env, capture_output=True, text=True, check=False
    )
    assert quiet.returncode == 0 and "no servers recorded" in quiet.stdout
