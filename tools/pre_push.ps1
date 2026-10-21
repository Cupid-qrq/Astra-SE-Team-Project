[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

function Invoke-GitText {
    param([string[]]$GitArgs)
    $value = & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "git failed: $GitArgs" }
    return ($value -join "`n").Trim()
}

$remoteUrl = Invoke-GitText -GitArgs @('remote','get-url','origin')
if ($remoteUrl -notin @('https://github.com/Cupid-qrq/Astra-SE-Team-Project.git','https://github.com/Cupid-qrq/Astra-SE-Team-Project','git@github.com:Cupid-qrq/Astra-SE-Team-Project.git')) {
    throw 'origin不是正式仓库'
}
$pushUrls = (Invoke-GitText -GitArgs @('remote','get-url','--push','--all','origin')) -split "`n"
if ($pushUrls.Count -ne 1 -or $pushUrls[0] -notin @('https://github.com/Cupid-qrq/Astra-SE-Team-Project.git','https://github.com/Cupid-qrq/Astra-SE-Team-Project','git@github.com:Cupid-qrq/Astra-SE-Team-Project.git')) {
    throw 'origin push URL 必须唯一且指向正式仓库'
}
if (Invoke-GitText -GitArgs @('status','--porcelain')) { throw '工作区有未提交或未跟踪文件，请先检查并提交' }
$branch = Invoke-GitText -GitArgs @('branch','--show-current')
if (-not $branch -or $branch -in @('main','master')) { throw '必须在工作分支执行' }
Invoke-GitText -GitArgs @('fetch','origin','--prune') | Out-Null
& git merge-base --is-ancestor origin/main HEAD
if ($LASTEXITCODE -ne 0) { throw '尚未包含最新origin/main，先集成并重新验证' }
& git show-ref --verify --quiet "refs/remotes/origin/$branch"
if ($LASTEXITCODE -eq 0) {
    & git merge-base --is-ancestor "origin/$branch" HEAD
    if ($LASTEXITCODE -ne 0) { throw '远程工作分支有本地未包含的提交，禁止覆盖' }
}
& python tools/check_repository.py
if ($LASTEXITCODE -ne 0) { throw '仓库静态检查失败' }
& python -m unittest discover -s tools/tests -v
if ($LASTEXITCODE -ne 0) { throw '开发工具回归失败' }
& python tools/check_commits.py --base origin/main --head HEAD
if ($LASTEXITCODE -ne 0) { throw '新commit标题不合规范' }
& git diff --check origin/main...HEAD -- . ':(exclude)archive/submissions/**'
if ($LASTEXITCODE -ne 0) { throw 'diff空白检查失败' }
& python tools/check_runtime.py
if ($LASTEXITCODE -ne 0) { throw '完整开发检查失败' }
Write-Output "本地检查通过，分支：$branch"
Write-Output ('HEAD：' + (Invoke-GitText -GitArgs @('rev-parse','HEAD')))
Write-Output ('origin/main：' + (Invoke-GitText -GitArgs @('rev-parse','origin/main')))
Write-Output '尚未推送。双方进度、未推送依赖、远端CI和非作者审批按PR模板核验。'
