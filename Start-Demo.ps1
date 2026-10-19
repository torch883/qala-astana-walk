[CmdletBinding()]
param(
    [string]$Python,
    [ValidateRange(1024, 65535)][int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$localPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not $Python) {
    if (Test-Path -LiteralPath $localPython) { $Python = $localPython }
    else { $Python = (Get-Command python -ErrorAction Stop).Source }
}
& $Python -m uvicorn api:app --host 127.0.0.1 --port $Port --no-access-log
exit $LASTEXITCODE
