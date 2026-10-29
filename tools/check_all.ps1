[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
# Unified entry: preserve A/web checks and include B shared infrastructure.
# Formal migrations, HTTP and isolation enter in later reviewed stages.
& pwsh -NoProfile -File (Join-Path $PSScriptRoot 'check_web.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& pwsh -NoProfile -File (Join-Path $PSScriptRoot 'check_a_line.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& python (Join-Path $PSScriptRoot 'model_probe.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& pwsh -NoProfile -File (Join-Path $PSScriptRoot 'check_server.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
