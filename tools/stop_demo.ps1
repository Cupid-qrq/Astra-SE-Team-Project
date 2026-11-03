[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskFile=Join-Path $taskRoot '.local/course-demo/processes.json'
foreach($taskRecord in (Get-Content -LiteralPath $taskFile -Raw|ConvertFrom-Json)){
 $taskProcess=Get-Process -Id $taskRecord.id -ErrorAction SilentlyContinue
 if($taskProcess -and $taskProcess.StartTime.ToUniversalTime().ToString('o') -eq $taskRecord.started){Stop-Process -Id $taskProcess.Id}
}
Write-Output '已停止本次记录的演示进程。'
