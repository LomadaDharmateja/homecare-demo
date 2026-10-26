// The cockpit web page, served by n8n itself (Webhook -> Code -> Respond to Webhook). No separate app.
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function buildPage({ partners, open, audit, today }) {
  const dot = { 'im Plan': 'ok', Achtung: 'warn', kritisch: 'crit' };
  const word = { 'im Plan': '🟢 im Plan', Achtung: '🟠 Achtung', kritisch: '🔴 kritisch' };
  const count = l => partners.filter(p => p.level === l).length;
  const de = iso => (iso ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}` : '');
  const time = iso => (iso ? new Date(iso).toLocaleString('de-DE', { timeZone: 'Europe/Berlin', dateStyle: 'short', timeStyle: 'short' }) : '');

  const partnerRows = partners.map(p => `
    <tr class="${dot[p.level]}">
      <td><b>${esc(p.stadt)}</b><div class="muted">${esc(p.name)} · ${esc(p.betreuer)}</div></td>
      <td>Tag ${p.day}<div class="bar"><span style="width:${Math.min(100, Math.round(p.day / 90 * 100))}%"></span></div></td>
      <td>${p.done}/${p.total}</td>
      <td>${p.aktive_kunden}</td>
      <td class="lvl">${word[p.level]}</td>
      <td>${p.findings.length ? '<ul>' + p.findings.map(f => `<li class="${dot[f.level]}">${esc(f.text)}</li>`).join('') + '</ul>' : '<span class="muted">keine Hinweise</span>'}</td>
    </tr>`).join('');

  const openCards = open.length ? open.map(v => {
    const changes = JSON.parse(v.aenderungen || '[]');
    const warnings = JSON.parse(v.warnungen || '[]');
    return `<div class="card">
      <div class="row"><b>#${v.id} · ${esc(v.stadt)}</b><span class="muted">${time(v.eingegangen)}</span></div>
      <p class="msg">„${esc(v.nachricht)}“</p>
      ${changes.length ? '<ul>' + changes.map(c => `<li><b>${esc(c.titel)}</b>: ${esc(c.vorher)} → <b>${esc(c.status)}</b><div class="muted">Beleg: „${esc(c.satz)}“ · ${esc(c.entschieden_von)}</div></li>`).join('') + '</ul>' : '<p class="muted">Keine Änderung vorgeschlagen.</p>'}
      ${v.kunden !== '' && v.kunden != null ? `<p>Aktive Kunden laut Nachricht: <b>${esc(v.kunden)}</b></p>` : ''}
      ${warnings.map(w => `<p class="alert">⚠️ ${esc(w)}</p>`).join('')}
      <a class="btn" href="${esc(v.freigabe_url)}" target="_blank">Prüfen und freigeben →</a>
    </div>`;
  }).join('') : '<p class="muted">Keine offenen Vorschläge.</p>';

  const auditRows = audit.map(a => `<tr><td>${time(a.zeit)}</td><td>${esc(a.stadt)}</td><td>${esc(a.wer)}</td><td>${esc(a.aktion)}</td><td>${esc(a.details)}</td></tr>`).join('');
  const options = partners.map(p => `<option value="${p.partner_id}">${esc(p.stadt)} (Tag ${p.day})</option>`).join('');

  return `<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Onboarding-Cockpit (n8n)</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2430;--muted:#667085;--line:#e4e7ec;--ok:#12805c;--warn:#b25e09;--crit:#c0262d;--accent:#6a55c9}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 10px}
.muted{color:var(--muted);font-size:13px}.sub{color:var(--muted);margin:0 0 16px}
.kpis{display:flex;gap:10px;flex-wrap:wrap}.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:120px}
.kpi b{display:block;font-size:22px}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:760px}th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);background:#fafbfc}
tr.crit td:first-child{border-left:4px solid var(--crit)}tr.warn td:first-child{border-left:4px solid var(--warn)}tr.ok td:first-child{border-left:4px solid var(--ok)}
td ul{margin:0;padding-left:18px}li.crit{color:var(--crit)}li.warn{color:var(--warn)}.lvl{white-space:nowrap}
.bar{height:5px;background:var(--line);border-radius:3px;margin-top:4px;width:90px}.bar span{display:block;height:100%;background:var(--accent);border-radius:3px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}.card ul{padding-left:18px}
.row{display:flex;justify-content:space-between;gap:8px}.msg{font-style:italic;color:#344054}
.alert{background:#fdecec;color:var(--crit);border-radius:8px;padding:8px 10px}
.btn{display:inline-block;background:var(--accent);color:#fff;border:0;border-radius:8px;padding:8px 14px;text-decoration:none;font:inherit;cursor:pointer}
form{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;display:grid;gap:10px}
select,textarea{font:inherit;padding:8px;border:1px solid var(--line);border-radius:8px;width:100%}textarea{min-height:80px}
.ex{display:flex;gap:6px;flex-wrap:wrap}.ex button{background:#eef0f4;border:0;border-radius:14px;padding:4px 10px;font-size:13px;cursor:pointer}
#result{white-space:pre-wrap}
.legend span{margin-right:12px}
</style></head><body><main>
<h1>Onboarding-Cockpit</h1>
<p class="sub">Komplett in n8n gebaut: Webhooks, Data Tables, Code-Regeln, lokale KI (Ollama) und Freigabe-Formular. Stand ${de(today)}. Erfundene Demo-Daten.</p>
<div class="kpis"><div class="kpi"><b>${partners.length}</b>Partner im Onboarding</div><div class="kpi"><b style="color:var(--crit)">${count('kritisch')}</b>kritisch</div>
<div class="kpi"><b style="color:var(--warn)">${count('Achtung')}</b>Achtung</div><div class="kpi"><b style="color:var(--ok)">${count('im Plan')}</b>im Plan</div><div class="kpi"><b>${open.length}</b>Vorschläge offen</div></div>

<h2>Partner und Ampel</h2>
<div class="wrap"><table><tr><th>Standort</th><th>Fortschritt</th><th>Erledigt</th><th>Kunden</th><th>Ampel</th><th>Hinweise (Regel und Grund)</th></tr>${partnerRows}</table></div>

<h2>Offene Vorschläge (warten auf Freigabe)</h2>
<div class="grid">${openCards}</div>

<h2>Neues Partner-Update senden</h2>
<form id="f"><label>Partner<select name="partner_id">${options}</select></label>
<label>Nachricht des Partners<textarea name="nachricht" required></textarea></label>
<div class="ex muted">Beispiele: <button type="button">Wir haben schon 3 Kunden! Das Büro ist angemietet, aber mit der Versicherung klappt es leider noch nicht.</button>
<button type="button">Der Bescheid ist da: Wir sind offiziell anerkannt!</button><button type="button">Die Startschulung machen wir im Dezember.</button></div>
<div><button class="btn">Vorschlag erstellen</button></div><div id="result" class="muted"></div></form>

<h2>Protokoll (letzte Einträge)</h2>
<div class="wrap"><table><tr><th>Zeit</th><th>Standort</th><th>Wer</th><th>Aktion</th><th>Details</th></tr>${auditRows}</table></div>
</main>
<script>
const f=document.getElementById('f'),out=document.getElementById('result');
document.querySelectorAll('.ex button').forEach(b=>b.onclick=()=>{f.nachricht.value=b.textContent});
f.onsubmit=async e=>{e.preventDefault();out.textContent='Wird ausgewertet …';
try{const r=await fetch('/webhook/onboarding-update',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({partner_id:Number(f.partner_id.value),nachricht:f.nachricht.value})});const j=await r.json();
if(!j.ok){out.textContent='Fehler: '+(j.fehler||r.status);return}
out.innerHTML='Vorschlag #'+j.vorschlag_nr+' gespeichert (noch nichts geändert). '+(j.aenderungen.length?j.aenderungen.map(c=>c.titel+' → '+c.status).join(', '):'Keine Änderung.')+
(j.warnungen.length?'<br>⚠️ '+j.warnungen.join(' '):'')+'<br><a class="btn" target="_blank" href="'+j.freigabe_url+'">Prüfen und freigeben →</a> <a href="">Seite neu laden</a>';
}catch(err){out.textContent='Fehler: '+err}};
</script></body></html>`;
}
