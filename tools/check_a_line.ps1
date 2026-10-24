[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$uv = Get-Command uv -ErrorAction SilentlyContinue
$uvPath = if ($uv) { $uv.Source } else { Join-Path $repo '.local/a-tools/Scripts/uv.exe' }
if (-not (Test-Path -LiteralPath $uvPath)) { throw '请先安装 uv 0.13.5，并配置 ASTRA_A_DATABASE_URL 指向专用 _test PostgreSQL 数据库。' }
if (-not $env:ASTRA_A_DATABASE_URL) { throw 'ASTRA_A_DATABASE_URL 必须指向真实 PostgreSQL 测试库，不能跳过数据库验证。' }
Push-Location -LiteralPath $repo
try {
    $env:PYTHONUTF8 = '1'
    & $uvPath sync --frozen --project server/a_line
    if ($LASTEXITCODE -ne 0) { throw 'A线依赖锁安装失败' }
    & $uvPath run --project server/a_line ruff check --config server/a_line/pyproject.toml server/app server/a_line/astra_a server/a_line/migrations server/tests/a_line
    if ($LASTEXITCODE -ne 0) { throw 'A线静态检查失败' }
    & $uvPath run --project server/a_line ruff format --check --config server/a_line/pyproject.toml server/app server/a_line/astra_a server/a_line/migrations server/tests/a_line
    if ($LASTEXITCODE -ne 0) { throw 'A线格式检查失败' }
    $env:MYPYPATH = (Join-Path $repo 'server') + [IO.Path]::PathSeparator + (Join-Path $repo 'server/a_line')
    & $uvPath run --project server/a_line mypy --config-file server/a_line/pyproject.toml -p app -p astra_a
    if ($LASTEXITCODE -ne 0) { throw 'A线类型检查失败' }
    & $uvPath run --project server/a_line pytest -c server/a_line/pyproject.toml server/tests/a_line
    if ($LASTEXITCODE -ne 0) { throw 'A线数据库与业务测试失败' }
    $env:ASTRA_A_PYTHON = (& $uvPath run --project server/a_line python -c 'import sys; print(sys.executable)').Trim()
    & pnpm --dir apps/web exec playwright test -c playwright.integration.config.ts
    if ($LASTEXITCODE -ne 0) { throw 'A线真实数据库浏览器集成失败' }
} finally {
    Pop-Location
}
