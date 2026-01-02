# PowerShell smoke test script
param(
  [string]$Base = 'http://127.0.0.1:8000'
)

Write-Host 'Check state...'
Invoke-RestMethod "$Base/api/v1/state" | ConvertTo-Json -Depth 5

Write-Host 'Check anchors...'
Invoke-RestMethod "$Base/api/v1/anchors" | ConvertTo-Json -Depth 5

Write-Host 'Insert anchor position...'
Invoke-RestMethod -Method Post -Uri "$Base/api/v1/anchors/position" -ContentType 'application/json' -Body '{"mac":"AA:BB:CC:11:22:33","x_cm":100,"y_cm":200,"z_cm":300}' | ConvertTo-Json -Depth 5

Write-Host 'Check fixtures...'
Invoke-RestMethod "$Base/api/v1/fixtures" | ConvertTo-Json -Depth 5

Write-Host 'Health...'
Invoke-RestMethod "$Base/api/v1/health" | ConvertTo-Json -Depth 5

Write-Host 'Calibration start...'
Invoke-RestMethod -Method Post -Uri "$Base/api/v1/calibration/start" -ContentType 'application/json' -Body '{"tag_mac":"AA:BB:CC:00:11:22","duration_ms":1000}' | ConvertTo-Json -Depth 5

Write-Host 'done'
