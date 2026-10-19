$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$localPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$workspacePython = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../work/.venv/Scripts/python.exe'))
if (Test-Path -LiteralPath $localPython) {
    & $localPython -m uvicorn api:app --host 127.0.0.1 --port 8000 --no-access-log
} elseif (Test-Path -LiteralPath $workspacePython) {
    & $workspacePython -m uvicorn api:app --host 127.0.0.1 --port 8000 --no-access-log
} else {
    python -m uvicorn api:app --host 127.0.0.1 --port 8000 --no-access-log
}
