[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('backup','restore','inventory')][string]$Action,[Parameter(Mandatory)][string]$File,[string]$Target)
$ErrorActionPreference='Stop'
if(-not $env:ASTRA_DATABASE_URL){throw '请通过本地私有配置设置ASTRA_DATABASE_URL。'}
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskScript=(wsl -d Ubuntu -- wslpath -a -u ((Join-Path $taskRoot 'tools/database_backup.py').Replace('\','/')) 2>$null).Trim()
$taskFile=(wsl -d Ubuntu -- wslpath -a -u (([IO.Path]::GetFullPath($File)).Replace('\','/')) 2>$null).Trim()
$env:WSLENV=(@($env:WSLENV,'ASTRA_DATABASE_URL')|Where-Object{$_}) -join ':'
$taskArgs=@('-d','Ubuntu','--','python3',$taskScript,$Action,'--file',$taskFile)
if($Target){$taskArgs+=@('--target',$Target)}
& wsl @taskArgs
exit $LASTEXITCODE
