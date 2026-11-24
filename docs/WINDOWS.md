# 🪟 Windows: what works, what doesn't, and how to install

Status: **reference.**

**Written for** someone running this pipeline on Windows, either
natively or under WSL2. **Assumed:** nothing beyond
[README.md](../README.md)'s Quickstart. **Not covered here:** the
Linux and macOS install, which [CLI.md](CLI.md#-installing) has, and the
interpreter tiers it depends on, which
[CLI.md](CLI.md#-which-interpreter) states once for every platform.

CI runs a blocking `windows-latest` leg, so nothing below is
hypothetical.

## ⚡ The short answer

**Use WSL2 with Debian or Ubuntu if you can.** Everything works there,
GPU included, and the install is the ordinary Linux one. Native Windows
works too and CI proves it, but ~30 render and PDF tests self-skip
because three OS packages have no apt to install them from.

| | Native Windows | WSL2 (Debian/Ubuntu) |
| --- | --- | --- |
| Corpus sync, drafting, the citation gate | yes | yes |
| The review layer's eleven aids | yes, bar two: `verbatim` needs `pdftotext`, and `figure` runs but reports only four of its nine checks without `lualatex` | yes |
| `draft render` to PDF | needs Pandoc + a TeX distribution installed by hand | yes, via `os-deps` |
| `chitragupta enrich` | yes | yes |
| GPU acceleration | CPU only | yes; see [below](#-gpu-features-under-wsl2) |
| Install command | needs Git Bash | the documented Linux one |

## 🧩 The situation

Two things make Windows different. First, the installer is a bash
script: `scripts/install_full_pipeline.sh` is the single install path
for a checkout, Docker and CI, and it needs a POSIX shell. CI's Windows
leg runs it unmodified under Git Bash; a laptop may need to
[install one](#-installing-native-windows).

Second, the hook launcher name. Every hook starts as `python`, which a
virtual environment creates on every platform
([HOOKS.md](HOOKS.md#-the-launcher-contract) has why), so it resolves
natively on Windows. It matters because a hook whose launcher does not
resolve produces **nothing at all**: no error, no log line. The citation
gate is one of those hooks, so drafts would land ungated
([SOUL.md](../SOUL.md) has why that is the one failure this project
cannot tolerate). `chitragupta draft gate`, the session-start preflight,
the install script's `python-deps` step and CI's `launchers` job all
report it.

The Windows-specific half is the placeholder. An unbraced
`$CLAUDE_PROJECT_DIR` is expanded by the *shell*, and on a Windows host
without Git Bash that shell is PowerShell, where it expands to nothing.
Always write `${CLAUDE_PROJECT_DIR}`.

## 🔧 Installing: native Windows

1. **Install Git for Windows**, which provides Git Bash. Everything
   below runs in a Git Bash prompt, not PowerShell or `cmd`.

2. **Install Python 3.12, 3.13 or 3.14** (not 3.14.1) from python.org
   or the Microsoft Store, with "Add to PATH" enabled. Confirm it
   resolves:

   ```bash
   python --version
   ```

3. **Create the venv and install**, exactly as on Linux; the script
   handles `Scripts/` versus `bin/` itself:

   ```bash
   python -m venv .venv-full
   source .venv-full/Scripts/activate
   bash scripts/install_full_pipeline.sh python-deps
   ```

   `os-deps` is apt-only and will not run here; that is expected.

4. **Install the three OS binaries by hand**, if you want rendering and
   the `verbatim` aid ([below](#-why-there-is-no-powershell-installer)
   says why this is not scripted):

   ```bash
   winget install JohnMacFarlane.Pandoc
   winget install MiKTeX.MiKTeX
   winget install oschwartz10612.Poppler
   ```

   Poppler is what provides `pdftotext`; add its `bin` directory to
   `PATH` yourself, as its package does not.

   A book with an [index](book/BOOK-INDEX.md) also needs `upmendex`,
   MiKTeX's `miktex-upmendex-bin-x64` package, from the MiKTeX Console's
   Packages tab.

5. **Check what you have:**

   ```bash
   python -m chitragupta.doctor
   ```

Without step 4, `draft render` and the `verbatim` aid report a missing
binary, and the corresponding tests self-skip. The citation gate,
`corpus sync`, every genre skill and eight of the eleven review aids
need no OS package at all.

**The `figure` aid is the one to watch**, because it does not refuse:
five of its nine checks need `lualatex`, including node overlap and
content protrusion, so without TeX it runs the other four and names
what it skipped. A green `figure` report on a host without TeX is not a
clean report. [CLI.md](CLI.md#-chitragupta-review-figure) has the
split.

## 🐧 Installing: WSL2

Install a Debian or Ubuntu distribution, then follow
[CLI.md](CLI.md#-installing) unchanged: inside WSL2 this is a Linux
host, `os-deps` works, and `python-is-python3` (which `os-deps`
installs) puts the hook launcher's name on `PATH`.

**Keep `papers/` and `content/` on the WSL2 filesystem, not under
`/mnt/c/`.** The Windows drives are reached over a 9p mount whose
per-file overhead makes a corpus sync bound by I/O. Clone into your WSL2
home directory.

## 🎮 GPU features under WSL2

The whole `enrich` layer (Docling's PDF parsing, sentence-transformers
embeddings, BERTopic) works on the GPU: CUDA-on-WSL2 is NVIDIA's
supported configuration. The install script's `ensure_gpu_torch` needs
`nvidia-smi` on `PATH` (WSL2 provides it at
`/usr/lib/wsl/lib/nvidia-smi`) and a parseable `CUDA Version: X.Y` in its
header, so it runs unmodified. `nvidia-smi` reports the Windows driver's
CUDA ceiling, which is the right number for choosing a wheel; its
reduced WSL2 feature set does not matter, as only that line is read.

**Install the NVIDIA driver on Windows only, never inside WSL.** A Linux
driver installed in the distribution shadows the passthrough and breaks
CUDA.

Native Windows is CPU-only for this pipeline. The `enrich` layer still
runs, more slowly; [PERFORMANCE.md](PERFORMANCE.md) has the numbers.

## 🚫 Why there is no PowerShell installer

`DEVELOPER-AGENTS.md` forbids a second install path: there is one place
a dependency fact can be written, so a fix lands once and every target
picks it up. A `.ps1` would duplicate a path CI's Windows leg already
runs, and would drift. The real gap is three OS packages with no apt
behind them, and scripting `winget` would not close it: the useful part
is knowing which binaries matter and what self-skips without them, which
is what this page and `chitragupta doctor` are for.
