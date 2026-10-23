"""Write the n8n workflow 'HOMECARE C - Weekly partner report'.

Usage: python n8n/build_workflow.py <output.json> [telegram_chat_id] [telegram_credential_id]
Without a chat ID the Telegram node keeps the placeholder YOUR_TELEGRAM_CHAT_ID (this is the repo copy).
"""
import json
import sys

out = sys.argv[1]
chat_id = sys.argv[2] if len(sys.argv) > 2 else "YOUR_TELEGRAM_CHAT_ID"
cred_id = sys.argv[3] if len(sys.argv) > 3 else "YOUR_CREDENTIAL_ID"


def node(n, name, type_, pos, params, version=1, **extra):
    return {"parameters": params, "id": f"c1000000-0000-4000-8000-00000000000{n}", "name": name,
            "type": f"n8n-nodes-base.{type_}", "typeVersion": version, "position": pos, **extra}


nodes = [
    node(1, "Every Monday 08:00", "scheduleTrigger", [0, 200],
         {"rule": {"interval": [{"field": "cronExpression", "expression": "0 8 * * 1"}]}}, 1.2),
    node(2, "Run now (manual test)", "manualTrigger", [0, 400], {}),
    node(3, "Get weekly report (analytics API)", "httpRequest", [240, 300],
         {"url": "http://host.docker.internal:8001/report/weekly", "options": {"timeout": 120000}}, 4.2),
    node(4, "Telegram: summary + top alerts", "telegram", [500, 200],
         {"chatId": chat_id,
          "text": "=📊 Wochenbericht Partnernetz {{ $json.month }}\n\n{{ $json.summary }}\n\nWichtigste Hinweise:\n"
                  "{{ $json.alerts.slice(0, 3).map(a => '• ' + a.text).join('\\n') }}\n\n"
                  "Ganzer Bericht im Dashboard. (Erfundene Demo-Daten)",
          "additionalFields": {"appendAttribution": False}},
         1.2, webhookId="9e3f1a20-4b5c-4d6e-8f70-1a2b3c4d5e6f",
         credentials={"telegramApi": {"id": cred_id, "name": "HOMECARE Telegram bot"}},
         onError="continueRegularOutput"),
    node(5, "Report to file", "convertToFile", [500, 400],
         {"operation": "toText", "sourceProperty": "markdown",
          "options": {"fileName": "={{ 'weekly_report_' + $json.month + '.md' }}"}}, 1.1),
    node(6, "Save weekly_report_<month>.md", "readWriteFile", [740, 400],
         {"operation": "write", "fileName": "={{ '/files/weekly_report_' + $('Get weekly report (analytics API)').item.json.month + '.md' }}"}),
]
connections = {
    "Every Monday 08:00": {"main": [[{"node": "Get weekly report (analytics API)", "type": "main", "index": 0}]]},
    "Run now (manual test)": {"main": [[{"node": "Get weekly report (analytics API)", "type": "main", "index": 0}]]},
    "Get weekly report (analytics API)": {"main": [[
        {"node": "Telegram: summary + top alerts", "type": "main", "index": 0},
        {"node": "Report to file", "type": "main", "index": 0}]]},
    "Report to file": {"main": [[{"node": "Save weekly_report_<month>.md", "type": "main", "index": 0}]]},
}
wf = {"id": "HomecareReportC", "name": "HOMECARE C - Weekly partner report (analytics -> Telegram + file)",
      "nodes": nodes, "connections": connections, "active": False,
      "settings": {"executionOrder": "v1", "timezone": "Europe/Berlin"}, "pinData": {}}
json.dump([wf], open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("wrote", out)
