# Import the n8n-only onboarding cockpit into the local n8n container and publish it.
# Usage (PowerShell, from the partner-onboarding folder):
#   .\n8n-native\import_to_n8n.ps1 -ChatId <your Telegram chat ID> -TelegramCredentialId <n8n credential ID>
# The chat ID is only written to a temp folder, never to the repo.
param([string]$ChatId = "YOUR_TELEGRAM_CHAT_ID", [string]$TelegramCredentialId = "YOUR_CREDENTIAL_ID")
$ErrorActionPreference = "Stop"
$tmp = Join-Path $env:TEMP "obimport"
.\.venv\Scripts\python.exe n8n-native\build_workflows.py $tmp $ChatId $TelegramCredentialId
docker exec -u root n8n mkdir -p /tmp/obimport
docker cp "$tmp\." n8n:/tmp/obimport/
docker exec n8n n8n import:credentials --input=/tmp/obimport/ollama_credential.json
foreach ($w in "setup", "update", "ampel", "bericht", "seite") { docker exec n8n n8n import:workflow --input=/tmp/obimport/$w.json }
foreach ($id in "HCob1Einrichtung", "HCob2PartnerUpd0", "HCob3AmpelRegeln", "HCob4MorgenBerch", "HCob5CockpitSeit") {
  docker exec n8n n8n publish:workflow --id=$id
}
docker exec -u root n8n rm -rf /tmp/obimport
Remove-Item -Recurse -Force $tmp
docker restart n8n
Write-Host "Done. Wait ~20 s, then: Invoke-RestMethod -Method Post http://localhost:5678/webhook/onboarding-einrichtung"
