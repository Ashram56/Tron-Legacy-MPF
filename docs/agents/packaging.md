# Agent F: packaging (install and run on every platform)

Make the game installable and runnable by the owner on every platform the master plan targets, with **one
line to install** and **one command to run** per platform: Windows, macOS, Linux, plus the options for each
hardware target (virtual + MPF Monitor, the real machine on a P-ROC, Visual Pinball X). Part of the
[master plan](README.md). Tron Legacy MPF (this repo) is the worked example: copy its scripts, rename, and
keep them in step.

"Packaging" here is the game's **install and run kit**. It is not the ROM extraction's MPF asset package
(`mpf_package/`, agent A's `AGENTS.md` section 10) and not the game itself (agent C).

## 1. What this agent owns

Every file below is this agent's, in the game repo. Other agents may add a feature flag to `setup.py` or
`run.py` for their own work (C: `--hw proc`, `--machine le`; D: `--hw vpx`, `--vpx`; E: `--dmd ...`); this agent
then carries it into every installer, the one-line commands, Docker, CI and the docs, on every platform.

| File (Tron) | What it does |
|---|---|
| `scripts/toolchain.py` | the pinned versions (Python, MPF, Godot, GMC, MPF Monitor, extra packages per option) and every per-OS path; standard library only |
| `scripts/setup.py` | the workspace on any OS: assets submodule, `.venv/`, Godot for the host, GMC (patched), MPF Monitor and its missing `.ui` files, generated config and media, Godot import. Idempotent; `--dry-run`, `--os/--arch` plan for another host; `--no-monitor`, `--vpx`, `--skip-godot`, `--skip-media`, `--upgrade` |
| `scripts/run.py` | starts Godot (GMC, BCP 5050) first, then MPF, optionally MPF Monitor; one option per hardware target (`--hw virtual/proc/vpx`, `--machine`, `--monitor`); stale media regenerated on launch; Xvfb on Linux without a display |
| `scripts/install/install_prereqs_windows.ps1` | Windows 10/11, PowerShell 5.1 or 7: Git, Python 3.11 (winget or the official installers), long paths, the clone, `setup.py`; `-Proc` (VC++ runtime, FTDI check). Transformers adds `-Vpx` / `-Table` (section 4) |
| `scripts/install/install_prereqs_macos.sh` | macOS 12+, Intel or Apple silicon: Homebrew or python.org 3.11, Git, `setup.py`; `--proc` |
| `scripts/install/install_prereqs_linux.sh` | apt, dnf, pacman; x86_64 or arm64; Python 3.11 from the distribution, deadsnakes or uv; Qt and Xvfb libraries; `--proc` builds the driver and installs the udev rule |
| `scripts/install/build_pinproc.sh`, `99-pinproc.rules` | libpinproc and pypinproc from pinned commits (Linux, macOS) |
| `scripts/setup.bat`, `setup.ps1`, `setup_workspace.sh` | thin wrappers that find Python and run `setup.py` |
| `docker/` | Linux alternative: one image, compose services (setup, godot, mpf, monitor), overlays for GPU, audio, P-ROC; `docker/tron.sh` |
| `.github/workflows/test.yml` | CI on Windows, macOS and Linux: `setup.py`, `pytest`, render check on Linux; pushes to `main` only |
| `tests/test_install.py`, `tests/test_toolchain.py` | installers in `--dry-run`, standalone clone, private-repo token flow, Docker plans, toolchain paths, `run.py` arguments |
| Docs: README "Install" and "Play", `docs/requirements.md`, `docs/development.md` "Getting started", `docker/README.md`, the set-up parts of `docs/vpx.md` and `docs/hardware.md` (P-ROC driver) | what the owner reads to install and start the game |

## 2. Inputs

- The game repo from agent C, once its toolchain step boots MPF + GMC (playbook section 4, step 1).
- The asset repo's location and visibility (submodule at `assets/`, or a folder in the game repo: Transformers
  keeps the ROM extraction in `rom/`, so it has no second repository to check).
- The owner's hardware line from the kickoff message (desktop, VPX, P-ROC, ...): which options to build.
- D's bridge (`vpx_bridge.py --register`, `vpx_table.py`) and E's display options, as they land.

## 3. Definition of done

1. **One line to install, per platform**, given in the README, that works on a computer with nothing
   installed. It installs what is missing (Git, Python 3.11, system libraries), clones the repo (or pulls an
   existing clone), runs `setup.py`, and ends by printing the run command. Tron:

   ```powershell
   powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/<owner>/<repo>/main/scripts/install/install_prereqs_windows.ps1 | iex"
   ```
   ```sh
   bash <(curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/scripts/install/install_prereqs_macos.sh)   # or ..._linux.sh
   ```

   With options, the Windows line needs the scriptblock form:
   `powershell -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((irm <URL>))) -Vpx -Table '<table.vpx>'"`.
2. **One command to run**, per platform and target, from the install folder:
   `.venv\Scripts\python scripts\run.py [--monitor | --hw proc | --hw vpx]` (Windows), `.venv/bin/python
   scripts/run.py ...` (macOS, Linux). The installer prints it at the end, with the options it was given.
