// Traffic light per partner. Plain rules, no AI: every finding says which rule fired and why.
// Same logic as app/status.py and service.risks().

const LEVELS = ['im Plan', 'Achtung', 'kritisch'];
const TARGET_CUSTOMERS = 10;
const PERMIT_WEEKS = [4, 8];  // handbook: the authority usually needs 4 to 8 weeks

const dayMs = 86400000;
const toDate = iso => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
const daysBetween = (a, b) => Math.round((toDate(a) - toDate(b)) / dayMs);
const plusDays = (iso, n) => new Date(toDate(iso) + n * dayMs).toISOString().slice(0, 10);
const ddmm = iso => `${iso.slice(8, 10)}.${iso.slice(5, 7)}.`;

// partner: {start_date, active_customers}; tasks: {taskId: {status, done_on, note}}; today: 'YYYY-MM-DD'
function assess(partner, tasks, checklist, today) {
  const byId = Object.fromEntries(checklist.map(t => [t.id, t]));
  const gate = checklist.filter(t => t.gate).map(t => t.id);
  const day = daysBetween(today, partner.start_date) + 1;
  const findings = [];
  const add = (level, text) => findings.push({ level, text });

  // 1. First customer visit without the handbook's preconditions: the most serious case.
  const missingGate = gate.filter(g => tasks[g].status !== 'erledigt');
  if (tasks.erster_kunde.status === 'erledigt' && missingGate.length) {
    add('kritisch', 'Kundeneinsätze laufen, aber Voraussetzungen fehlen: ' + missingGate.map(g => byId[g].title).join(', ') + '.');
  }
  // 2. Blocked and overdue tasks. A gate task blocks the start of customer care, so it is critical.
  for (const t of checklist) {
    const row = tasks[t.id];
    if (row.status === 'blockiert') {
      add(t.gate ? 'kritisch' : 'Achtung', `Blockiert: ${t.title}` + (row.note ? ` (${row.note})` : '') + '.');
    } else if (row.status === 'offen' && t.due_day < day) {
      add(t.gate ? 'kritisch' : 'Achtung', `Überfällig seit Tag ${t.due_day}: ${t.title} (zuständig: ${t.owner}).`);
    }
  }
  // 3. Permit forecast: the authority needs 4-8 weeks after the application.
  if (tasks.zulassung.status !== 'erledigt') {
    let filed, basis;
    if (tasks.antrag.status === 'erledigt' && tasks.antrag.done_on) {
      filed = tasks.antrag.done_on;
      basis = `Antrag gestellt am ${ddmm(filed)}`;
    } else {
      filed = today;
      basis = 'Antrag noch nicht gestellt, frühestens heute';
    }
    const first = daysBetween(plusDays(filed, PERMIT_WEEKS[0] * 7), partner.start_date) + 1;
    const last = daysBetween(plusDays(filed, PERMIT_WEEKS[1] * 7), partner.start_date) + 1;
    if (first > 90) {
      add('kritisch', `Zulassung kommt erst zwischen Tag ${first} und ${last} (${basis}). Vor Tag 90 sind keine Kundeneinsätze möglich.`);
    } else if (last > 90) {
      add('Achtung', `Zulassung kommt zwischen Tag ${first} und ${last} (${basis}). Das Ziel von ${TARGET_CUSTOMERS} Kunden bis Tag 90 ist gefährdet.`);
    }
  }
  // 4. Customer target in phase 3.
  const customers = partner.active_customers;
  if (day > 60 && day <= 90 && customers < TARGET_CUSTOMERS && !missingGate.length) {
    const left = 90 - day + 1;
    const need = TARGET_CUSTOMERS - customers;
    if (need > left / 2) {  // more than one new customer every two days: unrealistic
      add('Achtung', `${customers} von ${TARGET_CUSTOMERS} Kunden, noch ${left} Tage bis Tag 90 (nötig: ${need} neue Kunden).`);
    }
  }
  const done = checklist.filter(t => tasks[t.id].status === 'erledigt').length;
  const level = findings.reduce((m, f) => (LEVELS.indexOf(f.level) > LEVELS.indexOf(m) ? f.level : m), 'im Plan');
  findings.sort((a, b) => LEVELS.indexOf(b.level) - LEVELS.indexOf(a.level));
  return { day, phase: day <= 30 ? 1 : day <= 60 ? 2 : 3, done, total: checklist.length, level, findings,
    ready_for_customers: !missingGate.length, missing_for_customers: missingGate.map(g => byId[g].title) };
}

// Telegram text: partners that need attention, most serious first.
function risksText(assessed, pending) {
  const rows = assessed.filter(p => p.level !== 'im Plan')
    .sort((a, b) => (a.level !== 'kritisch') - (b.level !== 'kritisch') || b.day - a.day);
  const icon = { kritisch: '🔴', Achtung: '🟠' };
  const lines = [`🧭 Onboarding neuer Partner: ${rows.filter(p => p.level === 'kritisch').length} kritisch, ` +
    `${rows.filter(p => p.level === 'Achtung').length} mit Hinweis`];
  for (const p of rows) lines.push(`${icon[p.level]} ${p.city} (Tag ${p.day}): ${p.findings[0].text}`);
  if (pending) lines.push(`📨 ${pending} Partner-Update(s) warten auf Freigabe.`);
  lines.push('Details im Onboarding-Cockpit. (Erfundene Demo-Daten)');
  return { count: rows.length, text: lines.join('\n') };
}
