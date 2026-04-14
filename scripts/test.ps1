$ErrorActionPreference = "Stop"

uv sync --dev
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

uv run pytest -v
exit $LASTEXITCODE
