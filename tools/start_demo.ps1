[CmdletBinding()]
param([string]$ConfigFile)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
if (-not $ConfigFile) {$ConfigFile=Join-Path $taskRoot '.local/course-demo/application.json'}
$taskConfig=Get-Content -LiteralPath $ConfigFile -Raw | ConvertFrom-Json -AsHashtable
foreach($taskKey in $taskConfig.Keys){if($taskKey -match '^(ASTRA_|VITE_API_PROXY_TARGET$)'){Set-Item "Env:$taskKey" ([string]$taskConfig[$taskKey])}}
$taskDirectory=Join-Path $taskRoot '.local/course-demo'
New-Item -ItemType Directory -Path $taskDirectory -Force | Out-Null
if(Get-NetTCPConnection -LocalPort 8021,4176 -State Listen -ErrorAction SilentlyContinue){throw '演示端口已占用，请先核对已运行的演示进程。'}
Push-Location $taskRoot
try {
 & uv sync --locked --project server
 if($LASTEXITCODE -ne 0){throw '服务依赖准备失败'}
 $taskPython=(Join-Path $taskRoot 'server/.venv/Scripts/python.exe')
 & $taskPython tools/create_demo_tls.py (Join-Path $taskDirectory 'tls')
 if($LASTEXITCODE -ne 0){throw '本地TLS准备失败'}
 Push-Location (Join-Path $taskRoot 'apps/web')
 try { & pnpm exec tsc -b; if($LASTEXITCODE -ne 0){throw '前端类型检查失败'}; & node node_modules/vite/bin/vite.js build --outDir (Join-Path $taskDirectory 'dist'); if($LASTEXITCODE -ne 0){throw '前端构建失败'} } finally {Pop-Location}
 $env:ASTRA_DEMO_TLS=Join-Path $taskDirectory 'tls'
 $env:VITE_API_PROXY_TARGET='http://127.0.0.1:8021'
 $taskProcesses=@()
 # A foreground WSL command keeps the local PostgreSQL host alive during the demo.
 $taskDatabaseHost=Start-Process -FilePath wsl.exe -ArgumentList @('-d','Ubuntu','--exec','sleep','infinity') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskDirectory 'database-host.out.log') -RedirectStandardError (Join-Path $taskDirectory 'database-host.err.log') -PassThru
 $taskProcesses+=@{name='database-host';id=$taskDatabaseHost.Id;started=$taskDatabaseHost.StartTime.ToUniversalTime().ToString('o')}
 $taskProcesses|ConvertTo-Json -AsArray|Set-Content -LiteralPath (Join-Path $taskDirectory 'processes.json') -Encoding utf8
 $taskDatabaseReady=$false
 for($taskAttempt=0;$taskAttempt -lt 15;$taskAttempt++){
  & $taskPython -c "import os; from sqlalchemy import create_engine; engine=create_engine(os.environ['ASTRA_DATABASE_URL'],hide_parameters=True,connect_args={'connect_timeout':2}); connection=engine.connect(); connection.exec_driver_sql('SELECT 1'); connection.close(); engine.dispose()" 2>$null | Out-Null
  if($LASTEXITCODE -eq 0){$taskDatabaseReady=$true;break}
  Start-Sleep -Seconds 1
 }
 if(-not $taskDatabaseReady){throw '演示数据库未就绪，请检查Ubuntu PostgreSQL状态；可用停止脚本清理本次进程。'}
 $taskSpecs=@(
  @{Name='api';Args=@('-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port','8021','--no-access-log')},
  @{Name='judge';Args=@('-m','app.modules.judging.worker_cli','--enable-execution','--executor-host',$env:ASTRA_EXECUTOR_HOST,'--image',$env:ASTRA_EXECUTOR_IMAGE,'--executor-state-dir','/var/lib/astra-course-executor-demo')},
  @{Name='notifications';Args=@('-m','app.modules.operations.worker')}
 )
 foreach($taskSpec in $taskSpecs){
  $taskProcess=Start-Process -FilePath $taskPython -ArgumentList $taskSpec.Args -WorkingDirectory (Join-Path $taskRoot 'server') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskDirectory ($taskSpec.Name+'.out.log')) -RedirectStandardError (Join-Path $taskDirectory ($taskSpec.Name+'.err.log')) -PassThru
  $taskProcesses+=@{name=$taskSpec.Name;id=$taskProcess.Id;started=$taskProcess.StartTime.ToUniversalTime().ToString('o')}
 }
 $taskNode=(Get-Command node).Source
 $taskVite=Join-Path $taskRoot 'apps/web/node_modules/vite/bin/vite.js'
 $taskProcess=Start-Process -FilePath $taskNode -ArgumentList @($taskVite,'preview','--outDir',(Join-Path $taskDirectory 'dist'),'--host','127.0.0.1','--port','4176','--strictPort') -WorkingDirectory (Join-Path $taskRoot 'apps/web') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskDirectory 'web.out.log') -RedirectStandardError (Join-Path $taskDirectory 'web.err.log') -PassThru
 $taskProcesses+=@{name='web';id=$taskProcess.Id;started=$taskProcess.StartTime.ToUniversalTime().ToString('o')}
 $taskProcesses|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $taskDirectory 'processes.json') -Encoding utf8
 Write-Output '演示地址 https://localhost:4176；进程与日志位于 .local/course-demo。'
} finally {Pop-Location}
