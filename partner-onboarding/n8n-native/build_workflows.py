"""Build the n8n-only version of the onboarding cockpit: 5 workflows + 1 local Ollama credential.

The logic lives in code/*.js (tested against the Python version with test/compare_*.py) and is pasted
into n8n Code nodes here, so the repo has one readable source and n8n gets plain workflows.

Usage: python n8n-native/build_workflows.py <out_dir> [telegram_chat_id] [telegram_credential_id]
Without a chat ID the Telegram node keeps the placeholder YOUR_TELEGRAM_CHAT_ID (this is the repo copy).
"""
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "data"))
from app.checklist import TASKS  # noqa: E402
from app.updates import SYSTEM as JUDGE_PROMPT  # noqa: E402
from generate_data import PARTNERS  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "workflows"
CHAT_ID = sys.argv[2] if len(sys.argv) > 2 else "YOUR_TELEGRAM_CHAT_ID"
TG_CRED = sys.argv[3] if len(sys.argv) > 3 else "YOUR_CREDENTIAL_ID"
OLLAMA_CRED = {"id": "HCollamaLokal001", "name": "Ollama lokal (qwen2.5:3b)"}
MODEL = "qwen2.5:3b"
IDS = {"setup": "HCob1Einrichtung", "update": "HCob2PartnerUpd0", "ampel": "HCob3AmpelRegeln",
       "bericht": "HCob4MorgenBerch", "seite": "HCob5CockpitSeit"}
CORE = {name: (HERE / "code" / f"{name}_core.js").read_text(encoding="utf-8") for name in ("rules", "status", "seed", "page")}

# --- data tables -----------------------------------------------------------------------------------------
TABLES = {
    "ob_checkliste": {"nr": "number", "aufgabe": "string", "phase": "number", "titel": "string",
                      "faellig_tag": "number", "zustaendig": "string", "vor_erstem_kunden": "boolean",
                      "stichwoerter": "string"},
    "ob_partner": {"partner_id": "number", "name": "string", "stadt": "string", "start": "string",
                   "betreuer": "string", "aktive_kunden": "number"},
    "ob_aufgaben": {"partner_id": "number", "aufgabe": "string", "status": "string", "erledigt_am": "string",
                    "notiz": "string"},
    "ob_vorschlaege": {"partner_id": "number", "stadt": "string", "eingegangen": "string", "nachricht": "string",
                       "aenderungen": "string", "keine_aenderung": "string", "warnungen": "string",
                       "kunden": "string", "status": "string", "entschieden_von": "string",
                       "entschieden_am": "string", "freigabe_url": "string"},
    "ob_protokoll": {"zeit": "string", "partner_id": "number", "stadt": "string", "wer": "string",
                     "aktion": "string", "details": "string"},
    "ob_testfaelle": {"testset": "string", "nachricht": "string", "erwartet": "string",
                      "kunden_erwartet": "string"},
}


def uid(seed):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "homecare-onboarding-n8n/" + seed))


def table(name):
    return {"__rl": True, "mode": "name", "value": name}


def mapping(name, values):
    """resourceMapper for insert/update: explicit columns, so extra fields on the item are ignored."""
    return {"mappingMode": "defineBelow", "value": values, "matchingColumns": [],
            "schema": [{"id": c, "displayName": c, "required": False, "defaultMatch": False, "display": True,
                        "type": TABLES[name][c], "canBeUsedToMatch": True, "readOnly": False, "removed": False}
                       for c in values],
            "attemptToConvertTypes": False, "convertFieldsToString": False}


def filters(*conds):
    return {"conditions": [{"keyName": k, "condition": "eq", "keyValue": v} for k, v in conds]}


