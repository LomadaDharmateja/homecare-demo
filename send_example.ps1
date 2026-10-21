# Send one request through n8n, as a customer would.  Usage:
#   .\send_example.ps1 urgent | missing | german | vague
#   .\send_example.ps1 "Any text you like"
param([string]$which = "urgent")

$examples = @{
    urgent   = "My father (84) fell in the kitchen in Neuss this morning. He is okay but shaky and alone. Can someone stay with him today? Please call me back as soon as possible."
    missing  = "Could someone drive my mother to her physiotherapy appointment next Wednesday at 10 am? She uses a walker."
    german   = "Guten Tag, wir suchen ab naechster Woche Hilfe beim Einkaufen fuer meine Oma in Koeln. Bitte rufen Sie mich nachmittags an."
    vague    = "Hi, a friend told me about you. What kind of help do you offer?"
}
$text = if ($examples.ContainsKey($which)) { $examples[$which] } else { $which }

$body = @{ text = $text; channel = "web_form" } | ConvertTo-Json
Write-Host "Sending: $text`nThe local AI takes about 10-30 seconds..."
$r = Invoke-RestMethod -Uri http://localhost:5678/webhook/homecare-intake -Method Post `
     -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 180
$r | Select-Object id, service_type, urgency, priority, location, when_needed, callback_requested, missing_info, followup_status | Format-List
Write-Host "Draft reply (waiting for approval in the dashboard):`n$($r.followup_draft)"
