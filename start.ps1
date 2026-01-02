param(
    [int]$Port = 8000,
    [string]$Host = "0.0.0.0"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
Set-Location $repoRoot

$venvActivate = Join-Path $repoRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Error ".venv not found. Create it with: python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r pi\requirements.txt"
}

. $venvActivate

$piPath = Join-Path $repoRoot "pi"
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$($env:PYTHONPATH);$piPath"
} else {
    $env:PYTHONPATH = $piPath
}

if (-not $env:LT_DB_PATH) {
    $env:LT_DB_PATH = Join-Path $piPath "data\lighttracker.db"
}

$dbDir = Split-Path $env:LT_DB_PATH -Parent
if (-not (Test-Path $dbDir)) {
    New-Item -ItemType Directory -Force -Path $dbDir | Out-Null
}

if (-not $env:MQTT_HOST) { $env:MQTT_HOST = "localhost" }
if (-not $env:MQTT_PORT) { $env:MQTT_PORT = "1883" }
if (-not $env:DMX_UART_DEVICE) { $env:DMX_UART_DEVICE = "/dev/ttyUSB0" }

Write-Host "Starting LightTracker API on $Host:$Port (DB=$env:LT_DB_PATH)..." -ForegroundColor Cyan
uvicorn app.main:app --host $Host --port $Port
