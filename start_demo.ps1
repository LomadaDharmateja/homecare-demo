# Start everything for the demo: Docker + n8n, Ollama, the API and the dashboard.
# Run from PowerShell:   powershell -ExecutionPolicy Bypass -File .\start_demo.ps1
# Safe to run twice: anything already running is left alone.

$root = $PSScriptRoot
$svc  = Join-Path $root "intake-service"
$py   = Join-Path $svc ".venv\Scripts\python.exe"

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

Write-Host "1/4 Docker and n8n"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Starting Docker Desktop (can take a minute)..."
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    for ($i = 0; $i -lt 90; $i++) { docker info *> $null; if ($LASTEXITCODE -eq 0) { break }; Start-Sleep 2 }
}
docker start n8n *> $null
$okN8n = Wait-Url "n8n        http://localhost:5678" "http://localhost:5678/healthz" 90

Write-Host "2/4 Ollama"
if (-not (Test-Url "http://127.0.0.1:11434")) { Start-Process ollama -ArgumentList "serve" -WindowStyle Minimized }
$okOllama = Wait-Url "Ollama     http://localhost:11434" "http://127.0.0.1:11434" 30

Write-Host "3/4 API (agent + database)"
if (-not (Test-Url "http://127.0.0.1:8000/requests")) {
    Start-Process powershell -WorkingDirectory $svc -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='HOMECARE API'; & '$py' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
}
$okApi = Wait-Url "API        http://localhost:8000/docs" "http://127.0.0.1:8000/requests" 60

Write-Host "4/4 Dashboard"
if (-not (Test-Url "http://127.0.0.1:8501")) {
    Start-Process powershell -WorkingDirectory $svc -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='HOMECARE dashboard'; & '$py' -m streamlit run dashboard.py --server.headless true --server.port 8501 --browser.gatherUsageStats false"
}
$okDash = Wait-Url "Dashboard  http://localhost:8501" "http://127.0.0.1:8501" 60

# Load the model into memory now, so the first live request isn't slow.
if ($okOllama) {
    Write-Host "Warming up the model..."
    try { Invoke-RestMethod http://127.0.0.1:11434/api/generate -Method Post -Body '{"model":"qwen2.5:3b","prompt":"hi","stream":false,"options":{"num_predict":1}}' -TimeoutSec 120 | Out-Null } catch {}
}

if ($okN8n -and $okOllama -and $okApi -and $okDash) {
    Write-Host "`nAll running. Opening the dashboard and n8n." -ForegroundColor Green
    Start-Process "http://localhost:8501"
    Start-Process "http://localhost:5678"
} else {
    Write-Host "`nSomething did not start; see FAIL above." -ForegroundColor Red
}
