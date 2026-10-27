# Start everything for the demo: Docker + n8n, Ollama, and the four Python projects (API + dashboard each).
# Run from PowerShell:   powershell -ExecutionPolicy Bypass -File .\start_demo.ps1
# Safe to run twice: anything already running is left alone. Close a "HOMECARE ..." window to stop that part.

param([switch]$NoBrowser)   # -NoBrowser: start and check everything, but open no tabs
$root = $PSScriptRoot

function Test-Url($url) {
    try { Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 3 | Out-Null; return $true } catch { return $false }
}
function Wait-Url($name, $url, $seconds) {
    for ($i = 0; $i -lt $seconds; $i += 2) {
        if (Test-Url $url) { Write-Host "  OK    $name" -ForegroundColor Green; return $true }
        Start-Sleep 2
    }
    Write-Host "  FAIL  $name did not answer at $url" -ForegroundColor Red
    return $false
}
# Starts one Python app in its own minimized window, unless something already answers on its port.
function Start-App($title, $folder, $port, $command, $checkPath) {
    $dir = Join-Path $root $folder
    $py = Join-Path $dir ".venv\Scripts\python.exe"
    $url = "http://127.0.0.1:$port$checkPath"
    if (-not (Test-Path $py)) { Write-Host "  SKIP  $title (no .venv in $folder, see its README)" -ForegroundColor Yellow; return $false }
    if (-not (Test-Url $url)) {
        Start-Process powershell -WorkingDirectory $dir -WindowStyle Minimized -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='HOMECARE $title'; & '$py' -m $command"
    }
    return (Wait-Url ("{0,-28} http://localhost:{1}" -f $title, $port) $url 90)
}

Write-Host "1/3 Docker and n8n"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Starting Docker Desktop (can take a minute)..."
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    for ($i = 0; $i -lt 90; $i++) { docker info *> $null; if ($LASTEXITCODE -eq 0) { break }; Start-Sleep 2 }
}
docker start n8n *> $null
$ok = @(Wait-Url "n8n                          http://localhost:5678" "http://localhost:5678/healthz" 90)

Write-Host "2/3 Ollama"
if (-not (Test-Url "http://127.0.0.1:11434")) { Start-Process ollama -ArgumentList "serve" -WindowStyle Minimized }
$okOllama = Wait-Url "Ollama                       http://localhost:11434" "http://127.0.0.1:11434" 30
$ok += $okOllama

Write-Host "3/3 Projects"
$uv = "uvicorn app.main:app --host 127.0.0.1 --port"
$st = "streamlit run dashboard.py --server.headless true --browser.gatherUsageStats false --server.port"
$ok += Start-App "1 Intake API"           "intake-service"    8000 "$uv 8000" "/docs"
$ok += Start-App "1 Intake dashboard"     "intake-service"    8501 "$st 8501" ""
$ok += Start-App "3 Analytics API"        "partner-analytics" 8001 "$uv 8001" "/docs"
$ok += Start-App "3 Analytics dashboard"  "partner-analytics" 8502 "$st 8502" ""
$ok += Start-App "4 Handbook API"         "partner-handbook"  8002 "$uv 8002" "/docs"
$ok += Start-App "4 Handbook dashboard"   "partner-handbook"  8503 "$st 8503" ""
$ok += Start-App "5 Onboarding API"       "partner-onboarding" 8003 "$uv 8003" "/docs"
$ok += Start-App "5 Onboarding dashboard" "partner-onboarding" 8504 "$st 8504" ""

# The demo page: one tab per project, the steps on the left and the running app on the right.
$hubPy = Join-Path $root "intake-service\.venv\Scripts\python.exe"
if (-not (Test-Url "http://127.0.0.1:8500")) {
    Start-Process powershell -WorkingDirectory (Join-Path $root "demo") -WindowStyle Minimized -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='HOMECARE Demo page'; & '$hubPy' -m http.server 8500 --bind 127.0.0.1"
}
$ok += Wait-Url "Demo page                    http://localhost:8500" "http://127.0.0.1:8500" 20

# Load both models into memory now, so the first live question isn't slow.
if ($okOllama) {
    Write-Host "Warming up the models..."
    try { Invoke-RestMethod http://127.0.0.1:11434/api/generate -Method Post -Body '{"model":"qwen2.5:3b","prompt":"hi","stream":false,"options":{"num_predict":1}}' -TimeoutSec 120 | Out-Null } catch {}
    try { Invoke-RestMethod http://127.0.0.1:11434/api/embed -Method Post -Body '{"model":"granite-embedding:278m","input":"Hallo"}' -TimeoutSec 120 | Out-Null } catch {}
}

if ($ok -notcontains $false) {
    Write-Host "`nAll running: dashboards on 8501, 8502, 8503, 8504; n8n on 5678." -ForegroundColor Green
} else {
    Write-Host "`nSomething did not start; see FAIL/SKIP above." -ForegroundColor Red
}
if (-not $NoBrowser) {
    # "localhost" (not 127.0.0.1) so the n8n login also works inside the page.
    Start-Process "http://localhost:8500/"
}
