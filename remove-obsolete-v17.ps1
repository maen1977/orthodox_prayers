param(
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$obsolete = Join-Path $PSScriptRoot "src\SafeWindowsCleaner\MainWindow.V17.cs"

if (Test-Path $obsolete) {
    Remove-Item $obsolete -Force
    if (-not $Quiet) {
        Write-Host "Removed obsolete MainWindow.V17.cs." -ForegroundColor Green
    }
} elseif (-not $Quiet) {
    Write-Host "No obsolete MainWindow.V17.cs was found." -ForegroundColor DarkGray
}