3. **Every option on every installer** the platform can support: dry run (plan only, changes nothing), no
   questions, no MPF Monitor, P-ROC, VPX (Windows only: VPX runs only there), prerequisites only, and
   pass-through arguments to `setup.py`. The same names everywhere (`--dry-run` / `-DryRun`, and so on).
4. **Safe to re-run**: every step is skipped when in place; a second run updates the clone and redoes only
   what changed. A clone whose branch was deleted on GitHub (a merged PR) moves to the default branch.
5. **Settings by environment**, one prefix per game (Tron `TRON_`, Transformers `TF_`): `<P>_DIR` (install
   folder), `<P>_BRANCH`, `<P>_REPO`, `<P>_ASSETS_REPO` when there is a second repository, `<P>_GITHUB_TOKEN`.
6. **Tests**: every installer runs in its dry-run mode in `tests/test_install.py` (Linux families, macOS plan,
   standalone clone, branch gone, token flow); `pytest -q tests` green before pushing.
7. **Docs** say the one line, the run command, the options and the requirements, in the owner's words.

## 4. Porting the kit to a new game

On Transformers the kit was not ported with the game: its VPX bridge thread had to port the Windows installer
by hand to give the owner a one-line VPX set-up (Transformers-MPF commit 85e87a3). Port it all at once, as
soon as the game repo exists:

1. Copy `scripts/toolchain.py`, `setup.py`, `run.py`, `fsutil.py`, `gmc_patch.py`, `scripts/install/`, the
   wrappers, `docker/`, the CI workflow and `tests/test_install.py` / `test_toolchain.py`.
2. Rename, in one block at the top of each installer: the environment prefix, repository URL, default
   branch, install folder name (`~/Tron-Legacy-MPF`), the assets repository (or drop that check when there
   is none), the banner text, the short-path hint (`C:\tron`), the Docker image and service names, the COM
   ProgID (`TronMPF.Controller`).
3. **Default branch**: a repository without `main` yet (Transformers, during the build) needs the working
   branch as the default and in the raw URL of the one line; switch both to `main` once it exists.
4. **VPX set-up on Windows** (Transformers, worth porting back to Tron): `-Vpx` runs `setup.py --vpx` (olefile,
   pywin32), registers the COM server elevated (`Start-Process ... -Verb RunAs -Wait`, then check the exit
   code; the rest of the script stays unelevated), and with `-Table <path>` writes the table's `.vbs` with
   `vpx_table.py` (the `.vpx` itself is never changed). The final notes add the `run.py --hw vpx` line.
5. Run every installer with its dry-run option and the tests; on Windows, ask the owner to run the one line
   (`-DryRun` first) and report the output.

## 5. Learned so far

- **Private repositories**: test read access anonymously first (`git -c credential.helper= ls-remote`), then
  ask for a fine-grained GitHub token (Contents: read-only) and pass it to git for this run only (`url.insteadOf`
  in the environment, inherited by `setup.py`), and hand it to the credential helper for later pulls. Never
  open Git Credential Manager's window. A private repository answers 404 to `curl`/`irm` without a token, so
  the one line cannot fetch itself: document clone-then-run for that case.
- **Windows PowerShell 5.1** turns a native command's stderr into a terminating error under
  `$ErrorActionPreference = 'Stop'`: run git quietly and test `$LASTEXITCODE` only.
- **Never the bare `python` on Windows**: on a fresh install it is the Microsoft Store stub. Use the `py`
  launcher, then the default install folders.
- **Long paths**: turn on `LongPathsEnabled` (needs administrator once), or keep the clone in a short folder.
- **OneDrive**: deletes and renames fail transiently; every build-time file operation goes through
  `scripts/fsutil.py`, and the default install folder is outside OneDrive.
- **Pins and launch order**: every pin carries its reason in `toolchain.py` (the playbook's toolchain table
  lists them: `ruamel.yaml.clib`, MPF Monitor's missing `.ui` files, Godot from GitHub releases); probing
  GMC's port and the start order are in the playbook's section 6 (MPF, GMC). Re-read both before changing
  `setup.py` or `run.py`.
- **macOS and Linux one lines** use `bash <(curl ...)`, not `curl | bash`, so the script keeps the terminal as
  stdin for its questions and takes options after the line (inferred from the scripts' prompts).
- **CI runs only on pushes to `main`**: test the installers locally in dry-run mode; on Windows only the
  owner can run them for real.

## 6. Tron status and open work

Built: `setup.py` and `run.py` on three OSes, the three installers with one-line install, the P-ROC build,
Docker, CI on three OSes. Open:

1. Port `-Vpx` / `-Table` from Transformers' Windows installer (section 4, step 4); `docs/vpx.md` then gives the
   one line.
2. A double-click launcher per platform (Windows shortcut or `.bat`, macOS `.command`) that runs `run.py` with
   the installed options: not built; the owner runs the command line today.
3. Transformers has only the Windows installer; macOS and Linux installers, Docker and CI are not ported.

Keep this file current with every installer change and owner test. Last updated 2026-10-08.
