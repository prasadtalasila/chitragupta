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
MMPROJ = "mmproj-F16.gguf"
MMPROJ_BYTES = 899283680
MMPROJ_SHA256 = "8971ee4f331ff0a4c609374f32984b3d4e6dc086c0aa35f1d637fad1829e887f"

pytestmark = pytest.mark.skipif(
    BASH is None or sys.platform == "win32", reason="bash scripts for a Linux GPU host"
)


def sparse(path, size, sha256):
    with path.open("wb") as f:
        f.truncate(size)
    stat = path.stat()
    path.with_name(path.name + ".verified").write_text(
        f"{stat.st_size} {int(stat.st_mtime)} {sha256}\n", encoding="utf-8"
    )


def everything(
    tmp_path,
    codex="codex-cli 0.159.3",
    cuda=True,
    model_bytes=MODEL_BYTES,
    mmproj_bytes=MMPROJ_BYTES,
):
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
    sparse(models / MODEL, model_bytes, MODEL_SHA256)
    if mmproj_bytes is not None:
        sparse(models / MMPROJ, mmproj_bytes, MMPROJ_SHA256)
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
    assert f"mmproj: {tools}/models/{MMPROJ} (sha256 verified)" in result.stdout
    assert result.stdout.splitlines()[-1] == f"PATH={tools}/npm/bin:$PATH"


def test_nothing_present_names_every_tool_and_installs_nothing(tmp_path):
    (tmp_path / "bin").mkdir()
    tools = tmp_path / "tools"
    tools.mkdir()
    result = check(tmp_path / "bin", tools)
    assert result.returncode == 1
    names = ("codex", "opencode", "llama-server", "model", "mmproj", "claude", "pdftotext")
    for name in (*names, "lualatex"):
        assert f"{name}: missing" in result.stdout, name
    assert list(tools.iterdir()) == []


def test_another_codex_version_is_not_enough(tmp_path):
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
    bin_dir, tools = everything(tmp_path, model_bytes=1024)
    result = check(bin_dir, tools)
    assert result.returncode == 1
    assert f"model: missing, 1024 bytes, not {MODEL_BYTES}" in result.stdout


def test_a_missing_vision_projector_fails_the_check(tmp_path):
    bin_dir, tools = everything(tmp_path, mmproj_bytes=None)
    result = check(bin_dir, tools)
    assert result.returncode == 1
    assert f"mmproj: missing, {tools}/models/{MMPROJ}" in result.stdout


def test_a_vision_projector_of_the_wrong_size_fails(tmp_path):
    bin_dir, tools = everything(tmp_path, mmproj_bytes=2048)
    result = check(bin_dir, tools)
    assert result.returncode == 1
    assert f"mmproj: missing, 2048 bytes, not {MMPROJ_BYTES}" in result.stdout


def test_a_claude_that_is_not_logged_in_does_not_count(tmp_path):
    bin_dir, tools = everything(tmp_path)
    fake(bin_dir, "claude", "echo '{\"loggedIn\": false}'")
    result = check(bin_dir, tools)
    assert result.returncode == 1
    assert "claude: missing, or not logged in" in result.stdout


FAKE_SERVER = """#!{python}
import http.server, sys
port = int(sys.argv[sys.argv.index("--port") + 1])
open(sys.argv[0] + ".args", "w").write(" ".join(sys.argv[1:]))
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/v1/models" else 404)
        self.end_headers()
    def log_message(self, *args):
        pass
http.server.HTTPServer(("127.0.0.1", port), H).serve_forever()
"""


def free_gpu_index():
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
    mmproj = tmp_path / "mmproj.gguf"
    mmproj.write_bytes(b"")
    first = free_gpu_index()
    env = {
        **os.environ,
        "BENCH_TOOLS": str(tools),
        "LLAMA_SERVER": str(server),
        "MODEL_FILE": str(model),
        "MMPROJ_FILE": str(mmproj),
        "MODEL_ALIAS": "another-model",
        "LLAMA_EXTRA": "--spec-type draft-mtp --spec-draft-n-max 2",
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
        args = (tmp_path / "llama-server.args").read_text(encoding="utf-8").split()
        assert args[args.index("--mmproj") + 1] == str(mmproj), args
        assert args[args.index("--alias") + 1] == "another-model", args
        assert args[-4:] == ["--spec-type", "draft-mtp", "--spec-draft-n-max", "2"], args
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
    server, model = tmp_path / "llama-server", tmp_path / "model.gguf"
    fake(tmp_path, "llama-server", "exit 0")
    model.write_bytes(b"")
    blind = subprocess.run(
        [BASH, str(SERVE), "1"],
        env={**env, "LLAMA_SERVER": str(server), "MODEL_FILE": str(model), "WAIT": "4"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert blind.returncode == 1 and "no vision projector" in blind.stderr
    quiet = subprocess.run(
        [BASH, str(SERVE), "--stop"], env=env, capture_output=True, text=True, check=False
    )
    assert quiet.returncode == 0 and "no servers recorded" in quiet.stdout
