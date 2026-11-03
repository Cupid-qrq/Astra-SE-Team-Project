[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskFile=Join-Path $taskRoot '.local/course-demo/processes.json'
function Stop-DemoTree([int]$TaskProcessId){
 foreach($taskChild in (Get-CimInstance Win32_Process -Filter "ParentProcessId=$TaskProcessId" -ErrorAction SilentlyContinue)){Stop-DemoTree -TaskProcessId $taskChild.ProcessId}
 Stop-Process -Id $TaskProcessId -ErrorAction SilentlyContinue
}
foreach($taskRecord in (Get-Content -LiteralPath $taskFile -Raw|ConvertFrom-Json)){
 $taskProcess=Get-Process -Id $taskRecord.id -ErrorAction SilentlyContinue
 if($taskProcess -and $taskProcess.StartTime.ToUniversalTime().Ticks -eq ([datetime]$taskRecord.started).ToUniversalTime().Ticks){Stop-DemoTree -TaskProcessId $taskProcess.Id}
}
Write-Output '已停止本次记录的演示进程。'