class Flow:
    def __init__(self, key, name):
        self.key, self.name, self.nodes, self.conn = key, name, [], {}

    def add(self, name, type_, version, pos, params, **extra):
        node = {"parameters": params, "id": uid(f"{self.key}/{name}"), "name": name, "type": type_,
                "typeVersion": version, "position": pos, **extra}
        self.nodes.append(node)
        return name

    def base(self, name, short, version, pos, params, **extra):
        return self.add(name, f"n8n-nodes-base.{short}", version, pos, params, **extra)

    def code(self, name, pos, js, each=False, **extra):
        params = {"jsCode": js.strip() + "\n"}
        if each:
            params["mode"] = "runOnceForEachItem"
        return self.base(name, "code", 2, pos, params, **extra)

    def dt(self, name, pos, params, **extra):
        return self.base(name, "dataTable", 1.1, pos, params, **extra)

    def note(self, text, pos, w=360, h=200, color=7):
        n = sum(1 for x in self.nodes if x["type"].endswith("stickyNote")) + 1
        self.base(f"Notiz {n}", "stickyNote", 1, pos, {"content": text, "width": w, "height": h, "color": color})

    def link(self, a, b, out=0, kind="main"):
        outs = self.conn.setdefault(a, {}).setdefault(kind, [])
        while len(outs) <= out:
            outs.append([])
        outs[out].append({"node": b, "type": kind, "index": 0})

    def chain(self, *names):
        for a, b in zip(names, names[1:]):
            self.link(a, b)

    def write(self, extra_settings=None):
        wf = {"id": IDS[self.key], "name": self.name, "nodes": self.nodes, "connections": self.conn,
              "settings": {"executionOrder": "v1", **(extra_settings or {})}, "pinData": {}, "active": False,
              "meta": {"templateCredsSetupCompleted": True}, "tags": []}
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{self.key}.json").write_text(json.dumps(wf, ensure_ascii=False, indent=1), encoding="utf-8")


def respond_json(flow, name, pos, body_expr, code=200):
    return flow.base(name, "respondToWebhook", 1.1, pos,
                     {"respondWith": "json", "responseBody": "={{ JSON.stringify(" + body_expr + ") }}",
                      "options": {"responseCode": code}})


ONCE = {"executeOnce": True}
ALWAYS = {"alwaysOutputData": True}

# --- F1: setup -------------------------------------------------------------------------------------------
f = Flow("setup", "HOMECARE F1 · Onboarding (n8n): Einrichtung + Demo-Daten")
f.note("## Einrichtung (einmal, und vor jeder Demo)\nLegt die 6 Data Tables an, leert sie und füllt sie neu:\n"
       "Checkliste (15 Punkte aus dem Handbuch), 8 erfundene Partner, ihre Aufgaben, 50 Testfälle.\n"
       "Die Partner-Tage zählen ab heute, deshalb vor einer Demo neu ausführen.", [-40, -260], 620, 180, 5)
prev = f.base("Start", "manualTrigger", 1, [0, 0], {})
# The data-table module only runs inside the n8n server, so the setup can also be started by a webhook:
# Invoke-RestMethod -Method Post http://localhost:5678/webhook/onboarding-einrichtung
hook = f.base("Start per Webhook", "webhook", 2, [0, 200],
              {"httpMethod": "POST", "path": "onboarding-einrichtung", "responseMode": "lastNode", "options": {}},
              webhookId=uid("webhook-setup"))
f.link(hook, "Tabelle ob_checkliste")
x = 220
for name, cols in TABLES.items():
    c = f.dt(f"Tabelle {name}", [x, 0], {"resource": "table", "operation": "create", "tableName": name,
                                         "columns": {"column": [{"name": k, "type": t} for k, t in cols.items()]},
                                         "options": {"createIfNotExists": True}})
    d = f.dt(f"Leeren {name}", [x, 200], {"resource": "table", "operation": "clear", "dataTableId": table(name)})
    f.chain(prev, c, d)
    prev, x = d, x + 220

checklist_rows = [{"nr": i + 1, "aufgabe": t.id, "phase": t.phase, "titel": t.title, "faellig_tag": t.due_day,
                   "zustaendig": t.owner, "vor_erstem_kunden": t.gate, "stichwoerter": ", ".join(t.words)}
                  for i, t in enumerate(TASKS)]
partners = [[n, c, d, k, {t: list(v) for t, v in s.items()}] for n, c, d, k, s in PARTNERS]
cases = json.loads((HERE.parent / "eval" / "updates.json").read_text(encoding="utf-8"))
test_rows = [{"testset": k, "nachricht": c["msg"], "erwartet": json.dumps(c["changes"], ensure_ascii=False),
              "kunden_erwartet": "" if c.get("active_customers") is None else str(c["active_customers"])}
             for k, v in cases.items() if not k.startswith("_") for c in v]

