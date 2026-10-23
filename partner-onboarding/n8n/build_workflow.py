"""Write the n8n workflow 'HOMECARE E - Onboarding cockpit'.

Two entry points in one workflow:
  1. Webhook POST /webhook/partner-update {partner_id, nachricht}: a partner's e-mail (in production: an
     e-mail trigger) goes to the local API, which stores a proposal. Nothing changes until a person approves.
  2. Mon-Fri 08:30 (or "Run now"): risk digest from the API to Telegram.
Usage: python n8n/build_workflow.py <output.json> [telegram_chat_id] [telegram_credential_id]
Without a chat ID the Telegram node keeps the placeholder YOUR_TELEGRAM_CHAT_ID (this is the repo copy).
"""
import json
import sys

out = sys.argv[1]
chat_id = sys.argv[2] if len(sys.argv) > 2 else "YOUR_TELEGRAM_CHAT_ID"
cred_id = sys.argv[3] if len(sys.argv) > 3 else "YOUR_CREDENTIAL_ID"
API = "http://host.docker.internal:8003"


def node(n, name, type_, pos, params, version=1, **extra):
    return {"parameters": params, "id": f"e1000000-0000-4000-8000-00000000000{n}", "name": name,
            "type": f"n8n-nodes-base.{type_}", "typeVersion": version, "position": pos, **extra}


nodes = [
    node(1, "Partner-Update (Webhook)", "webhook", [0, 100],
         {"httpMethod": "POST", "path": "partner-update", "responseMode": "responseNode", "options": {}}, 2,
         webhookId="e1000000-0000-4000-8000-0000000000aa"),
    node(2, "Vorschlag erstellen (lokale API)", "httpRequest", [240, 100],
         {"method": "POST", "url": f"{API}/updates", "sendBody": True, "specifyBody": "json",
          "jsonBody": "={{ JSON.stringify({ partner_id: Number($json.body.partner_id), nachricht: $json.body.nachricht, "
                      "quelle: 'E-Mail (n8n)' }) }}",
          "options": {"timeout": 120000}}, 4.2),
    node(3, "Antwort: Vorschlag wartet auf Freigabe", "respondToWebhook", [480, 100], {"options": {}}, 1.1),
    node(4, "Mo-Fr 08:30", "scheduleTrigger", [0, 340],
         {"rule": {"interval": [{"field": "cronExpression", "expression": "30 8 * * 1-5"}]}}, 1.2),
    node(5, "Jetzt ausführen (Test)", "manualTrigger", [0, 520], {}),
    node(6, "Risiken holen (lokale API)", "httpRequest", [240, 420], {"url": f"{API}/risiken", "options": {}}, 4.2),
    node(7, "Telegram: Onboarding-Risiken", "telegram", [480, 420],
         {"chatId": chat_id, "text": "={{ $json.text }}", "additionalFields": {"appendAttribution": False}},
         1.2, webhookId="e1000000-0000-4000-8000-0000000000bb",
         credentials={"telegramApi": {"id": cred_id, "name": "HOMECARE Telegram bot"}},
         onError="continueRegularOutput"),
]
connections = {
    "Partner-Update (Webhook)": {"main": [[{"node": "Vorschlag erstellen (lokale API)", "type": "main", "index": 0}]]},
    "Vorschlag erstellen (lokale API)": {"main": [[{"node": "Antwort: Vorschlag wartet auf Freigabe", "type": "main",
                                                    "index": 0}]]},
    "Mo-Fr 08:30": {"main": [[{"node": "Risiken holen (lokale API)", "type": "main", "index": 0}]]},
    "Jetzt ausführen (Test)": {"main": [[{"node": "Risiken holen (lokale API)", "type": "main", "index": 0}]]},
    "Risiken holen (lokale API)": {"main": [[{"node": "Telegram: Onboarding-Risiken", "type": "main", "index": 0}]]},
}
wf = {"id": "HomecareOnboardingE", "name": "HOMECARE E - Onboarding (partner update -> approval queue; daily risks -> Telegram)",
      "nodes": nodes, "connections": connections, "active": False,
      "settings": {"executionOrder": "v1", "timezone": "Europe/Berlin"}, "pinData": {}}
json.dump([wf], open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("wrote", out)
