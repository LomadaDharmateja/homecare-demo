# Send one request through n8n, as a customer would.  Usage:
#   .\send_example.ps1 notfall | fehlt | einkauf | unklar | urgent | "Beliebiger eigener Text"
# German first (most real requests), plus one English example. Saved as UTF-8 with BOM so umlauts work in PowerShell 5.1.
param([string]$which = "notfall")

$examples = @{
    notfall = "Meine Mutter (86) ist heute früh in ihrer Wohnung in Neuss gestürzt. Sie ist jetzt allein und sehr unsicher. Kann heute noch jemand bei ihr bleiben? Bitte rufen Sie mich sofort zurück."
    fehlt   = "Könnte jemand meinen Vater nächsten Mittwoch um 10 Uhr zur Physiotherapie fahren? Er geht mit Rollator."
    einkauf = "Guten Tag, wir suchen ab nächster Woche Hilfe beim Einkaufen für meine Oma in Köln. Bitte rufen Sie mich nachmittags an."
    unklar  = "Hallo, eine Bekannte hat Sie empfohlen. Was für Hilfe bieten Sie eigentlich an?"
    urgent  = "My father (84) fell in the kitchen in Neuss this morning. He is okay but shaky and alone. Can someone stay with him today? Please call me back as soon as possible."
}
$text = if ($examples.ContainsKey($which)) { $examples[$which] } else { $which }

$body = @{ text = $text; channel = "web_form" } | ConvertTo-Json
Write-Host "Sende: $text`nDie lokale KI braucht etwa 10-30 Sekunden..."
$r = Invoke-RestMethod -Uri http://localhost:5678/webhook/homecare-intake -Method Post `
     -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 180
$r | Select-Object id, service_type, urgency, priority, location, when_needed, callback_requested, missing_info, summary, followup_status | Format-List
Write-Host "Antwort-Entwurf (wartet auf Freigabe im Dashboard):`n$($r.followup_draft)"
