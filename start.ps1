$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$medibedPython = Join-Path $env:LOCALAPPDATA 'MediBed\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $medibedPython)) {
    python -m venv --copies (Join-Path $env:LOCALAPPDATA 'MediBed\venv')
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
& $medibedPython -c "import flask, flask_sqlalchemy, dotenv, sklearn, numpy"
if ($LASTEXITCODE -ne 0) {
    & $medibedPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& $medibedPython app.py