steps = [
    ("Checkliste (aus dem Handbuch)", "ob_checkliste", f"return {json.dumps(checklist_rows, ensure_ascii=False)}.map(json => ({{json}}));"),
    ("Partner und Aufgaben erzeugen", "ob_partner", CORE["seed"] + f"""
const checklist = $('Checkliste (aus dem Handbuch)').all().map(i => ({{id: i.json.aufgabe, due_day: i.json.faellig_tag}}));
const today = $now.setZone('Europe/Berlin').toISODate();
const s = seedRows({json.dumps(partners, ensure_ascii=False)}, checklist, today);
return s.partnerRows.map(json => ({{json}}));"""),
    ("Aufgaben je Partner", "ob_aufgaben", CORE["seed"] + f"""
const checklist = $('Checkliste (aus dem Handbuch)').all().map(i => ({{id: i.json.aufgabe, due_day: i.json.faellig_tag}}));
const today = $now.setZone('Europe/Berlin').toISODate();
return seedRows({json.dumps(partners, ensure_ascii=False)}, checklist, today).taskRows.map(json => ({{json}}));"""),
    ("Testfälle (50 Nachrichten)", "ob_testfaelle", f"return {json.dumps(test_rows, ensure_ascii=False)}.map(json => ({{json}}));"),
    ("Protokoll: angelegt", "ob_protokoll", """
const now = $now.toISO();
return $('Partner und Aufgaben erzeugen').all().map(p => ({json: {zeit: now, partner_id: p.json.partner_id,
  stadt: p.json.stadt, wer: 'System', aktion: 'Partner angelegt', details: 'Start ' + p.json.start}}));"""),
]
x = 220
for title, tname, js in steps:
    c = f.code(title, [x, 420], js)
    i = f.dt(f"Speichern in {tname}", [x + 110, 600], {
        "resource": "row", "operation": "insert", "dataTableId": table(tname),
        "columns": mapping(tname, {k: "={{ $json." + k + " }}" for k in TABLES[tname]}), "options": {}})
    f.chain(prev, c, i)
    prev, x = i, x + 300
f.write()

# --- F2: partner update -> proposal -> approval ----------------------------------------------------------
f = Flow("update", "HOMECARE F2 · Onboarding (n8n): Partner-Update → Vorschlag → Freigabe")
f.note("## 1. Eingang\nE-Mail oder Formular des Partners kommt per Webhook. Der zweite Start ist der **Test**: "
       "n8n Evaluations schickt die 50 Testnachrichten durch denselben Ablauf.", [-500, -300], 420, 200, 7)
f.note("## 2. Regeln zuerst (Code, keine KI)\nNachricht in Satzteile zerlegen, Checklisten-Punkte über Stichwörter finden.\n"
       "Klare Wörter entscheiden: *leider/fehlt* → blockiert, *noch nicht/?* → keine Änderung, *abgeschlossen/liegt vor* → erledigt.\n"
       "Nur unklare Satzteile in der Vergangenheit gehen an die KI.", [160, -360], 520, 220, 4)
f.note("## 3. KI nur für Unklares\nEine kleine Frage je Satzteil: *Ist dieser Punkt erledigt?* Lokales Modell (Ollama), "
       "Antwort in festem Format: Begründung, dann ja/nein.", [740, -360], 460, 180, 3)
f.note("## 4. Vorschlag, keine Änderung\nAbgleich mit der Checkliste, Warnung bei Kunden ohne Versicherung/Zulassung. "
       "Gespeichert als Vorschlag, Antwort an den Absender.", [1640, -10], 520, 160, 6)
f.note("## 5. Mensch entscheidet\nDer Ablauf **wartet**, bis jemand im Formular freigibt (mit Namen). "
       "Erst dann ändern sich Checkliste und Kundenzahl. Jede Änderung steht im Protokoll.", [2980, -10], 520, 160, 4)

wh = f.base("Partner-Update (Webhook)", "webhook", 2, [-480, 0],
            {"httpMethod": "POST", "path": "onboarding-update", "responseMode": "responseNode", "options": {}},
            webhookId=uid("webhook-update"))
ev = f.base("Testfälle (n8n Evaluations)", "evaluationTrigger", 4.7, [-480, 220],
            {"source": "dataTable", "dataTableId": table("ob_testfaelle"), "limitRows": False})
prep = f.code("Eingang vorbereiten", [-240, 100], """
const j = $json;
const now = $now.toISO();
if (j.body) {  // webhook: {partner_id, nachricht, nur_testen?}
  return {json: {partner_id: Number(j.body.partner_id), nachricht: String(j.body.nachricht || '').trim(),
    nur_testen: j.body.nur_testen === true, eingegangen: now}};
}
// evaluation: one test case from ob_testfaelle
return {json: {partner_id: 0, nachricht: j.nachricht, erwartet: j.erwartet, kunden_erwartet: j.kunden_erwartet,
  testset: j.testset, nur_testen: true, eingegangen: now}};
""", each=True)
f.link(wh, prep)
f.link(ev, prep)
cl = f.dt("Checkliste laden", [0, 100], {"resource": "row", "operation": "get", "dataTableId": table("ob_checkliste"),
                                          "returnAll": True}, **ONCE)
