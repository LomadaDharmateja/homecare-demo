"""Write the n8n workflow 'HOMECARE D - Ask the partner handbook (chat)'.

Usage: python n8n/build_workflow.py n8n/handbook_chat_workflow.json
No secrets: the chat runs inside the n8n editor ("Open chat"), the handbook API runs on this laptop.
Chat mode "webhook" (Embedded Chat): a plain chat API, no hosted page. The hosted page is deliberately not used:
it loads its widget from a public CDN. n8n itself only listens on 127.0.0.1.
"""
import json
import sys


def node(n, name, type_, pos, params, version=1, **extra):
    return {"parameters": params, "id": f"d1000000-0000-4000-8000-00000000000{n}", "name": name,
            "type": type_, "typeVersion": version, "position": pos, **extra}


# Plain n8n expression (no arrow functions): answer, then one line per source.
REPLY = ("={{ $json.answer ? $json.answer + '\\n\\n' + ($json.sources || []).map(function (s) { return 'Quelle: ' + "
         "s.doc + ' > ' + s.section + ' (verantwortlich: ' + s.owner + ', Stand ' + s.date + ')'; }).join('\\n') "
         ": 'Der Handbuch-Assistent ist gerade nicht erreichbar. Bitte später noch einmal versuchen.' }}")

nodes = [
    node(1, "Chat: Frage eines Partners", "@n8n/n8n-nodes-langchain.chatTrigger", [0, 300],
         {"public": True, "mode": "webhook", "authentication": "none",
          "options": {"responseMode": "lastNode"}}, 1.1,
         webhookId="d1000000-0000-4000-8000-0000000000aa"),
    node(2, "Handbuch-API fragen (lokal)", "n8n-nodes-base.httpRequest", [260, 300],
         {"method": "POST", "url": "http://host.docker.internal:8002/frage", "sendBody": True,
          "bodyParameters": {"parameters": [{"name": "frage", "value": "={{ $json.chatInput }}"}]},
          "options": {"timeout": 120000}}, 4.2, onError="continueRegularOutput"),
    node(3, "Antwort + Quellen für den Chat", "n8n-nodes-base.set", [520, 300],
         {"assignments": {"assignments": [{"id": "d1-output", "name": "output", "value": REPLY, "type": "string"}]},
          "options": {}}, 3.4),
]
connections = {
    "Chat: Frage eines Partners": {"main": [[{"node": "Handbuch-API fragen (lokal)", "type": "main", "index": 0}]]},
    "Handbuch-API fragen (lokal)": {"main": [[{"node": "Antwort + Quellen für den Chat", "type": "main", "index": 0}]]},
}
wf = {"id": "HomecareHandbookD", "name": "HOMECARE D - Ask the partner handbook (chat -> local API)",
      "nodes": nodes, "connections": connections, "active": False, "settings": {"executionOrder": "v1"},
      "pinData": {}, "tags": []}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)
print("wrote", sys.argv[1])
