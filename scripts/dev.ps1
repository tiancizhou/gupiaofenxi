$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

uv sync --dev --project $ProjectRoot
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

uv run --project $ProjectRoot python "$ProjectRoot/run.py"
exit $LASTEXITCODE
