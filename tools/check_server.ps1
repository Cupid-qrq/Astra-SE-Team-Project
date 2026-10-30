[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if (-not $env:ASTRA_TEST_DATABASE_URL) {
    throw 'ASTRA_TEST_DATABASE_URL 必须指向独立的 PostgreSQL _test 数据库，不能跳过验证。'
}
Push-Location -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'server')
try {
    & uv sync --locked
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & uv run --locked ruff check app/shared tests/shared migrations
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & uv run --locked ruff format --check app/shared tests/shared migrations
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & uv run --locked mypy app/shared
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & uv run --locked pytest tests/shared
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
exit 0
