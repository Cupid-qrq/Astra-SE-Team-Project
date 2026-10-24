[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
# A branch integration adapter. B owns this entry and must append the actual
# server/database checks when P0-B1 merges; never replace them with this subset.
& pwsh -NoProfile -File (Join-Path $PSScriptRoot 'check_web.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& pwsh -NoProfile -File (Join-Path $PSScriptRoot 'check_a_line.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& python (Join-Path $PSScriptRoot 'model_probe.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
