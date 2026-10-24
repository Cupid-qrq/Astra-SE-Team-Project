[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'apps/web')
try {
    & pnpm install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw '锁文件依赖安装失败' }
    foreach ($step in @('format:check', 'lint', 'typecheck', 'contracts:check', 'test', 'build', 'production:check', 'e2e', 'e2e:production')) {
        & pnpm run $step
        if ($LASTEXITCODE -ne 0) { throw "前端检查失败：$step" }
    }
} finally {
    Pop-Location
}
