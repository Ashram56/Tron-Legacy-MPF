# Installs the pinned toolchain on Windows (MPF, Godot, GMC, generated media): runs scripts/setup.py.
# Usage (PowerShell, in the repo):  .\scripts\setup.ps1 [--monitor] [--dry-run] ...
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { & py -3 "$root\scripts\setup.py" @args } else { & python "$root\scripts\setup.py" @args }
exit $LASTEXITCODE
