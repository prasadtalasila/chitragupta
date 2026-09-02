# 🪟 Windows: what works, what doesn't, and how to install

Status: **reference.** Written 2026-09-02.

**Written for** someone running this pipeline on Windows, either
natively or under WSL2. **Assumed:** nothing beyond
[README.md](../README.md)'s Quickstart. **Not covered here:** the
Linux and macOS install, which [CLI.md](CLI.md#-installing) has, and the
interpreter tiers it depends on, which
[CLI.md](CLI.md#-which-interpreter) states once for every platform.

CI runs a blocking `windows-latest` leg, so nothing below is
hypothetical: it is what that leg does, plus the two things a laptop has
that a runner does not.

## 🧭 Table of contents

- [The short answer](#-the-short-answer)
- [The situation](#-the-situation)
- [Installing: native Windows](#-installing-native-windows)
- [Installing: WSL2](#-installing-wsl2)
- [GPU features under WSL2](#-gpu-features-under-wsl2)
- [Why there is no PowerShell installer](#-why-there-is-no-powershell-installer)

## ⚡ The short answer

**Use WSL2 with Debian or Ubuntu if you can.** Everything works there,
GPU included, and the install is the ordinary Linux one. Native Windows
works too and CI proves it, but ~30 render and PDF tests self-skip
because three OS packages have no apt to install them from.

| | Native Windows | WSL2 (Debian/Ubuntu) |
| --- | --- | --- |
| Corpus sync, drafting, the citation gate | yes | yes |
| The review layer's ten aids | yes, bar two: `verbatim` needs `pdftotext`, and `figure` runs but reports only three of its eight checks without `pdflatex` | yes |
| `draft render` to PDF | needs Pandoc + a TeX distribution installed by hand | yes, via `os-deps` |
| `chitragupta enrich` | yes | yes |
| GPU acceleration | CPU only | yes -- see [below](#-gpu-features-under-wsl2) |
| Install command | needs Git Bash | the documented Linux one |

## 🧩 The situation

Two things make Windows different, and only the second is really about
Windows.

**The installer is a bash script.** `scripts/install_full_pipeline.sh`
is the single install path for a checkout, Docker and CI
(`DEVELOPER-AGENTS.md` states why there is only one), and it needs a
POSIX shell. CI's Windows leg has one -- the runner image ships Git
Bash -- and runs the same script the Linux leg does, unmodified. A
laptop may not, so [below](#-installing-native-windows) starts by
installing one.

**The hook launcher name.** `.claude/settings.json` starts every hook
this repository registers as `python`, and
[HOOKS.md](HOOKS.md#-the-launcher-contract) records why that name rather
than `python3`: a virtual environment creates `python` on every
platform and `python3` only on POSIX, so `python3` is the name that
would go missing here. Windows is the *winning* host for that choice,
not the losing one -- the name resolves natively.

What makes it worth stating anyway is the failure mode. A hook whose
launcher does not resolve produces **nothing at all**: no error, no log
line. The citation gate is one of those hooks, so the settings file
still lists it, the suite still passes, and drafts land ungated --
[SOUL.md](../SOUL.md) has why that is the one failure this project
cannot tolerate. Two things now report it rather than one: `chitragupta
draft gate` and the session-start preflight both call
`chitragupta/hook_launchers.py`, the install script prints what it finds
at the end of `python-deps`, and CI's `launchers` job checks it on both
platforms with nothing installed.

The Windows-specific half of that check is the placeholder. An unbraced
`$CLAUDE_PROJECT_DIR` is expanded by the *shell*, not substituted by the
harness -- and on a Windows host without Git Bash that shell is
PowerShell, where the syntax names an undefined variable and expands to
nothing. Always write `${CLAUDE_PROJECT_DIR}`.

## 🔧 Installing: native Windows

1. **Install Git for Windows**, which provides Git Bash. Everything
   below runs in a Git Bash prompt, not PowerShell or `cmd`.

2. **Install Python 3.12 or newer** from python.org or the Microsoft
   Store, with "Add to PATH" enabled. Confirm both names resolve:

   ```bash
   python --version
   ```

3. **Create the venv and install**, exactly as on Linux -- the script
   handles `Scripts/` versus `bin/` itself:

   ```bash
   python -m venv .venv-full
   source .venv-full/Scripts/activate
   pip install --only-binary ':all:' poetry
   bash scripts/install_full_pipeline.sh python-deps
   ```

   `os-deps` is apt-only and will not run here. That is expected: it is
   not part of what a Windows host installs, and the script does not
   pretend otherwise.

4. **Install the three OS binaries by hand**, if you want rendering and
   the `verbatim` aid. There is no scripted path for these
   ([below](#-why-there-is-no-powershell-installer) says why), and
   `chitragupta doctor` reports which are missing at any point:

   ```bash
   winget install JohnMacFarlane.Pandoc
   winget install MiKTeX.MiKTeX
   winget install oschwartz10612.Poppler
   ```

   Poppler is what provides `pdftotext`; add its `bin` directory to
   `PATH` yourself, as its package does not.

5. **Check what you have:**

   ```bash
   python -m chitragupta.doctor
   ```

Without step 4, `draft render` and the `verbatim` aid report a missing
binary rather than failing obscurely, and the corresponding tests
self-skip. The citation gate, `corpus sync`, every genre skill and eight
of the ten review aids need no OS package at all.

**The tenth is `figure`, and it is the one to watch**, because it
neither refuses nor reports a missing binary: five of its eight checks
need `pdflatex`, so without TeX it runs and reports the other three,
naming what it skipped. Both of the checks a reader would call the point
of a layout check -- node overlap and content protrusion -- are in the
five. See [CLI.md](CLI.md#-chitragupta-review-figure)'s own "Needs
`pdflatex`" column for the split. A green `figure` report on a host
without TeX is three-eighths of a report, not a clean one.

## 🐧 Installing: WSL2

Install a Debian or Ubuntu distribution, then follow
[CLI.md](CLI.md#-installing) unchanged. There is no Windows-specific
step and no Windows-specific caveat: inside WSL2 this is a Linux host,
`os-deps` works, and `python-is-python3` -- which `os-deps` installs --
puts the hook launcher's name on `PATH`.

One thing that is easy to get wrong and slow to diagnose: **keep
`papers/` and `content/` on the WSL2 filesystem, not under `/mnt/c/`.**
The Windows drives are reached over a 9p mount whose per-file overhead
dominates PDF parsing, so a corpus sync over a real library there is
bound by I/O rather than by the parser. Clone into your WSL2 home
directory.

## 🎮 GPU features under WSL2

**Everything GPU-accelerated works,** which is to say the whole
`enrich` layer: Docling's PDF parsing, sentence-transformers
embeddings, and BERTopic's topic modelling. CUDA-on-WSL2 is NVIDIA's
supported configuration and PyTorch sees the device normally.

`install_full_pipeline.sh`'s `ensure_gpu_torch` needs exactly two
things, and WSL2 provides both: `nvidia-smi` on `PATH` (the Windows
driver exposes it at `/usr/lib/wsl/lib/nvidia-smi`, already on `PATH`),
and a parseable `CUDA Version: X.Y` in its header, which it prints. The
wheel-tag selection that reinstalls torch against the driver's CUDA
ceiling therefore runs unmodified.

Three things to get right:

1. **Install the NVIDIA driver on Windows only. Never inside WSL.** A
   Linux driver installed in the distribution shadows the passthrough
   and breaks CUDA. The WSL side needs no driver package.
2. **`nvidia-smi` reports the Windows driver's CUDA ceiling**, which is
   the right number for choosing a wheel -- so its output means the same
   thing here as on a bare Linux host.
3. `nvidia-smi` under WSL2 has a reduced feature set (no per-process
   listing, for one). Nothing in this repository parses those fields;
   only the CUDA version line is read.

Native Windows is CPU-only as far as this pipeline is concerned. The
`enrich` layer still runs; it is slower, and
[PERFORMANCE.md](PERFORMANCE.md) has the numbers that make that a real
consideration on a large corpus.

## 🚫 Why there is no PowerShell installer

Deliberate, and recorded here so it is not proposed as an oversight.

`DEVELOPER-AGENTS.md` forbids a second install path, and states the
invariant behind the rule: **one place a dependency fact can be
written**, so a fix lands once and every target picks it up. A `.ps1`
that created a venv and ran `poetry install` would be a second
implementation of a path that already works -- CI's Windows leg runs the
bash script and has been green for ten consecutive runs. The duplication
would buy nothing and would drift.

The genuine gap is smaller than an installer: three OS packages with no
apt behind them. Scripting `winget` would not close it either, because
the useful part is not the invocation -- it is knowing which binaries
matter and what self-skips without them, which is what this file and
`chitragupta doctor` are for.