rules = f.code("Regeln: Satzteile und Punkte", [240, 100], CORE["rules"] + """
const input = $('Eingang vorbereiten').first().json;
const checklist = checklistFromRows($input.all().map(i => i.json));
const r = ruleEvents(input.nachricht, checklist);
const state = {events: r.events};
if (!r.questions.length) return [{json: {ki_noetig: false, state}}];
return r.questions.map((q, i) => ({json: {ki_noetig: true, frage_nr: i, satz: q.satz, aufgabe: q.task, titel: q.titel,
  state: i === 0 ? state : null}}));
""")
need = f.base("KI nötig?", "if", 2.2, [480, 100], {"conditions": {
    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
    "conditions": [{"id": uid("if-ki"), "leftValue": "={{ $json.ki_noetig }}", "rightValue": "",
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
    "combinator": "and"}, "options": {}})
f.chain(prep, cl, rules, need)
judge = f.add("KI: Ist der Punkt erledigt?", "@n8n/n8n-nodes-langchain.chainLlm", 1.9, [760, 0], {
    "promptType": "define", "text": "=Checklisten-Punkt: {{ $json.titel }}\nSatzteil des Partners: {{ $json.satz }}",
    "hasOutputParser": True,
    "messages": {"messageValues": [{"type": "SystemMessagePromptTemplate", "message": JUDGE_PROMPT}]}},
    onError="continueRegularOutput")
llm = f.add("Ollama (lokal)", "@n8n/n8n-nodes-langchain.lmChatOllama", 1, [700, 220],
            {"model": MODEL, "options": {"temperature": 0, "numPredict": 200, "format": "json", "think": False}},
            credentials={"ollamaApi": OLLAMA_CRED})
parser = f.add("Antwortformat: Begründung + ja/nein", "@n8n/n8n-nodes-langchain.outputParserStructured", 1.3,
               [880, 220], {"schemaType": "manual", "inputSchema": json.dumps({
                   "type": "object", "properties": {"begruendung": {"type": "string", "description": "ein kurzer Halbsatz"},
                                                    "erledigt": {"type": "boolean"}},
                   "required": ["begruendung", "erledigt"]}, ensure_ascii=False, indent=1)})
f.link(need, judge, 0)
f.link(llm, judge, kind="ai_languageModel")
f.link(parser, judge, kind="ai_outputParser")
build = f.code("Vorschlag zusammensetzen", [1100, 100], CORE["rules"] + """
const input = $('Eingang vorbereiten').first().json;
const first = $('Regeln: Satzteile und Punkte').first().json;
let answers = [];
if (first.ki_noetig) {
  answers = $input.all().map(it => {
    const o = it.json.output;
    return o && typeof o.erledigt === 'boolean'
      ? {begruendung: String(o.begruendung || '').trim(), erledigt: o.erledigt}
      : {begruendung: 'ungültige Modellantwort', erledigt: false};
  });
}
const received = $now.setZone('Europe/Berlin').toISODate();
const p = buildProposal(input.nachricht, first.state.events, answers, received);
return [{json: {...input, ...p, ki_fragen: answers.length}}];
""")
f.link(judge, build)
f.link(need, build, 1)
check_eval = f.base("Test oder echt?", "evaluation", 4.8, [1340, 100], {"operation": "checkIfEvaluating"})
f.link(build, check_eval)

# evaluation branch
cmp_ = f.code("Mit Erwartung vergleichen", [1600, -160], """
const j = $json;
const got = Object.fromEntries(j.changes.map(c => [c.task, c.status]));
const exp = JSON.parse(j.erwartet || '{}');
const expCustomers = j.kunden_erwartet === '' || j.kunden_erwartet == null ? null : Number(j.kunden_erwartet);
const sorted = o => JSON.stringify(Object.keys(o).sort().map(k => [k, o[k]]));
const correct = sorted(got) === sorted(exp) && j.active_customers === expCustomers;
const wrongDone = Object.keys(got).filter(k => got[k] === 'erledigt' && exp[k] !== 'erledigt');
const fmt = o => Object.entries(o).map(([k, v]) => k + '=' + v).join(', ') || 'keine';
return {json: {korrekt: correct ? 1 : 0, falsch_erledigt: wrongDone.length, testset: j.testset,
  vorgeschlagen: fmt(got) + (j.active_customers != null ? ` (Kunden ${j.active_customers})` : ''),
  erwartet: fmt(exp) + (expCustomers != null ? ` (Kunden ${expCustomers})` : '')}};
""", each=True)
metrics = f.base("Kennzahlen für den Test", "evaluation", 4.8, [1840, -160], {
    "operation": "setMetrics", "metric": "customMetrics", "metrics": {"assignments": [
        {"id": uid("m1"), "name": "korrekt", "value": "={{ $json.korrekt }}", "type": "number"},
        {"id": uid("m2"), "name": "falsch_erledigt", "value": "={{ $json.falsch_erledigt }}", "type": "number"}]}})
f.link(check_eval, cmp_, 0)
f.link(cmp_, metrics)

# normal branch
only = f.base("Nur testen?", "if", 2.2, [1600, 160], {"conditions": {
    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
    "conditions": [{"id": uid("if-test"), "leftValue": "={{ $json.nur_testen }}", "rightValue": "",
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
    "combinator": "and"}, "options": {}})
f.link(check_eval, only, 1)
respond_json(f, "Antwort: nur Vorschlag (nichts gespeichert)", [1840, 40],
             "{ ok: true, nur_test: true, aenderungen: $json.changes, keine_aenderung: $json.notes, kunden: $json.active_customers }")
f.link(only, "Antwort: nur Vorschlag (nichts gespeichert)", 0)
pid = "{{ $('Vorschlag zusammensetzen').first().json.partner_id }}"
lp = f.dt("Partner laden", [1840, 260], {"resource": "row", "operation": "get", "dataTableId": table("ob_partner"),
                                         "matchType": "allConditions", "filters": filters(("partner_id", "=" + pid)),
                                         "returnAll": True}, **ONCE, **ALWAYS)
la = f.dt("Aufgaben des Partners laden", [2060, 260], {"resource": "row", "operation": "get",
                                                        "dataTableId": table("ob_aufgaben"), "matchType": "allConditions",
                                                        "filters": filters(("partner_id", "=" + pid)), "returnAll": True},
          **ONCE, **ALWAYS)
f.link(only, lp, 1)
f.link(lp, la)
match = f.code("Mit Checkliste abgleichen", [2280, 260], CORE["rules"] + """
const p = $('Vorschlag zusammensetzen').first().json;
const partner = $('Partner laden').all().map(i => i.json).find(r => r.partner_id === p.partner_id);
if (!partner) return [{json: {ok: false, fehler: `Partner ${p.partner_id} unbekannt`}}];
const checklist = checklistFromRows($('Checkliste laden').all().map(i => i.json));
const title = Object.fromEntries(checklist.map(t => [t.id, t.title]));
const tasks = Object.fromEntries($('Aufgaben des Partners laden').all().map(i => [i.json.aufgabe, i.json]));
const changes = [], skipped = [];
for (const c of p.changes) {
  if (tasks[c.task].status === c.status) skipped.push({...c, tasks: [c.task], grund: 'steht schon so in der Checkliste'});
  else changes.push({...c, titel: title[c.task], vorher: tasks[c.task].status});
}
// Customers reported while a must-have (insurance, permit, background check, templates) is still open.
const after = Object.fromEntries(Object.entries(tasks).map(([k, v]) => [k, v.status]));
for (const c of changes) after[c.task] = c.status;
const warnings = [];
if (after.erster_kunde === 'erledigt') {
  const missing = checklist.filter(t => t.gate && after[t.id] !== 'erledigt').map(t => t.title);
  if (missing.length) warnings.push('Partner meldet Kundeneinsätze, aber laut Checkliste fehlt noch: ' + missing.join(', ') +
    '. Bitte sofort klären, bevor weitere Einsätze stattfinden.');
}
const lines = changes.map(c => `• ${c.titel}: ${c.vorher} → ${c.status}  (Beleg: „${c.satz}“, ${c.entschieden_von})`);
const desc = `Nachricht: „${p.nachricht}“\\n\\nVorgeschlagene Änderungen:\\n` + (lines.join('\\n') || '• keine') +
  (p.active_customers != null ? `\\n• Aktive Kunden: ${partner.aktive_kunden} → ${p.active_customers}` : '') +
  (warnings.length ? '\\n\\n⚠️ ' + warnings.join(' ') : '');
return [{json: {ok: true, partner_id: p.partner_id, stadt: partner.stadt, eingegangen: p.eingegangen, nachricht: p.nachricht,
  aenderungen: JSON.stringify(changes), keine_aenderung: JSON.stringify([...p.notes, ...skipped]),
  warnungen: JSON.stringify(warnings), kunden: p.active_customers == null ? '' : String(p.active_customers),
  status: 'offen', entschieden_von: '', entschieden_am: '', freigabe_url: $execution.resumeFormUrl,
  beschreibung: desc, kunden_vorher: partner.aktive_kunden, changes, warnings}}];
""")
f.link(la, match)
found = f.base("Partner bekannt?", "if", 2.2, [2500, 260], {"conditions": {
    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
    "conditions": [{"id": uid("if-ok"), "leftValue": "={{ $json.ok }}", "rightValue": "",
                    "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
    "combinator": "and"}, "options": {}})
f.link(match, found)
respond_json(f, "Antwort: Partner unbekannt", [2720, 460], "{ ok: false, fehler: $json.fehler }", 404)
f.link(found, "Antwort: Partner unbekannt", 1)
cols = [c for c in TABLES["ob_vorschlaege"]]
save = f.dt("Vorschlag speichern", [2720, 200], {"resource": "row", "operation": "insert",
                                                  "dataTableId": table("ob_vorschlaege"),
                                                  "columns": mapping("ob_vorschlaege", {c: "={{ $json." + c + " }}" for c in cols}),
                                                  "options": {}})
f.link(found, save, 0)
M = "$('Mit Checkliste abgleichen').first().json"
log1 = f.dt("Protokoll: Update eingegangen", [2940, 200], {
    "resource": "row", "operation": "insert", "dataTableId": table("ob_protokoll"),
    "columns": mapping("ob_protokoll", {
        "zeit": "={{ $now.toISO() }}", "partner_id": "={{ " + M + ".partner_id }}", "stadt": "={{ " + M + ".stadt }}",
        "wer": "E-Mail des Partners", "aktion": "Update eingegangen",
        "details": "={{ 'Vorschlag #' + $('Vorschlag speichern').first().json.id + ': ' + " + M + ".changes.length + ' Änderung(en), ' + " + M + ".warnings.length + ' Warnung(en)' }}"}),
    "options": {}})
f.link(save, log1)
ans = respond_json(f, "Antwort: Vorschlag gespeichert", [3160, 200],
                   "{ ok: true, vorschlag_nr: $('Vorschlag speichern').first().json.id, stadt: " + M + ".stadt, "
                   "aenderungen: " + M + ".changes, warnungen: " + M + ".warnings, kunden: " + M + ".kunden, "
                   "hinweis: 'Noch nichts geändert. Freigabe über freigabe_url.', freigabe_url: " + M + ".freigabe_url }")
f.link(log1, ans)
wait = f.base("Warten auf Freigabe (Formular)", "wait", 1.1, [3380, 200], {
    "resume": "form", "formTitle": "={{ 'Partner-Update ' + " + M + ".stadt + ' prüfen' }}",
    "formDescription": "={{ " + M + ".beschreibung }}",
    "formFields": {"values": [
        {"fieldLabel": "Ihr Name", "placeholder": "z. B. Frau Becker", "requiredField": True},
        {"fieldLabel": "Entscheidung", "fieldType": "dropdown", "requiredField": True,
         "fieldOptions": {"values": [{"option": "Alle Änderungen übernehmen"}, {"option": "Ablehnen"}]}}]},
    "responseMode": "onReceived",
    "options": {"respondWithOptions": {"values": {"respondWith": "text",
                                                  "formSubmittedText": "Gespeichert. Die Entscheidung steht im Protokoll."}}}},
    webhookId=uid("wait-form"))
f.link(ans, wait)
decide = f.code("Entscheidung auswerten", [3600, 200], """
const form = $json;
const m = $('Mit Checkliste abgleichen').first().json;
const nr = $('Vorschlag speichern').first().json.id;
const by = String(form['Ihr Name'] || '').trim() || 'unbekannt';
const approve = form['Entscheidung'] === 'Alle Änderungen übernehmen';
const now = $now.toISO();
const row = (aktion, details) => ({json: {zeit: now, partner_id: m.partner_id, stadt: m.stadt, wer: by, aktion, details,
  _approve: approve, _by: by, _now: now}});
const rows = [];
if (approve) {
  for (const c of m.changes) rows.push(row('Checkliste geändert', `${c.titel}: ${c.vorher} → ${c.status}. Beleg: „${c.satz}“ (${c.entschieden_von}). Vorschlag #${nr}`));
  if (m.kunden !== '') rows.push(row('Kundenzahl geändert', `${m.kunden_vorher} → ${m.kunden}. Vorschlag #${nr}`));
}
rows.push(row(approve ? 'Vorschlag freigegeben' : 'Vorschlag abgelehnt', `Vorschlag #${nr}`));
return rows;
""")
f.link(wait, decide)
log2 = f.dt("Protokoll schreiben", [3820, 200], {"resource": "row", "operation": "insert",
                                                  "dataTableId": table("ob_protokoll"),
                                                  "columns": mapping("ob_protokoll", {c: "={{ $json." + c + " }}" for c in TABLES["ob_protokoll"]}),
                                                  "options": {}})
D = "$('Entscheidung auswerten').first().json"
st = f.dt("Vorschlag: Status setzen", [4040, 200], {
    "resource": "row", "operation": "update", "dataTableId": table("ob_vorschlaege"), "matchType": "allConditions",
    "filters": filters(("id", "={{ $('Vorschlag speichern').first().json.id }}")),
    "columns": mapping("ob_vorschlaege", {"status": "={{ " + D + "._approve ? 'freigegeben' : 'abgelehnt' }}",
                                          "entschieden_von": "={{ " + D + "._by }}",
                                          "entschieden_am": "={{ " + D + "._now }}"}), "options": {}}, **ONCE)
pc = f.dt("Partner: Kundenzahl", [4260, 200], {
    "resource": "row", "operation": "update", "dataTableId": table("ob_partner"), "matchType": "allConditions",
    "filters": filters(("partner_id", "={{ " + M + ".partner_id }}")),
    "columns": mapping("ob_partner", {"aktive_kunden": "={{ " + D + "._approve && " + M + ".kunden !== '' ? Number(" + M + ".kunden) : " + M + ".kunden_vorher }}"}),
    "options": {}}, **ONCE)
items = f.code("Checklisten-Änderungen", [4480, 200], """
if (!$('Entscheidung auswerten').first().json._approve) return [];
const m = $('Mit Checkliste abgleichen').first().json;
return m.changes.map(c => ({json: {partner_id: m.partner_id, aufgabe: c.task, status: c.status,
  erledigt_am: c.done_on || '', notiz: c.satz.slice(0, 200)}}));
""")
upd = f.dt("Checkliste aktualisieren", [4700, 200], {
    "resource": "row", "operation": "update", "dataTableId": table("ob_aufgaben"), "matchType": "allConditions",
    "filters": filters(("partner_id", "={{ $json.partner_id }}"), ("aufgabe", "={{ $json.aufgabe }}")),
    "columns": mapping("ob_aufgaben", {"status": "={{ $json.status }}", "erledigt_am": "={{ $json.erledigt_am }}",
                                       "notiz": "={{ $json.notiz }}"}), "options": {}})
f.chain(decide, log2, st, pc, items, upd)
f.write()

# --- F3: traffic light (sub-workflow) --------------------------------------------------------------------
f = Flow("ampel", "HOMECARE F3 · Onboarding (n8n): Ampel berechnen (Unter-Workflow)")
f.note("## Ampel: nur Regeln, keine KI\nWird vom Morgen-Bericht und von der Cockpit-Seite aufgerufen.\n"
       "🔴 Kunden ohne Versicherung/Zulassung, Pflichtpunkt blockiert oder überfällig, Zulassung erst nach Tag 90.\n"
       "🟠 normaler Punkt überfällig/blockiert, Zulassung spät, Kundenziel unrealistisch.", [-40, -260], 640, 200, 4)
t = f.base("Aufruf von anderem Workflow", "executeWorkflowTrigger", 1.1, [0, 0], {"inputSource": "passthrough"})
a = f.dt("Checkliste", [220, 0], {"resource": "row", "operation": "get", "dataTableId": table("ob_checkliste"),
                                  "returnAll": True}, **ONCE)
b = f.dt("Partner", [440, 0], {"resource": "row", "operation": "get", "dataTableId": table("ob_partner"),
                               "returnAll": True}, **ONCE)
c = f.dt("Aufgaben", [660, 0], {"resource": "row", "operation": "get", "dataTableId": table("ob_aufgaben"),
                                "returnAll": True}, **ONCE)
d = f.dt("Offene Vorschläge", [880, 0], {"resource": "row", "operation": "get", "dataTableId": table("ob_vorschlaege"),
                                         "matchType": "allConditions", "filters": filters(("status", "offen")),
                                         "returnAll": True}, **ONCE, **ALWAYS)
e = f.code("Ampel-Regeln", [1100, 0], CORE["rules"] + CORE["status"] + """
const today = $now.setZone('Europe/Berlin').toISODate();
const checklist = checklistFromRows($('Checkliste').all().map(i => i.json));
const taskRows = $('Aufgaben').all().map(i => i.json);
const open = $('Offene Vorschläge').all().map(i => i.json).filter(v => v.id).sort((x, y) => y.id - x.id);
const partners = $('Partner').all().map(i => i.json).sort((x, y) => x.start.localeCompare(y.start)).map(p => {
  const tasks = Object.fromEntries(taskRows.filter(r => r.partner_id === p.partner_id)
    .map(r => [r.aufgabe, {status: r.status, done_on: r.erledigt_am || null, note: r.notiz || ''}]));
  const a = assess({start_date: p.start, active_customers: p.aktive_kunden}, tasks, checklist, today);
  return {...p, city: p.stadt, ...a};
});
const risks = risksText(partners, open.length);
return [{json: {today, partners, offene_vorschlaege: open, telegram_text: risks.text, auffaellig: risks.count}}];
""")
f.chain(t, a, b, c, d, e)
f.write({"callerPolicy": "workflowsFromSameOwner"})


def call_ampel(flow, pos):
    return flow.base("Ampel berechnen (F3)", "executeWorkflow", 1.2, pos, {
        "workflowId": {"__rl": True, "value": IDS["ampel"], "mode": "id"},
        "workflowInputs": {"mappingMode": "defineBelow", "value": {}, "matchingColumns": [], "schema": [],
                           "attemptToConvertTypes": False, "convertFieldsToString": True},
        "options": {}})


# --- F4: morning report ----------------------------------------------------------------------------------
f = Flow("bericht", "HOMECARE F4 · Onboarding (n8n): Morgen-Bericht (Telegram)")
f.note("## Morgen-Bericht\nMo-Fr 08:30 (oder jetzt per Hand): Ampel berechnen, rote und orange Partner per Telegram "
       "an das Partnermanagement. Nur Stadt, Tag und Befund, keine Namen.", [-40, -240], 560, 180, 7)
s1 = f.base("Mo-Fr 08:30", "scheduleTrigger", 1.2, [0, 0],
            {"rule": {"interval": [{"field": "cronExpression", "expression": "30 8 * * 1-5"}]}})
s2 = f.base("Jetzt senden", "manualTrigger", 1, [0, 200], {})
amp = call_ampel(f, [240, 100])
tg = f.base("Telegram an Partnermanagement", "telegram", 1.2, [480, 100],
            {"chatId": CHAT_ID, "text": "={{ $json.telegram_text }}", "additionalFields": {"appendAttribution": False}},
            webhookId=uid("tg"), credentials={"telegramApi": {"id": TG_CRED, "name": "HOMECARE Telegram bot"}})
f.link(s1, amp)
f.link(s2, amp)
f.link(amp, tg)
f.write()

# --- F5: cockpit web page --------------------------------------------------------------------------------
f = Flow("seite", "HOMECARE F5 · Onboarding (n8n): Cockpit-Webseite")
f.note("## Cockpit-Seite, von n8n ausgeliefert\nhttp://localhost:5678/webhook/onboarding-cockpit\n"
       "Ampel je Partner, offene Vorschläge mit Freigabe-Link, Formular für neue Updates, Protokoll.",
       [-40, -240], 560, 180, 7)
w = f.base("Seite aufrufen (Webhook)", "webhook", 2, [0, 0],
           {"httpMethod": "GET", "path": "onboarding-cockpit", "responseMode": "responseNode", "options": {}},
           webhookId=uid("webhook-page"))
amp = call_ampel(f, [220, 0])
pr = f.dt("Protokoll (letzte 25)", [440, 0], {"resource": "row", "operation": "get", "dataTableId": table("ob_protokoll"),
                                              "returnAll": False, "limit": 25, "orderBy": True,
                                              "orderByColumn": "createdAt", "orderByDirection": "DESC"}, **ONCE, **ALWAYS)
pg = f.code("Seite bauen", [660, 0], CORE["page"] + """
const a = $('Ampel berechnen (F3)').first().json;
const audit = $('Protokoll (letzte 25)').all().map(i => i.json).filter(r => r.id);
return [{json: {html: buildPage({partners: a.partners, open: a.offene_vorschlaege, audit, today: a.today})}}];
""")
rp = f.base("Seite ausliefern", "respondToWebhook", 1.1, [880, 0], {
    "respondWith": "text", "responseBody": "={{ $json.html }}",
    "options": {"responseHeaders": {"entries": [{"name": "Content-Type", "value": "text/html; charset=utf-8"}]}}})
f.chain(w, amp, pr, pg, rp)
f.write()

# --- credential (no secret: the local Ollama needs no key) ---------------------------------------------------
(OUT / "ollama_credential.json").write_text(json.dumps([{**OLLAMA_CRED, "type": "ollamaApi",
                                                         "data": {"baseUrl": "http://host.docker.internal:11434"}}],
                                                       indent=1), encoding="utf-8")
print(f"wrote 5 workflows + credential to {OUT}")
