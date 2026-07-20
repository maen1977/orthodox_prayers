$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
python scripts/verify_r11_patch.py
python -m unittest discover -s tests -p "test_*.py"
Write-Host "R11_APPLY_OK: files are in the repository root."
