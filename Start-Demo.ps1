$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$localPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$workspacePython = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../work/.venv/Scripts/python.exe'))
if (Test-Path -LiteralPath $localPython) {
    & $localPython -m streamlit run app.py
} elseif (Test-Path -LiteralPath $workspacePython) {
    & $workspacePython -m streamlit run app.py
} else {
    python -m streamlit run app.py
}
