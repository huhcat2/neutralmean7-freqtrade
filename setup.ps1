$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath ".venv/Scripts/python.exe")) {
    py -3.13 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python 3.13 is required." }
}
& ./.venv/Scripts/python.exe -m pip install -r requirements-tested.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& ./.venv/Scripts/python.exe -m pip install --no-deps -e ./freqtrade
if ($LASTEXITCODE -ne 0) { throw "Freqtrade installation failed." }
& ./.venv/Scripts/python.exe ./release/install_qstrat.py ./release/NeutralMean7.qstrat --userdir ./user_data
if ($LASTEXITCODE -ne 0) { throw "Strategy installation failed." }
& ./.venv/Scripts/freqtrade.exe --version
