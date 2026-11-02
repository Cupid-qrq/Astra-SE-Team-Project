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
    & uv run --locked ruff check app/shared app/adapters app/modules/judging app/api app/main.py tests/shared tests/judge migrations ../tools/check_api_contract.py ../tools/verify_judge.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & uv run --locked ruff format --check app/shared app/adapters app/modules/judging app/api app/main.py tests/shared tests/judge migrations ../tools/check_api_contract.py ../tools/verify_judge.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & uv run --locked mypy app/shared app/adapters app/modules/judging app/api app/main.py ../tools/verify_judge.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & uv run --locked python ../tools/check_api_contract.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & uv run --locked pytest tests/shared tests/judge
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $env:ASTRA_SERVER_PYTHON = (& uv run --locked python -c 'import sys; print(sys.executable)').Trim()
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Push-Location -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'apps/web')
    try {
        & pnpm run e2e:server
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        Pop-Location
    }
} finally {
    Pop-Location
}
exit 0
